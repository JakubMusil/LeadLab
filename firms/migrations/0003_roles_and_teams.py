"""
Phase 2 – schema migration.

Creates the permission catalogue, role, team, and team-membership tables and
extends Membership with the Phase-2 fields (roles M2M, default_scope,
team FK).

A subsequent data migration (0004_seed_system_roles) seeds the catalogue and
creates system roles for every existing Firm.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0002_initial"),
    ]

    operations = [
        # ------------------------------------------------------------------
        # 1. Permission catalogue (static, seeded by the next data migration)
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="PermissionRecord",
            fields=[
                (
                    "code",
                    models.CharField(
                        help_text="Dot-notation permission code, e.g. 'record.edit'.",
                        max_length=60,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "group",
                    models.CharField(
                        db_index=True,
                        help_text="Logical group shown in the permissions UI (e.g. 'Records', 'Billing').",
                        max_length=40,
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "verbose_name": "permission",
                "verbose_name_plural": "permissions",
                "ordering": ["group", "code"],
            },
        ),
        # ------------------------------------------------------------------
        # 2. Role (per-firm)
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="Role",
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
                    "code",
                    models.CharField(
                        help_text="Short identifier, e.g. 'member', 'sales-lead'.  Unique within firm.",
                        max_length=60,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "is_system",
                    models.BooleanField(
                        default=False,
                        help_text="System roles are pre-created per firm and cannot be deleted.",
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "role",
                "verbose_name_plural": "roles",
                "ordering": ["firm", "name"],
            },
        ),
        migrations.AddField(
            model_name="role",
            name="firm",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="roles",
                to="firms.firm",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="role",
            unique_together={("firm", "code")},
        ),
        # ------------------------------------------------------------------
        # 3. RolePermission (M2M through-table: Role ↔ PermissionRecord)
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_permissions",
                        to="firms.role",
                    ),
                ),
                (
                    "permission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_permissions",
                        to="firms.permissionrecord",
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="rolepermission",
            unique_together={("role", "permission")},
        ),
        # Add M2M field on Role pointing to PermissionRecord (uses through table).
        migrations.AddField(
            model_name="role",
            name="permissions",
            field=models.ManyToManyField(
                blank=True,
                related_name="roles",
                through="firms.RolePermission",
                to="firms.permissionrecord",
            ),
        ),
        # ------------------------------------------------------------------
        # 4. Team
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="Team",
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
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(blank=True, max_length=100)),
                (
                    "color",
                    models.CharField(
                        blank=True,
                        default="#6366f1",
                        help_text="Hex colour used in the UI, e.g. '#6366f1'.",
                        max_length=7,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "team",
                "verbose_name_plural": "teams",
                "ordering": ["firm", "name"],
            },
        ),
        migrations.AddField(
            model_name="team",
            name="firm",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="teams",
                to="firms.firm",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="team",
            unique_together={("firm", "slug")},
        ),
        # ------------------------------------------------------------------
        # 5. Membership extensions (new Phase-2 fields)
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name="membership",
            name="default_scope",
            field=models.CharField(
                choices=[
                    ("own", "Own (created by or assigned to me)"),
                    ("team", "Team (my team's records)"),
                    ("category", "Category (specific categories)"),
                    ("all", "All records in workspace"),
                ],
                default="own",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="membership",
            name="team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="primary_memberships",
                to="firms.team",
            ),
        ),
        migrations.AddField(
            model_name="membership",
            name="roles",
            field=models.ManyToManyField(
                blank=True,
                related_name="memberships",
                to="firms.role",
                verbose_name="Roles",
            ),
        ),
        # ------------------------------------------------------------------
        # 6. TeamMembership (M2M through-table: Team ↔ Membership)
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="TeamMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="team_memberships",
                        to="firms.team",
                    ),
                ),
                (
                    "membership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="team_memberships",
                        to="firms.membership",
                    ),
                ),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="teammembership",
            unique_together={("team", "membership")},
        ),
    ]
