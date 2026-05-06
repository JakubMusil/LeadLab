"""
v2.2 – Drop the legacy ``role`` CharField from ``Membership``.

All role information is now stored exclusively in the M2M ``roles`` relation
(``Membership ↔ Role``).  The v2.1 migration and ``_sync_legacy_role_to_m2m``
signal ensured that the M2M relation was always kept in sync with the legacy
field, so no data is lost.

The ``MembershipManager.create()`` custom manager (introduced alongside this
migration) transparently handles any remaining callers that pass ``role=`` as
a keyword argument by mapping it to the appropriate system Role via
``_assign_system_role_by_code()``.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0007_fix_member_role_permissions"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="membership",
            name="role",
        ),
    ]
