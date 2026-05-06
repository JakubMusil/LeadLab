"""
Phase 2 – data migration.

Seeds the PermissionRecord catalogue from the Permission enum defined in
``firms.permissions``, then creates four system roles per Firm (Owner, Admin,
Member, Guest) and assigns the correct permissions to each.

Finally every existing Membership gains the corresponding system role in the
``roles`` M2M so that Phase 4 query-scoping can use the new model without
losing any access for existing users.

This migration is:
  * Forward-only (RunPython with no reverse).
  * Idempotent – safe to run on a DB with existing data or on a clean DB.
  * Non-destructive – existing ``Membership.role`` (legacy) is preserved.
"""

from django.db import migrations

from firms.migrations._seed_data import (
    LEGACY_TO_SYSTEM_ROLE,
    PERMISSION_META,
    SYSTEM_ROLES,
)


def seed_forward(apps, schema_editor):
    """Seed permissions, create system roles and link existing memberships."""
    PermissionRecord = apps.get_model("firms", "PermissionRecord")
    Role = apps.get_model("firms", "Role")
    RolePermission = apps.get_model("firms", "RolePermission")
    Firm = apps.get_model("firms", "Firm")
    Membership = apps.get_model("firms", "Membership")

    # 1. Seed PermissionRecord catalogue (idempotent via get_or_create)
    for code, (group, description) in PERMISSION_META.items():
        PermissionRecord.objects.get_or_create(
            code=code,
            defaults={"group": group, "description": description},
        )

    perm_map = {p.code: p for p in PermissionRecord.objects.all()}

    # 2. For each Firm ensure four system roles exist with correct permissions.
    for firm in Firm.objects.all():
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

    # 3. Link existing Memberships to their corresponding system role.
    for membership in Membership.objects.all():
        system_code = LEGACY_TO_SYSTEM_ROLE.get(membership.role)
        if system_code is None:
            continue
        try:
            role = Role.objects.get(firm=membership.firm, code=system_code)
        except Role.DoesNotExist:
            continue
        if not membership.roles.filter(pk=role.pk).exists():
            membership.roles.add(role)


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0003_roles_and_teams"),
    ]

    operations = [
        migrations.RunPython(seed_forward, migrations.RunPython.noop),
    ]
