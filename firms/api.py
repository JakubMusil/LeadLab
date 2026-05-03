"""
Django Ninja API router – Firms & Memberships

All write endpoints enforce:
  1. Valid session authentication.
  2. Membership in the target Firm (via TenantMiddleware + require_membership).
  3. Role-based access (Owners can do everything; Workers are read-only for team mgmt).
"""
import datetime
from decimal import Decimal
from typing import List, Optional

from django.db import transaction
from ninja import File, Form, Router, Schema, UploadedFile
from ninja.security import django_auth

from firms.auth import (
    AuthenticationRequired,
    FirmNotFound,
    MembershipRole,
    PermissionDenied,
    SubscriptionRequired,
    check_tier_limits,
    require_membership,
)
from firms.models import Firm, Invitation, Membership

router = Router(tags=["firms"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FirmOut(Schema):
    id: str
    name: str
    slug: str
    subscription_tier: str
    subscription_active: bool
    is_active: bool
    logo_url: Optional[str] = None
    primary_color: str = '#dc2626'
    default_currency: str = 'CZK'
    number_locale: str = 'cs-CZ'
    exchange_rate_mode: str = 'auto'


class FirmIn(Schema):
    name: str


class FirmUpdateIn(Schema):
    name: Optional[str] = None


class FirmCurrencyIn(Schema):
    default_currency: Optional[str] = None
    number_locale: Optional[str] = None
    exchange_rate_mode: Optional[str] = None


class FirmBrandingIn(Schema):
    primary_color: Optional[str] = None


class MemberRoleUpdateIn(Schema):
    role: str


class MembershipOut(Schema):
    id: str
    user_id: str
    user_email: str
    user_full_name: str
    role: str
    firm_id: str


class MemberInviteIn(Schema):
    email: str
    role: str = MembershipRole.WORKER


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


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Exchange Rate schemas
# ---------------------------------------------------------------------------

class ExchangeRateOut(Schema):
    id: str
    from_currency: str
    to_currency: str
    rate: str           # Decimal as string to preserve precision
    source: str
    valid_from: str
    valid_to: Optional[str]
    note: str
    created_by_email: Optional[str]
    created_at: str


class ExchangeRateIn(Schema):
    from_currency: str
    rate: str           # Decimal as string
    valid_from: str     # ISO date string
    note: str = ""


class ExchangeRatePatchIn(Schema):
    note: Optional[str] = None


class ExchangeRatePreviewOut(Schema):
    from_currency: str
    amount: str
    canonical_amount: Optional[str]
    canonical_currency: str
    rate_used: Optional[str]
    rate_source: Optional[str]


# ---------------------------------------------------------------------------
# Firm CRUD
# ---------------------------------------------------------------------------

def _firm_out(firm: Firm) -> dict:
    logo_url = None
    if firm.logo:
        from django.conf import settings
        logo_url = settings.MEDIA_URL + str(firm.logo)
    return {
        "id": str(firm.id),
        "name": firm.name,
        "slug": firm.slug,
        "subscription_tier": firm.subscription_tier,
        "subscription_active": firm.subscription_active,
        "is_active": firm.is_active,
        "logo_url": logo_url,
        "primary_color": firm.primary_color,
        "default_currency": firm.default_currency,
        "number_locale": firm.number_locale,
        "exchange_rate_mode": firm.exchange_rate_mode,
    }


@router.get("/", auth=django_auth, response=List[FirmOut])
def list_firms(request):
    """Return all Firms the authenticated user is a member of."""
    memberships = Membership.objects.filter(
        user=request.user
    ).select_related("firm")
    return [_firm_out(m.firm) for m in memberships]


@router.post("/", auth=django_auth, response={201: FirmOut, 400: ErrorOut})
def create_firm(request, payload: FirmIn):
    """Create a new Firm and make the creator its Owner."""
    with transaction.atomic():
        firm = Firm.objects.create(name=payload.name)
        Membership.objects.create(
            user=request.user,
            firm=firm,
            role=MembershipRole.OWNER,
        )
    return 201, _firm_out(firm)


@router.get("/{firm_id}", auth=django_auth, response={200: FirmOut, 403: ErrorOut, 404: ErrorOut})
def get_firm(request, firm_id: str):
    """Return details for a specific Firm (membership required)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    if not Membership.objects.filter(user=request.user, firm=firm).exists():
        return 403, {"detail": "You are not a member of this Firm."}

    return 200, _firm_out(firm)


@router.delete("/{firm_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
def delete_firm(request, firm_id: str):
    """Delete a Firm (Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not membership.is_owner:
        return 403, {"detail": "Only the Owner can delete a Firm."}

    firm.delete()
    return 204, None


@router.patch("/{firm_id}", auth=django_auth, response={200: FirmOut, 403: ErrorOut, 404: ErrorOut})
def update_firm(request, firm_id: str, payload: FirmUpdateIn):
    """Rename a Firm (Admin or Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can rename a Firm."}

    if payload.name is not None:
        firm.name = payload.name
        firm.save(update_fields=["name"])

    return 200, _firm_out(firm)




@router.patch("/{firm_id}/currency", auth=django_auth, response={200: FirmOut, 403: ErrorOut, 404: ErrorOut})
def update_firm_currency(request, firm_id: str, payload: FirmCurrencyIn):
    """Update currency & formatting settings (Admin or Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can update currency settings."}

    update_fields = []
    if payload.default_currency is not None:
        firm.default_currency = payload.default_currency.upper()[:3]
        update_fields.append("default_currency")
    if payload.number_locale is not None:
        firm.number_locale = payload.number_locale
        update_fields.append("number_locale")
    if payload.exchange_rate_mode is not None:
        if payload.exchange_rate_mode not in ("auto", "manual"):
            return 403, {"detail": "exchange_rate_mode must be 'auto' or 'manual'."}
        firm.exchange_rate_mode = payload.exchange_rate_mode
        update_fields.append("exchange_rate_mode")
    if update_fields:
        firm.save(update_fields=update_fields)

    return 200, _firm_out(firm)




# ---------------------------------------------------------------------------
# Exchange Rate Management
# ---------------------------------------------------------------------------

def _exchange_rate_out(rate) -> dict:
    return {
        "id": str(rate.id),
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
        "rate": str(rate.rate),
        "source": rate.source,
        "valid_from": rate.valid_from.isoformat(),
        "valid_to": rate.valid_to.isoformat() if rate.valid_to else None,
        "note": rate.note,
        "created_by_email": rate.created_by.email if rate.created_by else None,
        "created_at": rate.created_at.isoformat(),
    }


def _get_firm_and_check_admin(request, firm_id: str):
    """Return (firm, membership) or raise PermissionDenied/FirmNotFound."""
    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        raise FirmNotFound()
    try:
        membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        raise PermissionDenied()
    if not membership.is_admin_or_above:
        raise PermissionDenied()
    return firm, membership


@router.get(
    "/{firm_id}/exchange-rates/",
    auth=django_auth,
    response={200: List[ExchangeRateOut], 403: ErrorOut, 404: ErrorOut},
)
def list_exchange_rates(request, firm_id: str, include_history: bool = False):
    """List exchange rates for a firm. Pass ?include_history=true for closed rates."""
    from firms.models import FirmExchangeRate
    try:
        firm, _ = _get_firm_and_check_admin(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Admin or Owner access required."}

    qs = FirmExchangeRate.objects.filter(firm=firm).select_related("created_by")
    if not include_history:
        qs = qs.filter(valid_to__isnull=True)
    return 200, [_exchange_rate_out(r) for r in qs]


@router.post(
    "/{firm_id}/exchange-rates/",
    auth=django_auth,
    response={201: ExchangeRateOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_exchange_rate(request, firm_id: str, payload: ExchangeRateIn):
    """
    Create a new manual exchange rate.
    Automatically closes any existing active rate for the same currency pair.
    """
    from firms.models import FirmExchangeRate

    try:
        firm, _ = _get_firm_and_check_admin(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Admin or Owner access required."}

    try:
        rate_decimal = Decimal(payload.rate)
        valid_from = datetime.date.fromisoformat(payload.valid_from)
    except Exception:
        return 400, {"detail": "Invalid rate or valid_from date."}

    if rate_decimal <= 0:
        return 400, {"detail": "Rate must be greater than zero."}

    from_currency = payload.from_currency.upper()[:3]
    to_currency = firm.default_currency

    with transaction.atomic():
        # Close any currently active rate for this pair
        FirmExchangeRate.objects.filter(
            firm=firm,
            from_currency=from_currency,
            to_currency=to_currency,
            valid_to__isnull=True,
        ).update(valid_to=valid_from - datetime.timedelta(days=1))

        new_rate = FirmExchangeRate.objects.create(
            firm=firm,
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate_decimal,
            source="manual",
            valid_from=valid_from,
            valid_to=None,
            created_by=request.user,
            note=payload.note,
        )

    # Trigger async recalculation of canonical amounts
    try:
        from crm.tasks import recalculate_canonical_amounts_for_firm
        recalculate_canonical_amounts_for_firm.delay(str(firm.id))
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "create_exchange_rate: could not enqueue canonical recalc for firm %s", firm.id
        )

    return 201, _exchange_rate_out(new_rate)


@router.patch(
    "/{firm_id}/exchange-rates/{rate_id}/",
    auth=django_auth,
    response={200: ExchangeRateOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_exchange_rate(request, firm_id: str, rate_id: str, payload: ExchangeRatePatchIn):
    """Update the note of an exchange rate (note-only patch)."""
    from firms.models import FirmExchangeRate

    try:
        firm, _ = _get_firm_and_check_admin(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Admin or Owner access required."}

    try:
        rate = FirmExchangeRate.objects.select_related("created_by").get(
            id=rate_id, firm=firm
        )
    except FirmExchangeRate.DoesNotExist:
        return 404, {"detail": "Exchange rate not found."}

    if rate.source != "manual":
        return 400, {"detail": "Only manual rates can be edited."}

    if payload.note is not None:
        rate.note = payload.note
        rate.save(update_fields=["note", "updated_at"])

    return 200, _exchange_rate_out(rate)


@router.delete(
    "/{firm_id}/exchange-rates/{rate_id}/",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_exchange_rate(request, firm_id: str, rate_id: str):
    """
    Delete a manual exchange rate.
    After deletion, the system will fall back to ECB rates (if mode=auto).
    """
    from firms.models import FirmExchangeRate

    try:
        firm, _ = _get_firm_and_check_admin(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Admin or Owner access required."}

    try:
        rate = FirmExchangeRate.objects.get(id=rate_id, firm=firm)
    except FirmExchangeRate.DoesNotExist:
        return 404, {"detail": "Exchange rate not found."}

    if rate.source != "manual":
        return 403, {"detail": "Only manual rates can be deleted."}

    rate.delete()
    return 204, None


@router.get(
    "/{firm_id}/exchange-rates/preview/",
    auth=django_auth,
    response={200: ExchangeRatePreviewOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def preview_exchange_rate(request, firm_id: str, from_currency: str, amount: str):
    """
    Preview conversion: { from_currency, amount } → canonical amount.
    Used for live preview in the UI before saving.
    """
    from crm.money import get_rate, to_canonical

    try:
        firm, _ = _get_firm_and_check_admin(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Admin or Owner access required."}

    try:
        amount_decimal = Decimal(amount)
    except Exception:
        return 400, {"detail": "Invalid amount."}

    from_currency = from_currency.upper()[:3]
    canonical, rate_used = to_canonical(amount_decimal, from_currency, firm)

    # Determine rate source for UI display
    rate_source = None
    if rate_used is not None:
        from firms.models import FirmExchangeRate
        firm_rate = FirmExchangeRate.objects.filter(
            firm=firm,
            from_currency=from_currency,
            to_currency=firm.default_currency,
            valid_to__isnull=True,
        ).first()
        rate_source = "manual" if firm_rate else "ecb"

    return 200, {
        "from_currency": from_currency,
        "amount": str(amount_decimal),
        "canonical_amount": str(canonical) if canonical is not None else None,
        "canonical_currency": firm.default_currency,
        "rate_used": str(rate_used) if rate_used is not None else None,
        "rate_source": rate_source,
    }


@router.post("/{firm_id}/branding", auth=django_auth, response={200: FirmOut, 403: ErrorOut, 404: ErrorOut})
def update_branding(request, firm_id: str, payload: FirmBrandingIn = Form(...), logo: UploadedFile = File(None)):
    """Update firm logo and/or primary color. Owner only."""
    membership = require_membership(request, firm_id)
    if membership.role != MembershipRole.OWNER:
        raise PermissionDenied()
    firm = membership.firm
    if logo is not None:
        if firm.logo:
            firm.logo.delete(save=False)
        firm.logo.save(logo.name, logo, save=False)
    if payload.primary_color is not None:
        firm.primary_color = payload.primary_color
    firm.save()
    return _firm_out(firm)


@router.get("/{firm_id}/members", auth=django_auth, response={200: List[MembershipOut], 403: ErrorOut})
def list_members(request, firm_id: str):
    """List all members of a Firm."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found or inactive."}

    if not Membership.objects.filter(user=request.user, firm=firm).exists():
        return 403, {"detail": "You are not a member of this Firm."}

    members = Membership.objects.filter(firm=firm).select_related("user")
    return 200, [
        {
            "id": str(m.id),
            "user_id": str(m.user.id),
            "user_email": m.user.email,
            "user_full_name": m.user.full_name,
            "role": m.role,
            "firm_id": str(m.firm_id),
        }
        for m in members
    ]


@router.post("/{firm_id}/members", auth=django_auth, response={201: MembershipOut, 400: ErrorOut, 402: ErrorOut, 403: ErrorOut})
def invite_member(request, firm_id: str, payload: MemberInviteIn):
    """Invite a user to a Firm (Admin or Owner only)."""
    from users.models import User

    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found or inactive."}

    try:
        caller_membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not caller_membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can invite members."}

    if payload.role == MembershipRole.OWNER:
        return 400, {"detail": "Cannot assign the Owner role via invite."}

    try:
        check_tier_limits(firm)
    except SubscriptionRequired as exc:
        return 402, {"detail": str(exc)}

    try:
        invitee = User.objects.get(email=payload.email)
    except User.DoesNotExist:
        return 400, {"detail": f"No user found with email '{payload.email}'."}

    membership, created = Membership.objects.get_or_create(
        user=invitee,
        firm=firm,
        defaults={"role": payload.role},
    )
    if not created:
        return 400, {"detail": "User is already a member of this Firm."}

    return 201, {
        "id": str(membership.id),
        "user_id": str(invitee.id),
        "user_email": invitee.email,
        "user_full_name": invitee.full_name,
        "role": membership.role,
        "firm_id": str(firm.id),
    }


@router.delete("/{firm_id}/members/{membership_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
def remove_member(request, firm_id: str, membership_id: str):
    """Remove a member from a Firm (Admin/Owner only; cannot remove the Owner)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        caller_membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not caller_membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can remove members."}

    try:
        target = Membership.objects.get(id=membership_id, firm=firm)
    except Membership.DoesNotExist:
        return 404, {"detail": "Membership not found."}

    if target.is_owner:
        return 403, {"detail": "The Owner cannot be removed from the Firm."}

    target.delete()
    return 204, None


@router.patch(
    "/{firm_id}/members/{membership_id}",
    auth=django_auth,
    response={200: MembershipOut, 403: ErrorOut, 404: ErrorOut},
)
def update_member_role(request, firm_id: str, membership_id: str, payload: MemberRoleUpdateIn):
    """Update a member's role (Admin/Owner only; cannot change Owner's role)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        caller_membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not caller_membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can change member roles."}

    try:
        target = Membership.objects.get(id=membership_id, firm=firm)
    except Membership.DoesNotExist:
        return 404, {"detail": "Membership not found."}

    if target.is_owner:
        return 403, {"detail": "The Owner's role cannot be changed."}

    if payload.role == MembershipRole.OWNER:
        return 403, {"detail": "Cannot assign the Owner role."}

    target.role = payload.role
    target.save(update_fields=["role"])
    return 200, {
        "id": str(target.id),
        "user_id": str(target.user_id),
        "user_email": target.user.email,
        "user_full_name": target.user.full_name,
        "role": target.role,
        "firm_id": str(target.firm_id),
    }


# ---------------------------------------------------------------------------
# Email-based invitations (Admin/Owner only)
# ---------------------------------------------------------------------------

@router.get(
    "/{firm_id}/invitations/",
    auth=django_auth,
    response={200: List[InvitationOut], 403: ErrorOut},
    tags=["invitations"],
)
def list_invitations(request, firm_id: str):
    """List all pending and recent invitations for a Firm (Admin/Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found or inactive."}

    try:
        caller_membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not caller_membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can view invitations."}

    invitations = Invitation.objects.filter(firm=firm).select_related("firm", "invited_by").order_by("-id")
    return 200, [_invitation_out(inv) for inv in invitations]




@router.post(
    "/{firm_id}/invitations/",
    auth=django_auth,
    response={202: InvitationOut, 400: ErrorOut, 402: ErrorOut, 403: ErrorOut},
    tags=["invitations"],
)
def create_invitation(request, firm_id: str, payload: MemberInviteIn):
    """
    Create an email invitation for a given address (Admin/Owner only).

    The invited person does not need an existing account — they can create
    one when accepting the invitation.  An email is dispatched asynchronously.
    """
    from users.tasks import send_invitation_email

    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found or inactive."}

    try:
        caller_membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not caller_membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can send invitations."}

    if payload.role == MembershipRole.OWNER:
        return 400, {"detail": "Cannot assign the Owner role via invitation."}

    # Prevent re-inviting someone who is already a member.
    from users.models import User
    existing_user = User.objects.filter(email=payload.email).first()
    if existing_user and Membership.objects.filter(user=existing_user, firm=firm).exists():
        return 400, {"detail": "That user is already a member of this Firm."}

    # Enforce Free-tier member limit before issuing a new invitation.
    # Re-sending an existing (unaccepted) invitation does not consume a new
    # slot, so we only check when no prior invitation exists.
    existing_invitation = Invitation.objects.filter(email=payload.email, firm=firm).first()
    if existing_invitation is None:
        try:
            check_tier_limits(firm)
        except SubscriptionRequired as exc:
            return 402, {"detail": str(exc)}

    # Upsert the Invitation (re-send if one already exists but was not accepted).
    if existing_invitation:
        if existing_invitation.is_accepted:
            return 400, {"detail": "An accepted invitation already exists for that email."}
        # Refresh the expiry so the recipient gets a fresh link.
        from firms.models import _default_expiry
        existing_invitation.expires_at = _default_expiry()
        existing_invitation.role = payload.role
        existing_invitation.invited_by = request.user
        existing_invitation.save(update_fields=["expires_at", "role", "invited_by"])
        invitation = existing_invitation
    else:
        invitation = Invitation.objects.create(
            email=payload.email,
            firm=firm,
            role=payload.role,
            invited_by=request.user,
        )

    # Dispatch the email asynchronously (gracefully degrades if Celery is not running).
    try:
        send_invitation_email.delay(str(invitation.id))
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "create_invitation: Could not enqueue send_invitation_email for %s "
            "(Celery may not be running).",
            invitation.id,
        )

    return 202, _invitation_out(invitation)


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
