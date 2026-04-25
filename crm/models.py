import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from firms.models import Firm


# ---------------------------------------------------------------------------
# Base tenant-scoped model
# ---------------------------------------------------------------------------

class TenantModel(models.Model):
    """
    Abstract base that every tenant-scoped model should inherit from.
    Provides the ``firm`` FK and a custom manager that accepts an optional
    ``firm`` argument to return pre-filtered querysets.
    """

    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    PROPOSAL = "proposal", "Proposal"
    NEGOTIATION = "negotiation", "Negotiation"
    WON = "won", "Won"
    LOST = "lost", "Lost"
    CANCELED = "canceled", "Canceled"


class LeadSource(models.TextChoices):
    WEB = "web", "Web"
    EMAIL = "email", "Email"
    REFERRAL = "referral", "Referral"
    COLD_CALL = "cold_call", "Cold Call"
    SOCIAL = "social", "Social"
    OTHER = "other", "Other"


class ActivityType(models.TextChoices):
    COMMENT = "comment", "Comment"
    EMAIL_OUT = "email_out", "Email (Outbound)"
    EMAIL_IN = "email_in", "Email (Inbound)"
    CALL = "call", "Call"
    MEETING = "meeting", "Meeting"
    STATUS_CHANGE = "status_change", "Status Change"
    FILE_UPLOAD = "file_upload", "File Upload"
    TASK_ASSIGNED = "task_assigned", "Task Assigned"
    TASK_COMPLETED = "task_completed", "Task Completed"


# ---------------------------------------------------------------------------
# Customer (Address Book)
# ---------------------------------------------------------------------------

class Customer(TenantModel):
    """
    A contact in the address book. A single Customer can be linked to many
    Leads inside the same Firm.

    ``tags`` is stored as a JSONField (list of strings) for maximum database
    compatibility while still supporting PostgreSQL's native array operators
    when accessed via the Django ORM.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of free-form string tags for quick filtering.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary key-value pairs for custom fields.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantModel.Meta):
        verbose_name = "customer"
        verbose_name_plural = "customers"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["firm", "email"]),
        ]

    def __str__(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return f"{name} ({self.firm})" if name else self.email


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------

class Lead(TenantModel):
    """
    The central entity of the CRM — an inbound or outbound opportunity.

    ``customer`` is nullable to allow 'quick entry' leads where the
    full contact record is filled in later.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=LeadSource.choices,
        default=LeadSource.WEB,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_leads",
    )
    value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated deal value.",
    )
    currency = models.CharField(max_length=3, default="CZK")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantModel.Meta):
        verbose_name = "lead"
        verbose_name_plural = "leads"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["firm", "status"]),
            models.Index(fields=["firm", "assigned_to"]),
        ]

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"


# ---------------------------------------------------------------------------
# Activity (Polymorphic timeline log)
# ---------------------------------------------------------------------------

