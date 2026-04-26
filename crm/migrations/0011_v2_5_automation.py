# Generated for v2.5 — Workflow Automation

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0010_rename_crm_emailseq_firm_trigger_idx_crm_emailse_firm_id_e2507d_idx_and_more"),
        ("firms", "0006_plugin_config"),
    ]

    operations = [
        # AutomationRule
        migrations.CreateModel(
            name="AutomationRule",
            fields=[
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
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "trigger",
                    models.CharField(
                        choices=[
                            ("lead_created", "Lead Created"),
                            ("lead_status_change", "Lead Status Changed"),
                            ("task_overdue", "Task Overdue"),
                            ("proposal_sent", "Proposal Sent"),
                            ("proposal_accepted", "Proposal Accepted"),
                            ("lead_inactive", "Lead Inactive (N days)"),
                            ("webhook_received", "Custom Webhook Received"),
                        ],
                        db_index=True,
                        max_length=50,
                    ),
                ),
                (
                    "trigger_config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Trigger-specific configuration.",
                    ),
                ),
                (
                    "conditions",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="List of {field, operator, value} condition objects.",
                    ),
                ),
                (
                    "actions",
                    models.JSONField(
                        default=list,
                        help_text="Ordered list of action objects.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "automation rule",
                "verbose_name_plural": "automation rules",
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="automationrule",
            index=models.Index(
                fields=["firm", "trigger", "is_active"],
                name="crm_automat_firm_id_trigger_active_idx",
            ),
        ),
        # AutomationRun
        migrations.CreateModel(
            name="AutomationRun",
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
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="crm.automationrule",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("failure", "Failure"),
                            ("skipped", "Skipped"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("triggered_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "context",
                    models.JSONField(
                        default=dict,
                        help_text="Serialised event context that fired this run.",
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "automation run",
                "verbose_name_plural": "automation runs",
                "ordering": ["-triggered_at"],
            },
        ),
        migrations.AddIndex(
            model_name="automationrun",
            index=models.Index(
                fields=["rule", "-triggered_at"],
                name="crm_automat_rule_id_triggered_idx",
            ),
        ),
    ]
