import threading

from django.apps import AppConfig

# ---------------------------------------------------------------------------
# Thread-local user context — set by API endpoints before model saves so that
# auto-generated entity_change Activity records can capture the acting user.
# ---------------------------------------------------------------------------

_local = threading.local()


def set_current_user(user) -> None:
    """Store *user* in thread-local storage for the duration of the request."""
    _local.user = user


def clear_current_user() -> None:
    """Remove the thread-local user (called after the save completes)."""
    _local.user = None


def get_current_user():
    """Return the user stored for the current thread, or ``None``."""
    return getattr(_local, "user", None)


# ---------------------------------------------------------------------------
# Tracked fields per model — (field_attr, human label) pairs.
# Use *_id suffix for FK columns to avoid DB lookups on comparison.
# ---------------------------------------------------------------------------

_LEAD_FIELDS = [
    ("title", "Title"),
    ("description", "Description"),
    ("status", "Status"),
    ("source", "Source"),
    ("assigned_to_id", "Assigned To"),
    ("value", "Value"),
    ("currency", "Currency"),
]

_CUSTOMER_FIELDS = [
    ("first_name", "First Name"),
    ("last_name", "Last Name"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("company_name", "Company"),
    ("website", "Website"),
    ("address_city", "City"),
    ("address_country", "Country"),
    ("ico", "IČO"),
    ("dic", "DIČ"),
]

_REALIZATION_FIELDS = [
    ("title", "Title"),
    ("description", "Description"),
    ("status", "Status"),
    ("assigned_to_id", "Assigned To"),
    ("start_date", "Start Date"),
    ("end_date", "End Date"),
]

_MANAGEMENT_FIELDS = [
    ("title", "Title"),
    ("notes", "Notes"),
    ("type", "Type"),
    ("status", "Status"),
    ("assigned_to_id", "Assigned To"),
    ("expires_at", "Expires At"),
]

_PROPOSAL_FIELDS = [
    ("title", "Title"),
    ("status", "Status"),
    ("notes", "Notes"),
    ("expiry_date", "Expiry Date"),
    ("currency", "Currency"),
]


def _normalize(value) -> str:
    """Convert any field value to a stable string for comparison and storage.

    Returns a clean string representation suitable for display.
    ``None`` is stored as an empty string; ``Decimal`` values drop trailing
    zeros; all other types use their natural ``str()`` representation.
    """
    from decimal import Decimal
    if value is None:
        return ""
    if isinstance(value, Decimal):
        # Remove unnecessary trailing zeros: Decimal('50000.00') → '50000'
        normalized = value.normalize()
        # If the result uses scientific notation (e.g. '5E+4'), convert back
        try:
            return format(normalized, 'f')
        except Exception:
            return str(value)
    return str(value)


def _make_pre_save(tracked_fields):
    """Return a pre_save signal receiver that snapshots the old field values."""
    def _handler(sender, instance, **kwargs):
        if instance.pk is None:
            return  # new record — nothing to diff
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._pre_save_snapshot = {
                field: getattr(old, field, None)
                for field, _ in tracked_fields
            }
        except sender.DoesNotExist:
            pass
    return _handler


def _make_post_save(tracked_fields, entity_kwarg):
    """Return a post_save signal receiver that logs Activity records for changed fields."""
    def _handler(sender, instance, created, **kwargs):
        if created:
            return
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        if not snapshot:
            return

        # Determine firm — all tracked models have a firm FK
        firm = getattr(instance, "firm", None)
        if firm is None:
            return

        # Capture the acting user from thread-local context (set by API endpoints)
        from crm.apps import get_current_user
        acting_user = get_current_user()

        from crm.models import Activity, ActivityType
        # Lazy import to avoid circular dependency with crm.api at module load.
        from crm.api import _activity_out
        from crm.events import broadcast_event

        created_activities: list[Activity] = []
        for field, label in tracked_fields:
            old_val = snapshot.get(field)
            new_val = getattr(instance, field, None)
            if _normalize(old_val) == _normalize(new_val):
                continue
            # Use ``create()`` instead of ``bulk_create()`` so that:
            #   - the row is INSERTed immediately with its PK populated
            #     (so we can hand a fully-formed payload to the WebSocket);
            #   - any ``post_save`` listeners on Activity itself can fire;
            #   - we can broadcast each new activity individually below.
            #
            # The number of tracked fields per entity is small (≤ 6 today),
            # so the per-row INSERT cost vs. ``bulk_create`` is negligible.
            activity = Activity.objects.create(
                **{entity_kwarg: instance},
                user=acting_user,
                type=ActivityType.ENTITY_CHANGE,
                content_text="",
                metadata={
                    "field": field,
                    "field_label": label,
                    "old_value": _normalize(old_val),
                    "new_value": _normalize(new_val),
                },
            )
            created_activities.append(activity)

        # Broadcast each new entity_change activity over WebSocket so any
        # open ActivityTimeline rerenders the row instantly — without this,
        # the user had to hit refresh to see field-change log entries.
        # ``broadcast_event`` itself uses ``transaction.on_commit`` for the
        # channel-layer send, so this is safe inside a request transaction.
        for activity in created_activities:
            broadcast_event(
                firm=firm,
                event="activity.created",
                payload=_activity_out(activity),
            )
    return _handler


class CrmConfig(AppConfig):
    name = 'crm'

    def ready(self) -> None:
        from crm.streamline.registry import register_tool
        from crm.streamline.tools import BUILTIN_TOOLS

        for tool in BUILTIN_TOOLS:
            register_tool(tool)

        # -------------------------------------------------------------------
        # Register entity-change signals after models are fully loaded
        # -------------------------------------------------------------------
        from django.db.models.signals import pre_save, post_save
        from crm.models import Lead, Customer, Realization, Management, Proposal

        _entities = [
            (Lead, _LEAD_FIELDS, "lead"),
            (Customer, _CUSTOMER_FIELDS, "customer"),
            (Realization, _REALIZATION_FIELDS, "realization"),
            (Management, _MANAGEMENT_FIELDS, "management"),
            (Proposal, _PROPOSAL_FIELDS, "proposal"),
        ]

        for model, tracked, kwarg in _entities:
            pre_save.connect(
                _make_pre_save(tracked),
                sender=model,
                weak=False,
                dispatch_uid=f"crm_entity_change_pre_{model.__name__.lower()}",
            )
            post_save.connect(
                _make_post_save(tracked, kwarg),
                sender=model,
                weak=False,
                dispatch_uid=f"crm_entity_change_post_{model.__name__.lower()}",
            )