class Activity(models.Model):
    """
    An immutable event on the lead's timeline.

    The ``metadata`` JSONField carries type-specific payload:

    * EMAIL_OUT / EMAIL_IN → {"subject": "...", "to": "...", "message_id": "..."}
    * STATUS_CHANGE        → {"old_status": "...", "new_status": "..."}
    * TASK_ASSIGNED /
      TASK_COMPLETED       → {"task_id": "...", "due_date": "...", "priority": "..."}
    * FILE_UPLOAD          → {"filename": "...", "url": "...", "size_bytes": 0}
    * CALL / MEETING       → {"duration_minutes": 0, "notes": "..."}
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activities",
        help_text="The user who performed / logged this action.",
    )
    type = models.CharField(
        max_length=30,
        choices=ActivityType.choices,
        db_index=True,
    )
    content_text = models.TextField(blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Type-specific structured data (see model docstring).",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "activity"
        verbose_name_plural = "activities"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "-created_at"]),
            models.Index(fields=["lead", "type"]),
        ]

    def __str__(self):
        return (
            f"{self.get_type_display()} on Lead#{self.lead_id} "
            f"at {self.created_at:%Y-%m-%d %H:%M}"
        )


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Lead Attachment
# ---------------------------------------------------------------------------

def _attachment_upload_to(instance, filename):
    """Store attachments under media/attachments/<lead_id>/<filename>."""
    return f"attachments/{instance.lead_id}/{filename}"


class LeadAttachment(TenantModel):
    """
    A file attached to a Lead, served via Django's file server.

    The physical file is stored in MEDIA_ROOT/attachments/<lead_id>/.
    The ``file`` field's ``.url`` property resolves to the correct URL
    regardless of the active storage backend (local or S3).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_attachments",
    )
    file = models.FileField(upload_to=_attachment_upload_to)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(TenantModel.Meta):
        verbose_name = "lead attachment"
        verbose_name_plural = "lead attachments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "-created_at"]),
        ]

    def __str__(self):
        return self.original_filename


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class Task(TenantModel):
    """
    A to-do item scoped to a Lead. Completion is tracked explicitly so that
    we can log a TASK_COMPLETED Activity automatically.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    due_date = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantModel.Meta):
        verbose_name = "task"
        verbose_name_plural = "tasks"
        ordering = ["due_date", "created_at"]
        indexes = [
            models.Index(fields=["firm", "is_completed"]),
            models.Index(fields=["lead", "is_completed"]),
        ]

    def __str__(self):
        done = "✓" if self.is_completed else "○"
        return f"{done} {self.title}"


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class Notification(models.Model):
    """
    A persistent in-app notification for a specific Firm member.

    Created whenever a significant CRM event is broadcast over WebSocket so
    that users who are offline at the time can still catch up via the bell panel.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    event = models.CharField(
        max_length=50,
        help_text="Event name, e.g. 'lead.created', 'activity.created', 'task.completed'.",
    )
    payload = models.JSONField(
        default=dict,
        help_text="Event-specific structured payload (mirrors the WebSocket message).",
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'notification'
        verbose_name_plural = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['firm', 'user', 'is_read']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        read = '✓' if self.is_read else '○'
        return f'{read} [{self.event}] → {self.user}'


# ---------------------------------------------------------------------------
# Import Job (CSV bulk import)
# ---------------------------------------------------------------------------

def _import_upload_to(instance, filename):
    """Store imported CSV files under media/imports/<firm_id>/<filename>."""
    return f"imports/{instance.firm_id}/{filename}"


class ImportJobType(models.TextChoices):
    LEADS = "leads", "Leads"
    CUSTOMERS = "customers", "Customers"


class ImportJobStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class ImportJob(TenantModel):
    """
    Tracks the progress of a background CSV import for leads or customers.

    The Celery task ``process_import_job`` reads ``file``, creates records,
    and updates ``processed``, ``failed_count``, ``errors_json``, and
    ``status`` in place.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_jobs",
    )
    type = models.CharField(
        max_length=20,
        choices=ImportJobType.choices,
        default=ImportJobType.LEADS,
    )
    status = models.CharField(
        max_length=20,
        choices=ImportJobStatus.choices,
        default=ImportJobStatus.PENDING,
        db_index=True,
    )
    file = models.FileField(upload_to=_import_upload_to)
    original_filename = models.CharField(max_length=255, blank=True)
    total = models.PositiveIntegerField(default=0, help_text="Total rows in CSV (excluding header).")
    processed = models.PositiveIntegerField(default=0, help_text="Rows successfully imported so far.")
    failed_count = models.PositiveIntegerField(default=0, help_text="Rows that could not be imported.")
    errors_json = models.JSONField(
        default=list,
        blank=True,
        help_text="List of {row, error} dicts for rows that failed.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        verbose_name = "import job"
        verbose_name_plural = "import jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"ImportJob({self.type}, {self.status}) — {self.firm}"
