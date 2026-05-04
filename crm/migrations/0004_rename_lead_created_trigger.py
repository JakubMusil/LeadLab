"""
Migration: rename the 'lead_created' automation trigger value to 'record_created'
to match the Lead → PipelineRecord rename.

This migration:
1. Updates the choices list on AutomationRule.trigger (model-level metadata).
2. Runs a data migration to update existing rows from 'lead_created' → 'record_created'.
"""
import django.db.models.deletion
from django.db import migrations, models


def rename_lead_created_to_record_created(apps, schema_editor):
    AutomationRule = apps.get_model("crm", "AutomationRule")
    AutomationRule.objects.filter(trigger="lead_created").update(trigger="record_created")


def reverse_rename(apps, schema_editor):
    AutomationRule = apps.get_model("crm", "AutomationRule")
    AutomationRule.objects.filter(trigger="record_created").update(trigger="lead_created")


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0003_backfill_meeting_scheduled_tasks"),
    ]

    operations = [
        migrations.AlterField(
            model_name="automationrule",
            name="trigger",
            field=models.CharField(
                choices=[
                    ("record_created", "Record Created"),
                    ("lead_status_change", "Lead Status Changed"),
                    ("task_overdue", "Task Overdue"),
                    ("task_created", "Task Created"),
                    ("task_completed", "Task Completed"),
                    ("proposal_sent", "Proposal Sent"),
                    ("proposal_accepted", "Proposal Accepted"),
                    ("lead_inactive", "Lead Inactive (N days)"),
                    ("webhook_received", "Custom Webhook Received"),
                    ("contact_created", "Contact Created"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
        migrations.RunPython(
            rename_lead_created_to_record_created,
            reverse_rename,
        ),
    ]
