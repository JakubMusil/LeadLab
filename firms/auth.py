"""
firms.auth
==========
Re-usable helpers for enforcing multi-tenant access control and subscription
limits inside Django Ninja API endpoints (and plain Django views).

Usage in a Django Ninja router
------------------------------
    from firms.auth import require_membership, InvitationRole

    @router.get("/records")
    def list_leads(request):
        membership = require_membership(request)          # any role
        # ... firm-scoped query using request.firm ...

    @router.post("/records")
    def create_lead(request, payload: LeadIn):
        membership = require_membership(request, min_role=InvitationRole.MEMBER)
        require_active_subscription(request.firm)
        # ...
"""

from django.http import HttpRequest

from firms.models import Firm, Membership, InvitationRole
from firms.permissions import Permission, has_min_role

# ---------------------------------------------------------------------------
# SuperuserMembership sentinel
# ---------------------------------------------------------------------------


class SuperuserMembership:
    """Lightweight sentinel returned by auth gates when ``request.user.is_superuser``.

    Django superusers bypass all firm-level permission and role checks.
    They are above Owners and have full access to every workspace and resource.
    This sentinel exposes the same interface as ``firms.models.Membership`` so
    that callers of ``require_membership`` / ``require_permission`` can use the
    returned object without special-casing the superuser path.
    """

    # Role constants so callers can use the same attributes as a real Membership.
    primary_role: str = "owner"
    is_owner: bool = True
    is_admin_or_above: bool = True
    is_expired: bool = False
    default_scope: str = "all"
    # Superusers are not assigned to any specific team; team-level scoping is
    # irrelevant because they already have global access to all records.
    team = None
    # Per-membership preferences mirrored from ``firms.models.Membership`` so
    # endpoints that read these attributes (e.g. ``/digest-preference``) work
    # uniformly for both real members and superuser sentinels. Defaults match
    # the model field defaults.
    weekly_digest_enabled: bool = True

    def __init__(self, request: HttpRequest) -> None:
        self.firm = getattr(request, "firm", None)
        self.firm_id = self.firm.pk if self.firm else None
        self.user = request.user
        self.user_id = request.user.pk if request.user else None
        # Expose pk as None – superuser sentinel is not a real DB row.
        self.pk = None
        self.id = None

    # Expose a no-op for method callers that expect a real Membership.
    # This method exists solely for interface compatibility with ``Membership``
    # and is intentionally empty: superuser sentinels do not persist to the DB.
    def _assign_system_role_by_code(self, role_code: str) -> None:  # pragma: no cover
        pass

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SuperuserMembership user={self.user_id} firm={self.firm_id}>"


# ---------------------------------------------------------------------------
# Exceptions (subclass of Exception so they can be caught as regular errors
# or converted to HTTP responses by the API layer).
# ---------------------------------------------------------------------------


class PermissionDenied(Exception):
    """Raised when a user lacks the required Firm membership / role."""
    http_status = 403


class AuthenticationRequired(Exception):
    """Raised when the user is not authenticated at all."""
    http_status = 401


class SubscriptionRequired(Exception):
    """Raised when the Firm's subscription does not allow the operation."""
    http_status = 402


class FirmNotFound(Exception):
    """Raised when no active Firm matches the provided ID."""
    http_status = 404


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Core enforcement helpers
# ---------------------------------------------------------------------------


def require_membership(
    request: HttpRequest,
    min_role: str = InvitationRole.MEMBER,
) -> "Membership | SuperuserMembership":
    """
    Validate that the current request has a valid authenticated user with an
    active Membership in ``request.firm`` at *at least* ``min_role``.

    Django superusers (``request.user.is_superuser``) bypass all firm-level
    membership and role checks – they are above Owners and always get a
    :class:`SuperuserMembership` sentinel back.

    Returns the resolved :class:`~firms.models.Membership` (or
    :class:`SuperuserMembership` for superusers) on success.
    Raises one of the custom exceptions above on failure.
    """
    if not request.user or not request.user.is_authenticated:
        raise AuthenticationRequired("Authentication required.")

    if not getattr(request, "firm", None):
        raise FirmNotFound("No active Firm found for this request.")

    # Superuser short-circuit: Django superusers have full access to every firm.
    # Use strict identity check (is True) to guard against MagicMock in tests
    # where mock.is_superuser returns a truthy sentinel rather than a real bool.
    if getattr(request.user, "is_superuser", False) is True:
        return SuperuserMembership(request)

    membership: Membership | None = getattr(request, "membership", None)
    if membership is None:
        raise PermissionDenied(
            f"User '{request.user.email}' is not a member of firm '{request.firm.name}'."
        )

    if membership.is_expired:
        raise PermissionDenied(
            f"Membership of '{request.user.email}' in firm '{request.firm.name}' has expired."
        )

    if not has_min_role(membership, min_role):
        raise PermissionDenied(
            f"Role '{membership.primary_role}' is insufficient. "
            f"Required: '{min_role}'."
        )

    return membership


