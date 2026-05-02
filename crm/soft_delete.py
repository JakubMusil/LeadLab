"""
Soft-delete infrastructure for LeadLab CRM models.

Usage
-----
1. Inherit ``SoftDeleteMixin`` in your model alongside ``TenantModel``::

       class MyModel(SoftDeleteMixin, TenantModel):
           ...

2. Call ``perform_soft_delete(instance, user)`` in your API endpoint instead
   of ``instance.delete()``.

3. Use ``MyModel.objects.all()`` for normal queries (only non-deleted rows) or
   ``MyModel.all_objects.all()`` when you need to include soft-deleted rows
   (e.g. in Django admin, audit endpoints, or the purge task).
"""

import datetime
import logging

from django.conf import settings
from django.db import models
from django.utils import timezone as tz

logger = logging.getLogger(__name__)

# Default number of days before a soft-deleted record is hard-deleted.
_PURGE_DAYS_DEFAULT = getattr(settings, "SOFT_DELETE_PURGE_DAYS", 30)


# ---------------------------------------------------------------------------
# Managers
# ---------------------------------------------------------------------------

class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that adds a convenience ``delete_soft`` method."""

    def delete_soft(self, user, purge_days: int = _PURGE_DAYS_DEFAULT):
        """Soft-delete all records in the queryset at once."""
        now = tz.now()
        purge_after = now + datetime.timedelta(days=purge_days)
        return self.update(
            is_deleted=True,
            deleted_at=now,
            deleted_by=user,
            purge_after=purge_after,
        )


class SoftDeleteManager(models.Manager):
    """
    Default manager — returns only records where ``is_deleted=False``.

    Attach as ``objects`` on the model.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """
    Unfiltered manager — returns ALL records including soft-deleted ones.

    Attach as ``all_objects`` on the model (for admin / audit / purge use).
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class SoftDeleteMixin(models.Model):
    """
    Abstract mixin that adds soft-delete fields and helper methods to a model.

    Fields added:
    - ``is_deleted``  — boolean flag, indexed.
    - ``deleted_at``  — timestamp of soft-delete.
    - ``deleted_by``  — FK to AUTH_USER_MODEL (nullable).
    - ``purge_after`` — scheduled hard-delete timestamp (nullable for records
                        that should never be purged automatically).
    """

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    purge_after = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled timestamp for hard-delete. Null means never purge automatically.",
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    # ------------------------------------------------------------------
    # Instance helpers
    # ------------------------------------------------------------------

    def soft_delete(self, user, purge_days: int = _PURGE_DAYS_DEFAULT) -> None:
        """
        Mark this instance as soft-deleted.

        Sets ``is_deleted``, ``deleted_at``, ``deleted_by``, and
        ``purge_after`` then calls ``save(update_fields=...)``.
        """
        self.is_deleted = True
        self.deleted_at = tz.now()
        self.deleted_by = user
        self.purge_after = self.deleted_at + datetime.timedelta(days=purge_days)
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "purge_after"])

    @property
    def deleted_by_name(self) -> str:
        """Return display name of the user who deleted this record, or empty string."""
        if self.deleted_by_id is None:
            return ""
        user = self.deleted_by
        if user is None:
            return ""
        full = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        return full or getattr(user, "email", "") or str(user)


# ---------------------------------------------------------------------------
# Helper for API endpoints
# ---------------------------------------------------------------------------

def perform_soft_delete(instance: SoftDeleteMixin, user, purge_days: int = _PURGE_DAYS_DEFAULT) -> None:
    """
    Convenience wrapper for use in API endpoint handlers.

    Example::

        @router.delete("/customers/{id}", ...)
        def delete_customer(request, id: str):
            customer = get_object_or_404(Customer, id=id, firm=request.firm)
            perform_soft_delete(customer, request.user)
            return 204, None
    """
    instance.soft_delete(user, purge_days=purge_days)
