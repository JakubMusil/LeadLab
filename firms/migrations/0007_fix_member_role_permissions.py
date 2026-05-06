"""
Phase 8 – Remove record.delete from the Member system role.

The Member role (formerly Worker) should not have delete permissions;
only Admins and Owners can delete records.  This migration corrects the
seed data for all existing firms.
"""

from django.db import migrations


def remove_delete_from_member_role(apps, schema_editor):
    Role = apps.get_model("firms", "Role")
    RolePermission = apps.get_model("firms", "RolePermission")

    member_roles = Role.objects.filter(code="member", is_system=True)
    for role in member_roles:
        RolePermission.objects.filter(role=role, permission_id="record.delete").delete()


def add_delete_to_member_role(apps, schema_editor):
    """Reverse: restore record.delete to all Member system roles."""
    Role = apps.get_model("firms", "Role")
    RolePermission = apps.get_model("firms", "RolePermission")
    PermissionRecord = apps.get_model("firms", "PermissionRecord")

    member_roles = Role.objects.filter(code="member", is_system=True)
    try:
        perm = PermissionRecord.objects.get(code="record.delete")
    except PermissionRecord.DoesNotExist:
        return

    for role in member_roles:
        RolePermission.objects.get_or_create(role=role, permission=perm)


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0006_invitation_extended_fields"),
    ]

    operations = [
        migrations.RunPython(
            remove_delete_from_member_role,
            reverse_code=add_delete_to_member_role,
        ),
    ]
