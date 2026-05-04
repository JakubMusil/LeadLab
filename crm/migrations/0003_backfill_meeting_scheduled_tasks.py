"""
Data migration: backfill Task records for legacy MEETING_SCHEDULED Activities
that were created before the sitewide timer / auto-expire feature introduced
the Task ↔ Activity link.

For each MEETING_SCHEDULED Activity without a linked task whose metadata
contains a ``start_at`` timestamp, we create a corresponding Task of
``kind='meeting'`` and link it back to the Activity.
"""
from django.db import migrations
from django.utils.dateparse import parse_datetime


def backfill_meeting_scheduled_tasks(apps, schema_editor):
    Activity = apps.get_model("crm", "Activity")
    Task = apps.get_model("crm", "Task")

    candidates = (
        Activity.objects
        .filter(type="meeting_scheduled", task__isnull=True)
        .select_related("record", "record__firm", "customer", "customer__firm")
    )

    for activity in candidates:
        metadata = activity.metadata or {}
        start_at_raw = metadata.get("start_at")
        if not start_at_raw:
            continue

        start_dt = parse_datetime(str(start_at_raw))
        if start_dt is None:
            continue

        # Determine the firm from the linked entity
        firm = None
        if activity.record_id and activity.record:
            firm = activity.record.firm
        elif activity.customer_id and activity.customer:
            firm = activity.customer.firm
        if firm is None:
            continue

        task = Task.objects.create(
            firm=firm,
            record=activity.record,
            customer=activity.customer,
            title=metadata.get("title", "Meeting"),
            kind="meeting",
            due_date=start_dt,
            location=metadata.get("location", ""),
            attendees=metadata.get("attendees", []),
            auto_close_on_expiry=True,
            metadata={"backfilled": True},
        )
        activity.task = task
        activity.save(update_fields=["task"])


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0002_category_categoryfield_checkpoint_pipelinerecord_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_meeting_scheduled_tasks,
            migrations.RunPython.noop,
        ),
    ]
