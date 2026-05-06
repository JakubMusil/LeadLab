"""
firms.migrations._seed_helpers
================================
Reusable helper functions extracted from the 0004_seed_system_roles data
migration so that:

1. The data migration itself stays thin and easy to read.
2. Tests can call ``create_system_roles_for_firm()`` directly without going
   through the migration runner.
3. The ``post_save`` signal on ``Firm`` (Phase 6) can reuse the same logic.

These helpers work on *real* Django model classes (not the ``apps.get_model``
proxy objects used inside ``RunPython`` callbacks), which makes them
incompatible with the migration runner directly – that is intentional.
"""

from __future__ import annotations

from firms.models import PermissionRecord, Role, RolePermission
from firms.migrations._seed_data import PERMISSION_META, SYSTEM_ROLES, LEGACY_TO_SYSTEM_ROLE


def seed_permission_catalogue() -> None:
    """Ensure all permission codes exist in the PermissionRecord catalogue."""
    for code, (group, description) in PERMISSION_META.items():
        PermissionRecord.objects.get_or_create(
            code=code,
            defaults={"group": group, "description": description},
        )


def create_system_roles_for_firm(firm) -> None:
    """Create (or update) the four system roles for *firm* and assign permissions.

    Idempotent: safe to call multiple times on the same firm.
    """
    perm_map = {p.code: p for p in PermissionRecord.objects.all()}

    for role_code, role_name, role_desc, perm_codes in SYSTEM_ROLES:
        role, _created = Role.objects.get_or_create(
            firm=firm,
            code=role_code,
            defaults={
                "name": role_name,
                "is_system": True,
                "description": role_desc,
            },
        )
        existing_codes = set(
            RolePermission.objects.filter(role=role).values_list("permission_id", flat=True)
        )
        for pcode in perm_codes:
            if pcode not in existing_codes and pcode in perm_map:
                RolePermission.objects.create(role=role, permission=perm_map[pcode])


def link_membership_to_system_role(membership) -> None:
    """Assign the matching system role to *membership* based on its legacy ``role`` field."""
    system_code = LEGACY_TO_SYSTEM_ROLE.get(membership.role)
    if system_code is None:
        return
    try:
        role = Role.objects.get(firm=membership.firm, code=system_code)
    except Role.DoesNotExist:
        return
    if not membership.roles.filter(pk=role.pk).exists():
        membership.roles.add(role)
