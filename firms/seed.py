"""
firms.seed
==========
Helper functions for seeding firm-level default data (system roles, permission
catalogue).  These are the canonical runtime variants of the logic first
introduced in data migrations 0004_seed_system_roles.

Unlike the migration helpers in ``firms.migrations._seed_helpers``, this
module imports Django models directly and is safe to use in application code
(signals, management commands, tests).
"""

from __future__ import annotations


def create_system_roles_for_firm(firm) -> None:
    """Create (or update) the four system roles for *firm* and assign permissions.

    Idempotent: safe to call multiple times on the same firm.  Delegates to
    the shared implementation in ``firms.migrations._seed_helpers`` to keep a
    single source of truth for the system role definitions.
    """
    from firms.migrations._seed_helpers import (  # noqa: PLC0415
        create_system_roles_for_firm as _create,
    )
    _create(firm)
