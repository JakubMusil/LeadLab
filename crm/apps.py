from django.apps import AppConfig


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
    """Convert any field value to a stable string for comparison.

    Includes the type name to distinguish between falsy values of different
    types (e.g. 0 vs False vs None vs "").
    """
    if value is None:
        return ""
    # For numeric types include the type so 0 != False != ""
    return f"{type(value).__name__}:{value}"


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

        from crm.models import Activity, ActivityType
        activities_to_create = []
        for field, label in tracked_fields:
            old_val = snapshot.get(field)
            new_val = getattr(instance, field, None)
            if _normalize(old_val) == _normalize(new_val):
                continue
            activities_to_create.append(
                Activity(
                    **{entity_kwarg: instance},
                    user=None,  # system-generated; no request context in signals
                    type=ActivityType.ENTITY_CHANGE,
                    content_text="",
                    metadata={
                        "field": field,
                        "field_label": label,
                        "old_value": _normalize(old_val),
                        "new_value": _normalize(new_val),
                    },
                )
            )
        if activities_to_create:
            Activity.objects.bulk_create(activities_to_create)
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
