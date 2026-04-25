"""
firms.auth
==========
Re-usable helpers for enforcing multi-tenant access control and subscription
limits inside Django Ninja API endpoints (and plain Django views).

Usage in a Django Ninja router
------------------------------
    from firms.auth import require_membership, MembershipRole

    @router.get("/leads")
    def list_leads(request):
        membership = require_membership(request)          # any role
        # ... firm-scoped query using request.firm ...

    @router.post("/leads")
    def create_lead(request, payload: LeadIn):
        membership = require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
        # ...
"""

from django.http import HttpRequest

from firms.models import Firm, Membership, MembershipRole

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
# Role ordering — higher index = more privileges
# ---------------------------------------------------------------------------

_ROLE_ORDER = [MembershipRole.WORKER, MembershipRole.ADMIN, MembershipRole.OWNER]


def _role_rank(role: str) -> int:
    try:
        return _ROLE_ORDER.index(role)
    except ValueError:
        return -1


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

    if _role_rank(membership.role) < _role_rank(min_role):
        raise PermissionDenied(
            f"Role '{membership.get_role_display()}' is insufficient. "
            f"Required: '{MembershipRole(min_role).label}'."
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
    * 50 Leads total

    Raises :exc:`SubscriptionRequired` if any limit is exceeded.
    """
    if firm.subscription_tier == "pro":
        return  # no hard limits on Pro

    from crm.models import Lead  # local import to avoid circular dependency

    member_count = firm.memberships.count()
    # This guard is called *before* adding a new member.
    # When there are already 2 members, adding one more would exceed the
    # free-tier limit of 2, so we raise here.
    if member_count >= 2:
        raise SubscriptionRequired(
            "Free tier allows a maximum of 2 team members. "
            "Upgrade to Pro to invite more."
        )

    lead_count = Lead.objects.filter(firm=firm).count()
    if lead_count >= 50:
        raise SubscriptionRequired(
            "Free tier allows a maximum of 50 leads. "
            "Upgrade to Pro for unlimited leads."
        )
