# Generated for v2.4 — Plugin Marketplace & Ecosystem

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0005_firm_branding"),
    ]

    operations = [
        migrations.CreateModel(
            name="PluginConfig",
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
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plugin_configs",
                        to="firms.firm",
                    ),
                ),
                (
                    "plugin_name",
                    models.CharField(
                        help_text="Matches LeadLabPlugin.manifest['name'].",
                        max_length=100,
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                (
                    "config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Plugin-specific configuration values.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "plugin config",
                "verbose_name_plural": "plugin configs",
                "ordering": ["plugin_name"],
                "unique_together": {("firm", "plugin_name")},
            },
        ),
    ]