# ---------------------------------------------------------------------------
# Permission-based gate (Phase 4+)
# ---------------------------------------------------------------------------


def require_permission(
    request: HttpRequest,
    perm: Permission,
    *,
    resource=None,  # noqa: ARG001 – used in Phase 6+ for per-resource checks
) -> "Membership | SuperuserMembership":
    """
    Validate that the current request holds *perm*.

    Django superusers (``request.user.is_superuser``) bypass all permission
    checks and receive a :class:`SuperuserMembership` sentinel.

    For regular users, resolves the membership's effective permissions from the
    DB-backed ``Role`` / ``RolePermission`` tables via
    :func:`crm.permissions.resolve_effective_permissions`.

    Returns the resolved :class:`~firms.models.Membership` (or
    :class:`SuperuserMembership` for superusers) on success.
    Raises one of the standard auth exceptions on failure.
    """
    if not request.user or not request.user.is_authenticated:
        raise AuthenticationRequired("Authentication required.")

    if not getattr(request, "firm", None):
        raise FirmNotFound("No active Firm found for this request.")

    # Superuser short-circuit: Django superusers have full access to every firm.
    # Use strict identity check (is True) to guard against MagicMock in tests
    # where mock.is_superuser returns a truthy sentinel rather than a real bool.
    if getattr(request.user, "is_superuser", False) is True:
        return SuperuserMembership(request)

    membership: Membership | None = getattr(request, "membership", None)
    if membership is None:
        raise PermissionDenied(
            f"User '{request.user.email}' is not a member of firm '{request.firm.name}'."
        )

    if membership.is_expired:
        raise PermissionDenied(
            f"Membership of '{request.user.email}' in firm '{request.firm.name}' has expired."
        )

    # Owner short-circuit: owners always have all permissions
    if membership.is_owner:
        return membership

    from crm.permissions import resolve_effective_permissions  # local import to avoid circular

    effective = resolve_effective_permissions(membership)
    perm_code = perm.value if isinstance(perm, Permission) else str(perm)

    if perm_code not in effective:
        raise PermissionDenied(
            f"Permission '{perm_code}' is not granted to role '{membership.primary_role}'."
        )

    return membership


def require_active_subscription(firm: Firm) -> None:
    """
    Raise :exc:`SubscriptionRequired` if the firm does not have an active
    subscription that permits write operations.

    Free tier is considered "active" — limits are enforced separately via
    :func:`check_tier_limits`.
    """
    if not firm.subscription_active:
        raise SubscriptionRequired(
            f"Firm '{firm.name}' does not have an active subscription. "
            "Please upgrade your plan to continue."
        )


def check_tier_limits(firm: Firm) -> None:
    """
    Enforce usage limits for the Free tier:

    * 1 Firm  (checked externally at registration time)
    * 2 Users (Members)
    * 50 Records total

    Raises :exc:`SubscriptionRequired` if any limit is exceeded.
    """
    if firm.subscription_tier == "pro":
        return  # no hard limits on Pro

    from crm.models import PipelineRecord  # local import to avoid circular dependency

    member_count = firm.memberships.count()
    # This guard is called *before* adding a new member.
    # When there are already 2 members, adding one more would exceed the
    # free-tier limit of 2, so we raise here.
    if member_count >= 2:
        raise SubscriptionRequired(
            "Free tier allows a maximum of 2 team members. "
            "Upgrade to Pro to invite more."
        )

    lead_count = PipelineRecord.objects.filter(firm=firm).count()
    if lead_count >= 50:
        raise SubscriptionRequired(
            "Free tier allows a maximum of 50 records. "
            "Upgrade to Pro for unlimited records."
        )
