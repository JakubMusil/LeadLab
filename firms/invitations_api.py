"""
Django Ninja API router – Public Invitation endpoints (no authentication required)

Endpoints:
    GET    /invitations/{token}          — preview an invitation
    POST   /invitations/{token}/accept   — accept an invitation
"""
from typing import Optional

from django.db import transaction
from django.utils import timezone as django_timezone
from ninja import Router, Schema

from firms.models import Invitation, Membership

public_router = Router(tags=["invitations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InvitationOut(Schema):
    id: str
    token: str
    email: str
    role: str
    firm_id: str
    firm_name: str
    invited_by_email: Optional[str]
    expires_at: str
    is_expired: bool
    is_accepted: bool


class AcceptInvitationIn(Schema):
    password: str
    first_name: str = ""
    last_name: str = ""
    timezone: str = "UTC"


class AcceptOut(Schema):
    detail: str
    user_email: str
    firm_name: str
    role: str


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Public: preview & accept
# ---------------------------------------------------------------------------

@public_router.get(
    "/{token}",
    auth=None,
    response={200: InvitationOut, 404: ErrorOut, 410: ErrorOut},
)
def preview_invitation(request, token: str):
    """
    Return details of an invitation so the frontend can display the firm name,
    role, and whether the link is still valid.
    """
    try:
        invitation = Invitation.objects.select_related("firm", "invited_by").get(
            token=token
        )
    except Invitation.DoesNotExist:
        return 404, {"detail": "Invitation not found."}

    if invitation.is_accepted:
        return 410, {"detail": "This invitation has already been accepted."}

    if invitation.is_expired:
        return 410, {"detail": "This invitation has expired."}

    return 200, _invitation_out(invitation)


@public_router.post(
    "/{token}/accept",
    auth=None,
    response={200: AcceptOut, 400: ErrorOut, 404: ErrorOut, 410: ErrorOut},
)
def accept_invitation(request, token: str, payload: AcceptInvitationIn):
    """
    Accept an invitation.

    - If the invited email already has an account the provided ``password`` is
      used to authenticate; on success the user is added to the Firm.
    - If no account exists a new one is created with the supplied ``password``
      and optional profile fields, then the user is added to the Firm.

    In both cases the Membership is created atomically with ``accepted_at``
    being stamped on the Invitation.
    """
    from django.contrib.auth import authenticate

    from users.models import User

    try:
        invitation = Invitation.objects.select_related("firm").get(token=token)
    except Invitation.DoesNotExist:
        return 404, {"detail": "Invitation not found."}

    if invitation.is_accepted:
        return 410, {"detail": "This invitation has already been accepted."}

    if invitation.is_expired:
        return 410, {"detail": "This invitation has expired."}

    firm = invitation.firm
    if not firm.is_active:
        return 400, {"detail": "The firm is no longer active."}

    existing_user = User.objects.filter(email=invitation.email).first()

    with transaction.atomic():
        if existing_user:
            # Authenticate the existing user with the provided password.
            authenticated = authenticate(
                request, username=invitation.email, password=payload.password
            )
            if authenticated is None:
                return 400, {"detail": "Invalid password for the existing account."}
            user = authenticated
        else:
            # Create a new account for the invitee.
            user = User.objects.create_user(
                email=invitation.email,
                password=payload.password,
                first_name=payload.first_name,
                last_name=payload.last_name,
                timezone=payload.timezone,
            )

        # Guard: do not create a duplicate membership.
        if Membership.objects.filter(user=user, firm=firm).exists():
            return 400, {"detail": "You are already a member of this Firm."}

        membership = Membership.objects.create(
            user=user,
            firm=firm,
            role=invitation.role,  # handled by MembershipManager → assigns system role via M2M
            default_scope=invitation.invited_default_scope or "own",
            team_id=invitation.invited_team_id,
        )
        # Apply granular roles if specified in the invitation (overrides the
        # default system role assigned above from invitation.role).
        if invitation.invited_role_codes:
            from firms.models import Role
            roles = Role.objects.filter(
                firm=firm, code__in=invitation.invited_role_codes
            )
            membership.roles.set(roles)
        invitation.accepted_at = django_timezone.now()
        invitation.save(update_fields=["accepted_at"])

    return 200, {
        "detail": "Invitation accepted.",
        "user_email": user.email,
        "firm_name": firm.name,
        "role": invitation.role,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invitation_out(invitation: Invitation) -> dict:
    return {
        "id": str(invitation.id),
        "token": str(invitation.token),
        "email": invitation.email,
        "role": invitation.role,
        "firm_id": str(invitation.firm_id),
        "firm_name": invitation.firm.name,
        "invited_by_email": (
            invitation.invited_by.email if invitation.invited_by else None
        ),
        "expires_at": invitation.expires_at.isoformat(),
        "is_expired": invitation.is_expired,
        "is_accepted": invitation.is_accepted,
    }
