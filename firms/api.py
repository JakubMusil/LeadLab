"""
Django Ninja API router – Firms & Memberships

All write endpoints enforce:
  1. Valid session authentication.
  2. Membership in the target Firm (via TenantMiddleware + require_membership).
  3. Role-based access (Owners can do everything; Workers are read-only for team mgmt).
"""
import csv
import datetime
import io
from decimal import Decimal
from typing import List, Optional

from django.db import transaction
from django.http import HttpResponse
from ninja import File, Form, Router, Schema, UploadedFile
from ninja.security import django_auth

from firms.auth import (
    AuthenticationRequired,
    FirmNotFound,
    InvitationRole,
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
    expires_at: Optional[str] = None  # ISO-8601 datetime; null clears the expiry


class MembershipOut(Schema):
    id: str
    user_id: str
    user_email: str
    user_full_name: str
    role: str
    firm_id: str
    roles: List[str] = []
    permissions: List[str] = []
    expires_at: Optional[str] = None  # ISO-8601 or null
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    team_color: Optional[str] = None


class MemberInviteIn(Schema):
    email: str
    role: str = InvitationRole.MEMBER
    # Phase 6 – extended invite settings
    role_codes: List[str] = []
    default_scope: str = "own"
    team_id: Optional[str] = None


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


def _membership_out(m: Membership) -> dict:
    """Serialise a Membership to the MembershipOut schema dict."""
    from crm.permissions import resolve_effective_permissions
    try:
        role_codes = list(m.roles.values_list("code", flat=True))
    except Exception:
        role_codes = []
    try:
        permissions = sorted(resolve_effective_permissions(m))
    except Exception:
        permissions = []
    return {
        "id": str(m.id),
        "user_id": str(m.user_id),
        "user_email": m.user.email,
        "user_full_name": m.user.full_name,
        "role": m.primary_role,
        "firm_id": str(m.firm_id),
        "roles": role_codes,
        "permissions": permissions,
        "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        "team_id": str(m.team_id) if m.team_id else None,
        "team_name": m.team.name if m.team_id and m.team else None,
        "team_color": m.team.color if m.team_id and m.team else None,
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
    from crm.management.commands.seed_pipeline_categories import seed_for_firm
    with transaction.atomic():
        firm = Firm.objects.create(name=payload.name)
        Membership.objects.create(
            user=request.user,
            firm=firm,
            role=InvitationRole.OWNER,
        )
        seed_for_firm(firm)
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


@router.get(
    "/{firm_id}/exchange-rates/export.csv",
    auth=django_auth,
)
def export_exchange_rates_csv(request, firm_id: str, include_history: bool = False):
    """
    Export exchange rates for a firm as a CSV file.
    Pass ?include_history=true to include closed (historical) rates.
    Access: Admin or Owner only.
    """
    from firms.models import FirmExchangeRate

    try:
        firm, _ = _get_firm_and_check_admin(request, firm_id)
    except FirmNotFound:
        return HttpResponse("Firm not found.", status=404)
    except PermissionDenied:
        return HttpResponse("Admin or Owner access required.", status=403)

    qs = FirmExchangeRate.objects.filter(firm=firm).select_related("created_by").order_by("-valid_from")
    if not include_history:
        qs = qs.filter(valid_to__isnull=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "from_currency", "to_currency", "rate", "source",
        "valid_from", "valid_to", "note", "created_by", "created_at",
    ])
    for rate in qs:
        writer.writerow([
            rate.from_currency,
            rate.to_currency,
            str(rate.rate),
            rate.source,
            rate.valid_from.isoformat(),
            rate.valid_to.isoformat() if rate.valid_to else "",
            rate.note,
            rate.created_by.email if rate.created_by else "",
            rate.created_at.isoformat(),
        ])

    filename = f"exchange_rates_{firm.slug}.csv"
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@router.post("/{firm_id}/branding", auth=django_auth, response={200: FirmOut, 403: ErrorOut, 404: ErrorOut})
def update_branding(request, firm_id: str, payload: FirmBrandingIn = Form(...), logo: UploadedFile = File(None)):
    """Update firm logo and/or primary color. Owner only."""
    membership = require_membership(request, firm_id)
    if not membership.is_owner:
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
def list_members(request, firm_id: str, q: Optional[str] = None):
    """List all members of a Firm. Supports optional full-text search via ?q=."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found or inactive."}

    if not Membership.objects.filter(user=request.user, firm=firm).exists():
        return 403, {"detail": "You are not a member of this Firm."}

    members = Membership.objects.filter(firm=firm).select_related("user", "team").prefetch_related("roles")
    if q:
        from django.db import models as _dj_models  # noqa: PLC0415
        members = members.filter(
            _dj_models.Q(user__email__icontains=q)
            | _dj_models.Q(user__first_name__icontains=q)
            | _dj_models.Q(user__last_name__icontains=q)
        )
    return 200, [_membership_out(m) for m in members]


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

    if payload.role == InvitationRole.OWNER:
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
        defaults={"role": payload.role},  # handled transparently by MembershipManager
    )
    if not created:
        return 400, {"detail": "User is already a member of this Firm."}

    return 201, _membership_out(membership)


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
    response={200: MembershipOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_member_role(request, firm_id: str, membership_id: str, payload: MemberRoleUpdateIn):
    """Update a member's role and/or expiry (Admin/Owner only; cannot change Owner's role)."""
    from django.utils.dateparse import parse_datetime
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

    if payload.role == InvitationRole.OWNER:
        return 403, {"detail": "Cannot assign the Owner role."}

    target._assign_system_role_by_code(payload.role)

    # Handle expires_at update (explicit null clears expiry)
    if "expires_at" in payload.dict(exclude_unset=False):
        if payload.expires_at is None:
            target.expires_at = None
        else:
            parsed = parse_datetime(payload.expires_at)
            if parsed is None:
                return 400, {"detail": "Invalid expires_at format; use ISO-8601."}
            target.expires_at = parsed
        target.save(update_fields=["expires_at"])

    target.refresh_from_db()
    return 200, _membership_out(target)


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

    if payload.role == InvitationRole.OWNER:
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
        existing_invitation.invited_role_codes = payload.role_codes
        existing_invitation.invited_default_scope = payload.default_scope
        existing_invitation.invited_team_id = payload.team_id or None
        existing_invitation.save(update_fields=[
            "expires_at", "role", "invited_by",
            "invited_role_codes", "invited_default_scope", "invited_team_id",
        ])
        invitation = existing_invitation
    else:
        invitation = Invitation.objects.create(
            email=payload.email,
            firm=firm,
            role=payload.role,
            invited_by=request.user,
            invited_role_codes=payload.role_codes,
            invited_default_scope=payload.default_scope,
            invited_team_id=payload.team_id or None,
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


# ---------------------------------------------------------------------------
# Audit Log (Phase 6)
# ---------------------------------------------------------------------------

class AuditLogOut(Schema):
    id: str
    action: str
    target_type: str
    target_id: str
    actor_email: Optional[str]
    payload: dict
    created_at: str


@router.get(
    "/{firm_id}/audit-log",
    auth=django_auth,
    response={200: List[AuditLogOut], 403: ErrorOut, 404: ErrorOut},
    tags=["audit"],
)
def list_audit_log(
    request,
    firm_id: str,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """
    Return a paginated audit log of permission-related changes for the firm.

    Requires ``role.manage`` permission (Admin or Owner).

    Query params:
        action      – filter by action code, e.g. 'role.created'
        target_type – filter by target type, e.g. 'role', 'membership'
        page        – page number (1-indexed)
        page_size   – entries per page (max 200)
    """
    from firms.models import PermissionAuditLog

    try:
        firm, _ = _get_firm_and_check_admin(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Admin or Owner access required."}

    qs = PermissionAuditLog.objects.filter(firm=firm).select_related("actor")
    if action:
        qs = qs.filter(action=action)
    if target_type:
        qs = qs.filter(target_type=target_type)

    page_size = min(max(1, page_size), 200)
    offset = (max(1, page) - 1) * page_size
    entries = qs.order_by("-created_at")[offset: offset + page_size]

    return 200, [
        {
            "id": str(e.id),
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "actor_email": e.actor.email if e.actor else None,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


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


# ---------------------------------------------------------------------------
# Ownership Transfer
# ---------------------------------------------------------------------------


class TransferOwnershipIn(Schema):
    to_user_id: str  # UUID of the target Membership (user who will become new owner)


class OwnershipTransferOut(Schema):
    id: str
    firm_id: str
    from_user_email: str
    to_user_email: str
    expires_at: str
    is_pending: bool
    is_confirmed: bool


@router.post(
    "/{firm_id}/transfer-ownership",
    auth=django_auth,
    response={200: OwnershipTransferOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
    tags=["firms"],
)
def initiate_ownership_transfer(request, firm_id: str, payload: TransferOwnershipIn):
    """
    Initiate an ownership transfer for the given Firm.

    Only the current Owner can call this endpoint.  The target user must
    already be a member of the Firm.  An email with a confirmation link is
    sent to the new owner; they have 48 hours to confirm.

    Any existing pending (unconfirmed) transfer for this Firm is automatically
    cancelled before the new one is created.
    """
    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    from firms.models import OwnershipTransfer

    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not membership.is_owner:
        return 403, {"detail": "Only the Owner can initiate an ownership transfer."}

    # Resolve target membership
    try:
        target_membership = Membership.objects.select_related("user").get(
            id=payload.to_user_id, firm=firm
        )
    except Membership.DoesNotExist:
        return 404, {"detail": "Target membership not found in this Firm."}

    if target_membership.user == request.user:
        return 400, {"detail": "Cannot transfer ownership to yourself."}

    with transaction.atomic():
        # Cancel any existing pending transfers for this firm
        OwnershipTransfer.objects.filter(
            firm=firm, confirmed_at__isnull=True
        ).delete()

        transfer = OwnershipTransfer.objects.create(
            firm=firm,
            from_user=request.user,
            to_user=target_membership.user,
        )

        # Write audit log entry
        from firms.models import PermissionAuditLog
        try:
            PermissionAuditLog.objects.create(
                firm=firm,
                actor=request.user,
                action="ownership.transfer_initiated",
                target_type="ownership_transfer",
                target_id=str(transfer.id),
                payload={
                    "to_user_email": target_membership.user.email,
                    "expires_at": transfer.expires_at.isoformat(),
                },
            )
        except Exception:
            pass  # Never block the transfer creation due to audit log failure

    # Send confirmation email to the new owner
    confirm_url = (
        f"{getattr(django_settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')}"
        f"/app/ownership-transfer/{firm.id}/{transfer.token}/confirm"
    )
    try:
        from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@leadlab.app")
        send_mail(
            subject=f"[LeadLab] Confirm ownership transfer – {firm.name}",
            message=(
                f"Hi,\n\n"
                f"{request.user.email} has invited you to become the new Owner of "
                f"the workspace \"{firm.name}\" on LeadLab.\n\n"
                f"To accept, click the link below (valid for 48 hours):\n"
                f"{confirm_url}\n\n"
                f"If you did not expect this, you can safely ignore this email.\n\n"
                f"— The LeadLab team"
            ),
            from_email=from_email,
            recipient_list=[target_membership.user.email],
            fail_silently=True,
        )
    except Exception:
        pass  # Email failure must not roll back the transfer record

    return 200, {
        "id": str(transfer.id),
        "firm_id": str(firm.id),
        "from_user_email": request.user.email,
        "to_user_email": target_membership.user.email,
        "expires_at": transfer.expires_at.isoformat(),
        "is_pending": transfer.is_pending,
        "is_confirmed": transfer.is_confirmed,
    }


@router.post(
    "/{firm_id}/transfer-ownership/{token}/confirm",
    auth=django_auth,
    response={200: OwnershipTransferOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
    tags=["firms"],
)
def confirm_ownership_transfer(request, firm_id: str, token: str):
    """
    Confirm a pending ownership transfer.

    Only the *designated new owner* (the ``to_user`` on the transfer record)
    can call this endpoint.  On success:
        - The current owner's system role is demoted to *admin*.
        - The new owner's system role is elevated to *owner*.
        - ``confirmed_at`` is set on the transfer.
        - A ``PermissionAuditLog`` entry is written.
    """
    from django.utils import timezone as tz
    from firms.models import OwnershipTransfer, PermissionAuditLog

    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        transfer = OwnershipTransfer.objects.select_related(
            "from_user", "to_user"
        ).get(token=token, firm=firm, confirmed_at__isnull=True)
    except OwnershipTransfer.DoesNotExist:
        return 404, {"detail": "Transfer not found or already confirmed."}

    if transfer.is_expired:
        return 400, {"detail": "This transfer confirmation link has expired."}

    if transfer.to_user != request.user:
        return 403, {
            "detail": "Only the designated new owner can confirm this transfer."
        }

    with transaction.atomic():
        # Demote current owner → admin
        try:
            old_owner_membership = Membership.objects.get(
                user=transfer.from_user, firm=firm
            )
            old_owner_membership._assign_system_role_by_code("admin")
        except Membership.DoesNotExist:
            pass  # Former owner no longer a member – proceed anyway

        # Elevate new owner → owner
        new_owner_membership, _ = Membership.objects.get_or_create(
            user=transfer.to_user, firm=firm
        )
        new_owner_membership._assign_system_role_by_code("owner")

        # Mark transfer as confirmed
        transfer.confirmed_at = tz.now()
        transfer.save(update_fields=["confirmed_at"])

        # Audit log
        try:
            PermissionAuditLog.objects.create(
                firm=firm,
                actor=request.user,
                action="ownership.transfer_confirmed",
                target_type="ownership_transfer",
                target_id=str(transfer.id),
                payload={
                    "from_user_email": transfer.from_user.email,
                    "to_user_email": transfer.to_user.email,
                },
            )
        except Exception:
            pass

    return 200, {
        "id": str(transfer.id),
        "firm_id": str(firm.id),
        "from_user_email": transfer.from_user.email,
        "to_user_email": transfer.to_user.email,
        "expires_at": transfer.expires_at.isoformat(),
        "is_pending": transfer.is_pending,
        "is_confirmed": transfer.is_confirmed,
    }


@router.delete(
    "/{firm_id}/transfer-ownership",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
    tags=["firms"],
)
def cancel_ownership_transfer(request, firm_id: str):
    """
    Cancel any pending ownership transfer for the given Firm (Owner only).
    """
    from firms.models import OwnershipTransfer, PermissionAuditLog

    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not membership.is_owner:
        return 403, {"detail": "Only the Owner can cancel an ownership transfer."}

    deleted, _ = OwnershipTransfer.objects.filter(
        firm=firm, confirmed_at__isnull=True
    ).delete()

    if deleted:
        try:
            PermissionAuditLog.objects.create(
                firm=firm,
                actor=request.user,
                action="ownership.transfer_cancelled",
                target_type="ownership_transfer",
                target_id=str(firm.id),
                payload={},
            )
        except Exception:
            pass

    return 204, None


@router.get(
    "/{firm_id}/transfer-ownership",
    auth=django_auth,
    response={200: Optional[OwnershipTransferOut], 403: ErrorOut, 404: ErrorOut},
    tags=["firms"],
)
def get_pending_ownership_transfer(request, firm_id: str):
    """
    Return the pending ownership transfer for the given Firm, if any.

    Accessible to all members of the Firm.
    """
    from firms.models import OwnershipTransfer

    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    if not Membership.objects.filter(user=request.user, firm=firm).exists():
        return 403, {"detail": "You are not a member of this Firm."}

    try:
        transfer = OwnershipTransfer.objects.select_related(
            "from_user", "to_user"
        ).filter(firm=firm, confirmed_at__isnull=True).latest("created_at")
    except OwnershipTransfer.DoesNotExist:
        return 200, None

    if transfer.is_expired:
        return 200, None

    return 200, {
        "id": str(transfer.id),
        "firm_id": str(firm.id),
        "from_user_email": transfer.from_user.email,
        "to_user_email": transfer.to_user.email,
        "expires_at": transfer.expires_at.isoformat(),
        "is_pending": transfer.is_pending,
        "is_confirmed": transfer.is_confirmed,
    }
