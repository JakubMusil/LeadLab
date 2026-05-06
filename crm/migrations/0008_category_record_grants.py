"""
Phase 3 – schema migration.

Adds ``CategoryGrant`` and ``RecordGrant`` tables for per-resource access
control (ACL).  Both tables use (principal_type, principal_id) to identify
either a User or a Team as the grantee, allowing additive positive grants
at the category or individual record level.

Indexes are added on (category/record, principal_type, principal_id) to
support the fast ACL lookups performed in the query-scoping layer (Phase 4).
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0007_add_created_by_assigned_to_customer_proposal"),
        ("firms", "0005_permission_audit_log"),
    ]

    operations = [
        # ----------------------------------------------------------------
        # CategoryGrant
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="CategoryGrant",
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
                    "principal_type",
                    models.CharField(
                        choices=[("user", "User"), ("team", "Team")],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                (
                    "principal_id",
                    models.UUIDField(db_index=True),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("view", "View"),
                            ("edit", "Edit"),
                            ("manage", "Manage"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "granted_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When set, the grant is automatically revoked after this timestamp.",
                        null=True,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grants",
                        to="crm.category",
                    ),
                ),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Membership of the user who created this grant.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="category_grants_given",
                        to="firms.membership",
                    ),
                ),
            ],
            options={
                "verbose_name": "category grant",
                "verbose_name_plural": "category grants",
                "ordering": ["-granted_at"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="categorygrant",
            unique_together={("category", "principal_type", "principal_id")},
        ),
        migrations.AddIndex(
            model_name="categorygrant",
            index=models.Index(
                fields=["category", "principal_type", "principal_id"],
                name="crm_catgrant_cat_princ_idx",
            ),
        ),
        # ----------------------------------------------------------------
        # RecordGrant
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name="RecordGrant",
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
                    "principal_type",
                    models.CharField(
                        choices=[("user", "User"), ("team", "Team")],
                        db_index=True,
                        max_length=10,
                    ),
                ),
                (
                    "principal_id",
                    models.UUIDField(db_index=True),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("view", "View"),
                            ("edit", "Edit"),
                            ("manage", "Manage"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "granted_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When set, the grant is automatically revoked after this timestamp.",
                        null=True,
                    ),
                ),
                (
                    "record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grants",
                        to="crm.pipelinerecord",
                    ),
                ),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Membership of the user who created this grant.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="record_grants_given",
                        to="firms.membership",
                    ),
                ),
            ],
            options={
                "verbose_name": "record grant",
                "verbose_name_plural": "record grants",
                "ordering": ["-granted_at"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="recordgrant",
            unique_together={("record", "principal_type", "principal_id")},
        ),
        migrations.AddIndex(
            model_name="recordgrant",
            index=models.Index(
                fields=["record", "principal_type", "principal_id"],
                name="crm_recgrant_rec_princ_idx",
            ),
        ),
    ]
