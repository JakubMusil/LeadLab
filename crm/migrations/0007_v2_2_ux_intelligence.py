# Generated for v2.2 — UX Intelligence & Personalisation

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0006_push_subscription"),
        ("firms", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------
        # DashboardLayout
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="DashboardLayout",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "layout",
                    models.JSONField(
                        default=list,
                        help_text="Ordered list of widget config objects.",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "firm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_layouts",
                        to="firms.firm",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_layouts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "dashboard layout",
                "verbose_name_plural": "dashboard layouts",
                "unique_together": {("user", "firm")},
            },
        ),
        # ------------------------------------------------------------------
        # LeadScoringRule
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="LeadScoringRule",
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
                    "firm",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="firms.firm",
                    ),
                ),
                (
                    "field",
                    models.CharField(
                        help_text="Lead attribute to test.",
                        max_length=50,
                    ),
                ),
                (
                    "operand",
                    models.JSONField(
                        help_text="Comparison value for the field.",
                    ),
                ),
                (
                    "score_delta",
                    models.IntegerField(
                        help_text="Points contributed when this rule matches.",
                    ),
                ),
            ],
            options={
                "verbose_name": "lead scoring rule",
                "verbose_name_plural": "lead scoring rules",
                "ordering": ["field"],
            },
        ),
        # ------------------------------------------------------------------
        # SavedView
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="SavedView",
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
                (
                    "entity",
                    models.CharField(
                        choices=[("leads", "Leads"), ("customers", "Customers")],
                        max_length=20,
                    ),
                ),
                (
                    "filters",
                    models.JSONField(
                        default=dict,
                        help_text='Serialised filter state, e.g. {"status": "new"}.',
                    ),
                ),
                ("sort_by", models.CharField(blank=True, max_length=50)),
                ("sort_dir", models.CharField(default="asc", max_length=4)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "firm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_views",
                        to="firms.firm",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_views",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "saved view",
                "verbose_name_plural": "saved views",
                "ordering": ["entity", "name"],
                "unique_together": {("user", "firm", "entity", "name")},
            },
        ),
    ]
