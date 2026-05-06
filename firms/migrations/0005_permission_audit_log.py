"""
Phase 3 – schema migration.

Adds the ``PermissionAuditLog`` table which records every permission-related
change (Role / Membership / CategoryGrant / RecordGrant create / update / delete).
The table is append-only by convention – no update or delete operations are
performed at the application level.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0004_seed_system_roles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PermissionAuditLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("role.created", "Role created"),
                            ("role.updated", "Role updated"),
                            ("role.deleted", "Role deleted"),
                            ("membership.created", "Membership created"),
                            ("membership.updated", "Membership updated"),
                            ("membership.deleted", "Membership deleted"),
                            ("category_grant.created", "CategoryGrant created"),
                            ("category_grant.deleted", "CategoryGrant deleted"),
                            ("record_grant.created", "RecordGrant created"),
                            ("record_grant.deleted", "RecordGrant deleted"),
                        ],
                        db_index=True,
                        max_length=40,
                    ),
                ),
                (
                    "target_type",
                    models.CharField(
                        db_index=True,
                        help_text="Type tag of the affected object (e.g. 'role', 'membership').",
                        max_length=40,
                    ),
                ),
                (
                    "target_id",
                    models.CharField(
                        db_index=True,
                        help_text="String representation of the affected object's PK.",
                        max_length=40,
                    ),
                ),
                (
                    "payload",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Snapshot of changed fields or relevant context.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        help_text="The user who performed the action. Null for system/migration actions.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="permission_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "firm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="permission_audit_logs",
                        to="firms.firm",
                    ),
                ),
            ],
            options={
                "verbose_name": "permission audit log",
                "verbose_name_plural": "permission audit logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="permissionauditlog",
            index=models.Index(
                fields=["firm", "-created_at"],
                name="firms_permi_firm_id_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="permissionauditlog",
            index=models.Index(
                fields=["actor", "-created_at"],
                name="firms_permi_actor_id_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="permissionauditlog",
            index=models.Index(
                fields=["target_type", "target_id"],
                name="firms_permi_tgt_type_id_idx",
            ),
        ),
    ]
