"""
Django Ninja API router – Role & Permission management (Phase 6)

Endpoints:
    GET    /firms/{firm_id}/permission-catalogue        — static list of all permission codes
    GET    /firms/{firm_id}/roles                       — list roles for the firm
    POST   /firms/{firm_id}/roles                       — create a custom role
    PATCH  /firms/{firm_id}/roles/{role_id}             — update a custom role
    DELETE /firms/{firm_id}/roles/{role_id}             — delete a custom role
    PUT    /firms/{firm_id}/roles/{role_id}/permissions — replace the full permission set for a role
"""
from typing import List, Optional

from django.db import transaction
from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import (
    AuthenticationRequired,
    FirmNotFound,
    PermissionDenied,
    require_permission,
)
from firms.models import Firm, Membership, MembershipRole, PermissionRecord, Role, RolePermission
from firms.permissions import Permission

router = Router(tags=["roles"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PermissionCatalogueOut(Schema):
    code: str
    group: str
    description: str


class RoleOut(Schema):
    id: str
    code: str
    name: str
    is_system: bool
    description: str
    permissions: List[str]


class RoleCreateIn(Schema):
    code: str
    name: str
    description: str = ""
    permissions: List[str] = []


class RoleUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None


class RolePermissionsIn(Schema):
    permissions: List[str]


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _role_out(role: Role) -> dict:
    return {
        "id": str(role.id),
        "code": role.code,
        "name": role.name,
        "is_system": role.is_system,
        "description": role.description,
        "permissions": list(role.permissions.values_list("code", flat=True).order_by("code")),
    }


def _get_firm_and_membership(request, firm_id: str):
    """Return (firm, membership) or raise appropriate exception."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        raise FirmNotFound("Firm not found.")
    membership = getattr(request, "membership", None)
    if membership is None or membership.firm_id != firm.pk:
        raise PermissionDenied("You are not a member of this Firm.")
    return firm, membership


def _actor_permission_codes(membership: Membership) -> set[str]:
    """Return the set of permission codes the actor can grant to others.

    Used for privilege escalation prevention: an actor cannot assign
    permissions they do not themselves hold.  Owners hold all permissions.
    For non-owners the set is derived from their DB-backed Role assignments.
    """
    if membership.role == MembershipRole.OWNER:
        return {p.code for p in PermissionRecord.objects.all()}
    codes: set[str] = set()
    for role in membership.roles.prefetch_related("permissions").all():
        codes.update(role.permissions.values_list("code", flat=True))
    return codes


# ---------------------------------------------------------------------------
# Permission catalogue
# ---------------------------------------------------------------------------

@router.get(
    "/{firm_id}/permission-catalogue",
    auth=django_auth,
    response={200: List[PermissionCatalogueOut], 403: ErrorOut, 404: ErrorOut},
)
def list_permission_catalogue(request, firm_id: str):
    """Return the static catalogue of all permission codes (read-only reference)."""
    try:
        _get_firm_and_membership(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Access denied."}

    perms = PermissionRecord.objects.all().order_by("group", "code")
    return 200, [
        {"code": p.code, "group": p.group, "description": p.description}
        for p in perms
    ]


# ---------------------------------------------------------------------------
# Role CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/{firm_id}/roles",
    auth=django_auth,
    response={200: List[RoleOut], 403: ErrorOut, 404: ErrorOut},
)
def list_roles(request, firm_id: str):
    """List all roles (system and custom) for a firm. Any member may read."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Access denied."}

    roles = Role.objects.filter(firm=firm).prefetch_related("permissions").order_by("name")
    return 200, [_role_out(r) for r in roles]


@router.post(
    "/{firm_id}/roles",
    auth=django_auth,
    response={201: RoleOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_role(request, firm_id: str, payload: RoleCreateIn):
    """Create a custom role for the firm. Requires ``role.manage`` permission."""
    try:
        firm, membership = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.ROLE_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "role.manage permission required."}

    # Prevent creation of roles with permissions the actor does not have.
    actor_perms = _actor_permission_codes(membership)
    forbidden = [p for p in payload.permissions if p not in actor_perms]
    if forbidden:
        return 403, {"detail": f"Cannot grant permissions you do not hold: {forbidden}"}

    if Role.objects.filter(firm=firm, code=payload.code).exists():
        return 400, {"detail": f"Role with code '{payload.code}' already exists in this firm."}

    # Disallow creating roles with billing/firm management permissions for non-owners.
    protected = {Permission.BILLING_MANAGE.value, Permission.FIRM_DELETE.value, Permission.FIRM_TRANSFER.value}
    if membership.role != MembershipRole.OWNER:
        bad = [p for p in payload.permissions if p in protected]
        if bad:
            return 403, {"detail": f"Only the Owner can assign these permissions: {bad}"}

    with transaction.atomic():
        role = Role.objects.create(
            firm=firm,
            code=payload.code,
            name=payload.name,
            is_system=False,
            description=payload.description,
        )
        if payload.permissions:
            perm_objs = PermissionRecord.objects.filter(code__in=payload.permissions)
            role.permissions.set(perm_objs)

    return 201, _role_out(role)


@router.patch(
    "/{firm_id}/roles/{role_id}",
    auth=django_auth,
    response={200: RoleOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_role(request, firm_id: str, role_id: str, payload: RoleUpdateIn):
    """Update a custom role's name or description. System roles cannot be modified."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.ROLE_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "role.manage permission required."}

    try:
        role = Role.objects.get(id=role_id, firm=firm)
    except Role.DoesNotExist:
        return 404, {"detail": "Role not found."}

    if role.is_system:
        return 403, {"detail": "System roles cannot be modified."}

    update_fields = []
    if payload.name is not None:
        role.name = payload.name
        update_fields.append("name")
    if payload.description is not None:
        role.description = payload.description
        update_fields.append("description")
    if update_fields:
        role.save(update_fields=update_fields)

    return 200, _role_out(role)


@router.delete(
    "/{firm_id}/roles/{role_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_role(request, firm_id: str, role_id: str):
    """Delete a custom role. System roles cannot be deleted."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.ROLE_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "role.manage permission required."}

    try:
        role = Role.objects.get(id=role_id, firm=firm)
    except Role.DoesNotExist:
        return 404, {"detail": "Role not found."}

    if role.is_system:
        return 403, {"detail": "System roles cannot be deleted."}

    role.delete()
    return 204, None


@router.put(
    "/{firm_id}/roles/{role_id}/permissions",
    auth=django_auth,
    response={200: RoleOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def set_role_permissions(request, firm_id: str, role_id: str, payload: RolePermissionsIn):
    """Replace the full permission set for a role.

    Guards:
    - Requires ``role.manage``.
    - Actor cannot assign permissions they do not themselves hold (privilege escalation prevention).
    - Cannot set ``billing.manage``, ``firm.delete``, ``firm.transfer`` unless Owner.
    """
    try:
        firm, membership = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.ROLE_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "role.manage permission required."}

    try:
        role = Role.objects.get(id=role_id, firm=firm)
    except Role.DoesNotExist:
        return 404, {"detail": "Role not found."}

    if role.is_system:
        return 403, {"detail": "System role permissions cannot be modified via API."}

    # Privilege escalation check
    actor_perms = _actor_permission_codes(membership)
    forbidden = [p for p in payload.permissions if p not in actor_perms]
    if forbidden:
        return 403, {"detail": f"Cannot grant permissions you do not hold: {forbidden}"}

    protected = {Permission.BILLING_MANAGE.value, Permission.FIRM_DELETE.value, Permission.FIRM_TRANSFER.value}
    if membership.role != MembershipRole.OWNER:
        bad = [p for p in payload.permissions if p in protected]
        if bad:
            return 403, {"detail": f"Only the Owner can assign these permissions: {bad}"}

    # Validate all codes exist
    existing_codes = set(PermissionRecord.objects.filter(code__in=payload.permissions).values_list("code", flat=True))
    unknown = [p for p in payload.permissions if p not in existing_codes]
    if unknown:
        return 400, {"detail": f"Unknown permission codes: {unknown}"}

    with transaction.atomic():
        perm_objs = PermissionRecord.objects.filter(code__in=payload.permissions)
        role.permissions.set(perm_objs)

    return 200, _role_out(role)
