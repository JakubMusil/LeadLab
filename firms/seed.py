"""
firms.seed
==========
Helper functions for seeding firm-level default data (system roles, permission
catalogue).  These are the canonical runtime variants of the logic first
introduced in data migrations 0004_seed_system_roles.

Unlike the migration helpers in ``firms.migrations._seed_helpers``, this
module imports from ``firms.role_seeds``, which is a standalone utility
module safe to use in application code (signals, management commands, tests).
"""

from __future__ import annotations

from firms.role_seeds import create_system_roles_for_firm  # noqa: F401 – re-exported

__all__ = ["create_system_roles_for_firm"]
