"""
firms.migrations._seed_data
============================
Static data shared between the 0004_seed_system_roles migration RunPython
callback and the ``_seed_helpers`` module (which works on real model classes).

Keeping the raw data here means there is a single authoritative source that
both the migration and the test helpers use.
"""

# ---------------------------------------------------------------------------
# Permission catalogue
# ---------------------------------------------------------------------------

# code → (group, description)
PERMISSION_META: dict[str, tuple[str, str]] = {
    "record.view":         ("Records",             "View pipeline records"),
    "record.create":       ("Records",             "Create pipeline records"),
    "record.edit":         ("Records",             "Edit pipeline records"),
    "record.delete":       ("Records",             "Delete pipeline records"),
    "category.view":       ("Categories",          "View pipeline categories"),
    "category.manage":     ("Categories",          "Manage pipeline categories"),
    "team.manage":         ("Teams",               "Manage teams and their members"),
    "role.manage":         ("Roles",               "Create, edit and assign roles"),
    "billing.manage":      ("Billing & Ownership", "Manage subscription and billing"),
    "firm.delete":         ("Billing & Ownership", "Delete the workspace"),
    "firm.transfer":       ("Billing & Ownership", "Transfer workspace ownership"),
    "integrations.manage": ("Integrations",        "Configure integrations and plugins"),
    "report.view":         ("Reports",             "View reports and analytics"),
    "activity.create":     ("Streamline",          "Create activities in the streamline"),
    "streamline.view_all": ("Streamline",          "View all team streamline activities"),
    "proposal.create":     ("Proposals",           "Create proposals on records"),
}

# ---------------------------------------------------------------------------
# System role definitions
# ---------------------------------------------------------------------------

# Each entry: (code, name, description, permission_codes_set)
SYSTEM_ROLES: list[tuple[str, str, str, set[str]]] = [
    (
        "owner",
        "Owner",
        "Full access. Cannot be removed. Only owner can delete the workspace or transfer ownership.",
        set(PERMISSION_META.keys()),
    ),
    (
        "admin",
        "Admin",
        "Manages members, roles, categories, and integrations. Cannot manage billing or delete the workspace.",
        {
            "record.view", "record.create", "record.edit", "record.delete",
            "category.view", "category.manage",
            "team.manage", "role.manage",
            "integrations.manage",
            "report.view",
            "activity.create", "streamline.view_all",
            "proposal.create",
        },
    ),
    (
        "member",
        "Member",
        "Standard workspace member (formerly Worker). Default scope is own records.",
        {
            "record.view", "record.create", "record.edit",
            "category.view",
            "activity.create",
            "proposal.create",
            "report.view",
        },
    ),
    (
        "guest",
        "Guest",
        "Read-only access, e.g. for external auditors. Limited to viewing records in granted categories.",
        {
            "record.view",
            "category.view",
        },
    ),
]

# ---------------------------------------------------------------------------
# Legacy role → system role mapping
# ---------------------------------------------------------------------------

LEGACY_TO_SYSTEM_ROLE: dict[str, str] = {
    "owner": "owner",
    "admin": "admin",
    "worker": "member",
}
