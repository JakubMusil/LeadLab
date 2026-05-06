"""
firms.auth
==========
Re-usable helpers for enforcing multi-tenant access control and subscription
limits inside Django Ninja API endpoints (and plain Django views).

Usage in a Django Ninja router
------------------------------
    from firms.auth import require_membership, MembershipRole

    @router.get("/records")
    def list_leads(request):
        membership = require_membership(request)          # any role
        # ... firm-scoped query using request.firm ...

    @router.post("/records")
    def create_lead(request, payload: LeadIn):
        membership = require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
        # ...
"""

from django.conf import settings
from django.http import HttpRequest

from firms.models import Firm, Membership, MembershipRole
from firms.permissions import Permission, has_min_role

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
    min_role: str = MembershipRole.WORKER,
) -> Membership:
    """
    Validate that the current request has a valid authenticated user with an
    active Membership in ``request.firm`` at *at least* ``min_role``.

    Returns the resolved :class:`~firms.models.Membership` on success.
    Raises one of the custom exceptions above on failure.
    """
    if not request.user or not request.user.is_authenticated:
        raise AuthenticationRequired("Authentication required.")

    if not getattr(request, "firm", None):
        raise FirmNotFound("No active Firm found for this request.")

    membership: Membership | None = getattr(request, "membership", None)
    if membership is None:
        raise PermissionDenied(
            f"User '{request.user.email}' is not a member of firm '{request.firm.name}'."
        )

    if not has_min_role(membership, min_role):
        raise PermissionDenied(
            f"Role '{membership.get_role_display()}' is insufficient. "
            f"Required: '{MembershipRole(min_role).label}'."
        )

    return membership


# ---------------------------------------------------------------------------
# Permission-based gate (Phase 4)
# ---------------------------------------------------------------------------

# Maps a Permission code to the legacy min_role that covers it.
# Used as fallback when PERMISSIONS_V2_ENABLED is False.
_PERMISSION_TO_MIN_ROLE: dict[str, str] = {
    Permission.RECORD_VIEW: MembershipRole.WORKER,
    Permission.RECORD_CREATE: MembershipRole.WORKER,
    Permission.RECORD_EDIT: MembershipRole.WORKER,
    Permission.RECORD_DELETE: MembershipRole.ADMIN,
    Permission.CATEGORY_VIEW: MembershipRole.WORKER,
    Permission.ACTIVITY_CREATE: MembershipRole.WORKER,
    Permission.PROPOSAL_CREATE: MembershipRole.WORKER,
    Permission.REPORT_VIEW: MembershipRole.WORKER,
    Permission.CATEGORY_MANAGE: MembershipRole.ADMIN,
    Permission.TEAM_MANAGE: MembershipRole.ADMIN,
    Permission.ROLE_MANAGE: MembershipRole.ADMIN,
    Permission.INTEGRATIONS_MANAGE: MembershipRole.ADMIN,
    Permission.STREAMLINE_VIEW_ALL: MembershipRole.ADMIN,
    Permission.BILLING_MANAGE: MembershipRole.OWNER,
    Permission.FIRM_DELETE: MembershipRole.OWNER,
    Permission.FIRM_TRANSFER: MembershipRole.OWNER,
}


def require_permission(
    request: HttpRequest,
    perm: Permission,
    *,
    resource=None,  # noqa: ARG001 – used in Phase 6+ for per-resource checks
) -> Membership:
    """
    Validate that the current request holds *perm*.

    When ``settings.PERMISSIONS_V2_ENABLED`` is ``False`` (default):
        Maps *perm* to the equivalent legacy ``min_role`` and delegates to
        :func:`require_membership`, keeping existing behaviour unchanged.

    When ``settings.PERMISSIONS_V2_ENABLED`` is ``True``:
        Resolves the membership's effective permissions from the DB-backed
        ``Role`` / ``RolePermission`` tables via
        :func:`crm.permissions.resolve_effective_permissions`.

    Returns the resolved :class:`~firms.models.Membership` on success.
    Raises one of the standard auth exceptions on failure.
    """
    if not request.user or not request.user.is_authenticated:
        raise AuthenticationRequired("Authentication required.")

    if not getattr(request, "firm", None):
        raise FirmNotFound("No active Firm found for this request.")

    membership: Membership | None = getattr(request, "membership", None)
    if membership is None:
        raise PermissionDenied(
            f"User '{request.user.email}' is not a member of firm '{request.firm.name}'."
        )

    if not getattr(settings, "PERMISSIONS_V2_ENABLED", False):
        # Legacy path: map permission → min_role and delegate
        min_role = _PERMISSION_TO_MIN_ROLE.get(perm, MembershipRole.ADMIN)
        if not has_min_role(membership, min_role):
            raise PermissionDenied(
                f"Role '{membership.get_role_display()}' is insufficient for permission '{perm}'."
            )
        return membership

    # V2 path: resolve via DB roles
    from crm.permissions import resolve_effective_permissions  # local import to avoid circular

    effective = resolve_effective_permissions(membership)
    perm_code = perm.value if isinstance(perm, Permission) else str(perm)

    # Owner short-circuit: owners always have all permissions
    if membership.role == MembershipRole.OWNER:
        return membership

    if perm_code not in effective:
        raise PermissionDenied(
            f"Permission '{perm_code}' is not granted to role '{membership.get_role_display()}'."
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
