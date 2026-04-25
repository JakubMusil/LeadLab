"""
Django Ninja API router – Firms & Memberships

All write endpoints enforce:
  1. Valid session authentication.
  2. Membership in the target Firm (via TenantMiddleware + require_membership).
  3. Role-based access (Owners can do everything; Workers are read-only for team mgmt).
"""
from typing import List, Optional

from django.db import transaction
from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import (
    AuthenticationRequired,
    FirmNotFound,
    MembershipRole,
    PermissionDenied,
    require_membership,
)
from firms.models import Firm, Membership

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


class FirmIn(Schema):
    name: str


class MembershipOut(Schema):
    id: str
    user_email: str
    role: str
    firm_id: str


class InviteIn(Schema):
    email: str
    role: str = MembershipRole.WORKER


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Firm CRUD
# ---------------------------------------------------------------------------

@router.get("/", auth=django_auth, response=List[FirmOut])
def list_firms(request):
    """Return all Firms the authenticated user is a member of."""
    memberships = Membership.objects.filter(
        user=request.user
    ).select_related("firm")
    return [
        {
            "id": str(m.firm.id),
            "name": m.firm.name,
            "slug": m.firm.slug,
            "subscription_tier": m.firm.subscription_tier,
            "subscription_active": m.firm.subscription_active,
            "is_active": m.firm.is_active,
        }
        for m in memberships
    ]


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
    return 201, {
        "id": str(firm.id),
        "name": firm.name,
        "slug": firm.slug,
        "subscription_tier": firm.subscription_tier,
        "subscription_active": firm.subscription_active,
        "is_active": firm.is_active,
    }


@router.get("/{firm_id}", auth=django_auth, response={200: FirmOut, 403: ErrorOut, 404: ErrorOut})
def get_firm(request, firm_id: str):
    """Return details for a specific Firm (membership required)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    if not Membership.objects.filter(user=request.user, firm=firm).exists():
        return 403, {"detail": "You are not a member of this Firm."}

    return 200, {
        "id": str(firm.id),
        "name": firm.name,
        "slug": firm.slug,
        "subscription_tier": firm.subscription_tier,
        "subscription_active": firm.subscription_active,
        "is_active": firm.is_active,
    }


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


# ---------------------------------------------------------------------------
# Team / Membership management
# ---------------------------------------------------------------------------

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
            "user_email": m.user.email,
            "role": m.role,
            "firm_id": str(m.firm_id),
        }
        for m in members
    ]


@router.post("/{firm_id}/members", auth=django_auth, response={201: MembershipOut, 400: ErrorOut, 403: ErrorOut})
def invite_member(request, firm_id: str, payload: InviteIn):
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
        "user_email": invitee.email,
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
