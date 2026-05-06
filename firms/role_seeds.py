"""
firms.role_seeds
================
Standalone utility module for seeding firm-level system roles and the
permission catalogue.

Keeping this logic outside ``firms.migrations`` allows both the data
migrations *and* runtime code (signals, management commands, tests) to import
it without coupling to migration internals.

Usage::

    from firms.role_seeds import create_system_roles_for_firm, SYSTEM_ROLES
    create_system_roles_for_firm(firm_instance)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Permission catalogue metadata
# ---------------------------------------------------------------------------

#: Mapping of permission code → (group, description).
PERMISSION_META: dict[str, tuple[str, str]] = {
    "record.view":         ("Records", "View pipeline records"),
    "record.create":       ("Records", "Create pipeline records"),
    "record.edit":         ("Records", "Edit pipeline records"),
    "record.delete":       ("Records", "Delete pipeline records"),
    "category.view":       ("Categories", "View pipeline categories"),
    "category.manage":     ("Categories", "Manage pipeline categories (create/edit/delete)"),
    "team.manage":         ("Teams", "Create and manage teams"),
    "role.manage":         ("Roles", "Create and manage roles"),
    "billing.manage":      ("Billing", "Manage subscription and billing"),
    "firm.delete":         ("Firm", "Delete the workspace"),
    "firm.transfer":       ("Firm", "Transfer workspace ownership"),
    "integrations.manage": ("Integrations", "Manage integrations and plugins"),
    "report.view":         ("Reports", "View reports and analytics"),
    "activity.create":     ("Streamline", "Create activities in the streamline"),
    "streamline.view_all": ("Streamline", "View all streamline activities including restricted ones"),
    "proposal.create":     ("Proposals", "Create and manage proposals"),
}

#: System role definitions: (code, name, description, [permission_codes]).
SYSTEM_ROLES: list[tuple[str, str, str, list[str]]] = [
    (
        "owner",
        "Owner",
        "Full access to all workspace features. Cannot be deleted.",
        list(PERMISSION_META.keys()),
    ),
    (
        "admin",
        "Admin",
        "Manages members, roles, categories, and integrations.",
        [
            "record.view", "record.create", "record.edit", "record.delete",
            "category.view", "category.manage",
            "team.manage", "role.manage",
            "integrations.manage",
            "report.view",
            "activity.create",
            "streamline.view_all",
            "proposal.create",
        ],
    ),
    (
        "member",
        "Member",
        "Standard CRM user. Default scope is own records.",
        [
            "record.view", "record.create", "record.edit",
            "category.view",
            "report.view",
            "activity.create",
            "proposal.create",
        ],
    ),
    (
        "guest",
        "Guest",
        "Read-only access to permitted records and categories.",
        [
            "record.view",
            "category.view",
        ],
    ),
]

#: Maps legacy ``Membership.role`` values to the equivalent system role code.
LEGACY_TO_SYSTEM_ROLE: dict[str, str] = {
    "owner": "owner",
    "admin": "admin",
    "worker": "member",
}


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def seed_permission_catalogue() -> None:
    """Ensure all permission codes exist in the ``PermissionRecord`` catalogue.

    Idempotent – safe to call multiple times.
    """
    from firms.models import PermissionRecord  # local import to avoid circular at module level
    for code, (group, description) in PERMISSION_META.items():
        PermissionRecord.objects.get_or_create(
            code=code,
            defaults={"group": group, "description": description},
        )


def create_system_roles_for_firm(firm) -> None:
    """Create (or update) the four system roles for *firm* and assign permissions.

    Idempotent: safe to call multiple times on the same firm.

    This function is used:
    - By data migration ``0004_seed_system_roles`` for existing firms.
    - By the ``Firm`` ``post_save`` signal for new firms created at runtime.
    - Directly in tests to bootstrap a firm with system roles.
    """
    from firms.models import PermissionRecord, Role, RolePermission  # local imports
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
        new_rps = [
            RolePermission(role=role, permission=perm_map[pcode])
            for pcode in perm_codes
            if pcode not in existing_codes and pcode in perm_map
        ]
        if new_rps:
            RolePermission.objects.bulk_create(new_rps, ignore_conflicts=True)


def link_membership_to_system_role(membership) -> None:
    """Assign the matching system role to *membership* based on its *primary_role*.

    Uses ``primary_role`` (derived from M2M ``roles``) rather than the removed
    legacy ``role`` CharField.  Falls back to ``'member'`` (standard member
    access) rather than ``'guest'`` (read-only) because this function is called
    in contexts where a meaningful default assignment is expected – e.g. after
    accepting an invitation without explicit role codes.
    """
    from firms.models import Role  # local import
    role_code = membership.primary_role
    # Override the 'guest' fallback from primary_role (which is returned when no
    # M2M roles are assigned) with 'member' – the sensible default for a new member.
    if role_code == "guest":
        role_code = "member"
    system_code = LEGACY_TO_SYSTEM_ROLE.get(role_code, role_code)
    try:
        role = Role.objects.get(firm=membership.firm, code=system_code)
    except Role.DoesNotExist:
        return
    if not membership.roles.filter(pk=role.pk).exists():
        membership.roles.add(role)
