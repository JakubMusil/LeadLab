"""
Calendar / Task unification — backfill child Tasks for existing
``meeting_scheduled`` Activities so they show up in the calendar /
agenda just like newly created ones.

Idempotent: any Activity that already has ``task_id`` set is skipped.
For each remaining ``meeting_scheduled`` Activity, a Task is created
(kind=meeting, auto_close_on_expiry=True) using the metadata fields
written by ``MeetingScheduledTool``.  The Activity is then linked to
the new Task via ``Activity.task``.

Forward direction is the only one that does meaningful work — the
reverse direction is a no-op because we cannot tell which tasks were
auto-created versus manually created without an extra marker.
"""
from django.db import migrations


def backfill_meeting_scheduled_tasks(apps, schema_editor):
    Activity = apps.get_model("crm", "Activity")
    Task = apps.get_model("crm", "Task")

    qs = (
        Activity.objects
        .filter(type="meeting_scheduled", task__isnull=True)
        .order_by("created_at")
    )

    for activity in qs.iterator():
        # Resolve the firm from whichever entity the activity is attached to.
        # Activities are guaranteed to have at least one of these populated.
        entity = (
            activity.lead
            or activity.realization
            or activity.management
            or activity.customer
            or activity.proposal
        )
        if entity is None or getattr(entity, "firm_id", None) is None:
            continue

        metadata = activity.metadata or {}
        start_at = metadata.get("start_at")
        # We can only construct a meaningful calendar Task when the
        # original invite carried a start time.  Activities without
        # ``start_at`` are left as legacy log-only entries.
        if not start_at:
            continue

        # Parse ISO-8601 strings; ``apps.get_model`` returns historical
        # models so we cannot rely on Task model methods, but the field
        # is just a DateTimeField that accepts aware datetimes.
        from datetime import datetime

        def _parse(value):
            if not value or not isinstance(value, str):
                return None
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None

        start_dt = _parse(start_at)
        end_dt = _parse(metadata.get("end_at"))
        if start_dt is None:
            continue

        attendees_raw = metadata.get("attendees") or []
        attendees = [str(a) for a in attendees_raw if a is not None]

        title_bits = ["Meeting"]
        try:
            entity_title = (
                getattr(entity, "title", None)
                or " ".join(
                    str(x) for x in [
                        getattr(entity, "first_name", ""),
                        getattr(entity, "last_name", ""),
                    ] if x
                ).strip()
                or getattr(entity, "company_name", "")
                or getattr(entity, "email", "")
            )
        except Exception:
            entity_title = ""
        if entity_title:
            title_bits.append(str(entity_title))
        title = " — ".join(b for b in title_bits if b)[:255]

        task = Task.objects.create(
            firm_id=entity.firm_id,
            kind="meeting",
            title=title,
            description=activity.content_text or "",
            status="todo",
            priority="medium",
            due_date=start_dt,
            due_date_end=end_dt,
            location=str(metadata.get("location") or "")[:255],
            attendees=attendees,
            auto_close_on_expiry=True,
            assigned_to_id=activity.user_id,
            created_by_id=activity.user_id,
            lead_id=activity.lead_id,
            realization_id=activity.realization_id,
            management_id=activity.management_id,
            customer_id=activity.customer_id,
            proposal_id=activity.proposal_id,
            metadata={
                "source_activity_id": str(activity.id),
                "source_activity_type": activity.type,
                "ics_url": metadata.get("ics_url") or "",
                "provider_event_id": metadata.get("provider_event_id") or "",
                "backfilled": True,
            },
        )
        activity.task = task
        activity.save(update_fields=["task"])


def noop_reverse(apps, schema_editor):
    """
    Reverse is intentionally a no-op.

    We only set ``Activity.task`` for activities we created Tasks for in
    the forward direction, but we have no reliable way to undo that
    without potentially clobbering manual links a user may have made
    after the migration ran.  Leaving the data in place is safe — the
    reverse migration only undoes any *schema* changes, of which this
    migration has none.
    """
    return


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0042_task_attendees_task_auto_close_on_expiry_task_kind_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_meeting_scheduled_tasks, noop_reverse),
    ]
