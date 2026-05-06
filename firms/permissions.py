"""
firms.permissions
=================
Permission constants, scope definitions, and the ``can()`` / ``has_min_role()``
helpers used by ``firms.auth`` and future phases of the permission system.

Phase 1 – Foundation
--------------------
* ``Permission`` enum  – all action × resource codes.
* ``Scope`` enum       – OWN / TEAM / CATEGORY / ALL.
* ``LEGACY_ROLE_PERMISSIONS`` – maps the three legacy roles to their
  corresponding permission sets so the rest of the system has a single
  authoritative source of truth.
* ``can(membership, permission)`` – evaluates a permission check against
  the legacy map (Phase 4 will add DB-backed resolution behind the
  ``PERMISSIONS_V2_ENABLED`` feature flag).
* ``has_min_role(membership, min_role)`` – backward-compat wrapper so
  ``firms.auth.require_membership`` can delegate to ``can()`` internally
  while keeping its public ``min_role=`` signature unchanged.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from firms.models import Membership

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission codes
# ---------------------------------------------------------------------------


class Permission(str, Enum):
    # Record-level actions
    RECORD_VIEW = "record.view"
    RECORD_CREATE = "record.create"
    RECORD_EDIT = "record.edit"
    RECORD_DELETE = "record.delete"

    # Category-level actions
    CATEGORY_VIEW = "category.view"
    CATEGORY_MANAGE = "category.manage"

    # Team management
    TEAM_MANAGE = "team.manage"

    # Role / permission management
    ROLE_MANAGE = "role.manage"

    # Billing & firm ownership
    BILLING_MANAGE = "billing.manage"
    FIRM_DELETE = "firm.delete"
    FIRM_TRANSFER = "firm.transfer"

    # Integrations & plugins
    INTEGRATIONS_MANAGE = "integrations.manage"

    # Reports
    REPORT_VIEW = "report.view"

    # Activity / streamline
    ACTIVITY_CREATE = "activity.create"
    STREAMLINE_VIEW_ALL = "streamline.view_all"

    # Proposals
    PROPOSAL_CREATE = "proposal.create"


# ---------------------------------------------------------------------------
# Scope definitions
# ---------------------------------------------------------------------------


class Scope(str, Enum):
    OWN = "own"
    TEAM = "team"
    CATEGORY = "category"
    ALL = "all"


# ---------------------------------------------------------------------------
# Legacy role → permission mapping
#
# This is the single authoritative source that translates today's flat
# OWNER / ADMIN / WORKER roles into the granular Permission set.  All
# runtime enforcement in Phase 1 is derived from this mapping.
# ---------------------------------------------------------------------------

_WORKER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.RECORD_VIEW,
        Permission.RECORD_CREATE,
        Permission.RECORD_EDIT,
        Permission.CATEGORY_VIEW,
        Permission.ACTIVITY_CREATE,
        Permission.PROPOSAL_CREATE,
        Permission.REPORT_VIEW,
    }
)

_ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        *_WORKER_PERMISSIONS,
        Permission.RECORD_DELETE,
        Permission.CATEGORY_MANAGE,
        Permission.TEAM_MANAGE,
        Permission.ROLE_MANAGE,
        Permission.INTEGRATIONS_MANAGE,
        Permission.STREAMLINE_VIEW_ALL,
    }
)

_OWNER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        *_ADMIN_PERMISSIONS,
        Permission.BILLING_MANAGE,
        Permission.FIRM_DELETE,
        Permission.FIRM_TRANSFER,
    }
)

# Public mapping – importable by other modules for introspection / UI.
LEGACY_ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": _OWNER_PERMISSIONS,
    "admin": _ADMIN_PERMISSIONS,
    "member": _WORKER_PERMISSIONS,
    "guest": frozenset({Permission.RECORD_VIEW}),
}

# Sentinel permission that is the *minimum* distinguishing capability for each
# legacy role level.  Used by ``has_min_role`` to express legacy "min_role"
# checks through ``can()`` so there is one code-path for authorization.
_MIN_ROLE_SENTINEL: dict[str, Permission] = {
    "member": Permission.RECORD_VIEW,    # every valid member can view records
    "admin": Permission.ROLE_MANAGE,     # only admin+ can manage roles
    "owner": Permission.FIRM_DELETE,     # only owner can delete the firm
}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def can(
    membership: "Membership",
    permission: Permission,
    scope: Scope | None = None,  # noqa: ARG001 – used in Phase 4+
) -> bool:
    """Return ``True`` if *membership* holds *permission*.

    Phase 1 delegates entirely to the legacy role map.  The ``scope``
    parameter is accepted for forward-compatibility but is not evaluated
    until ``PERMISSIONS_V2_ENABLED`` is active (Phase 4).
    """
    # Unknown membership role → deny and log a warning so misconfigurations
    # surface quickly (returning an empty frozenset is the secure default but
    # could be hard to diagnose without a log message).
    role_perms = LEGACY_ROLE_PERMISSIONS.get(membership.primary_role)
    if role_perms is None:
        logger.warning(
            "can(): unrecognised membership role %r for membership %s – denying permission %r",
            membership.primary_role,
            membership.pk,
            permission,
        )
        return False
    return permission in role_perms


def has_min_role(membership: "Membership", min_role: str) -> bool:
    """Return ``True`` if *membership* holds at least the permissions
    associated with *min_role* (MEMBER < ADMIN < OWNER).

    This is a backward-compatibility bridge that allows ``require_membership``
    in ``firms.auth`` to delegate its role-rank check to ``can()``, keeping
    both code-paths in sync when the permission map changes.
    """
    sentinel = _MIN_ROLE_SENTINEL.get(min_role)
    if sentinel is None:
        # Unknown min_role value – fall back to deny.
        return False
    return can(membership, sentinel)
