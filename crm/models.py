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
    PROPOSAL_ACCEPTED = "proposal_accepted", "Proposal Accepted"
    PROPOSAL_REJECTED = "proposal_rejected", "Proposal Rejected"


class ProposalStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    VIEWED = "viewed", "Viewed"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"


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
# Project
# ---------------------------------------------------------------------------

class Project(TenantModel):
    """
    A lightweight project container. Tasks can be assigned to multiple projects.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantModel.Meta):
        verbose_name = "project"
        verbose_name_plural = "projects"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Task choices
# ---------------------------------------------------------------------------

class TaskPriority(models.TextChoices):
    NONE = "none", "None"
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class TaskStatus(models.TextChoices):
    TODO = "todo", "To Do"
    IN_PROGRESS = "in_progress", "In Progress"
    BLOCKED = "blocked", "Blocked"
    DONE = "done", "Done"
    CANCELLED = "cancelled", "Cancelled"


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class Task(TenantModel):
    """
    A to-do item that can optionally be linked to a Lead, Proposal, Customer,
    or exist independently. Completion is tracked explicitly so that we can
    log a TASK_COMPLETED Activity automatically.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Entity links — all optional; a task may exist standalone
    lead = models.ForeignKey(
        Lead,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    proposal = models.ForeignKey(
        "Proposal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    customer = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    parent_task = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subtasks",
        help_text="Parent task for subtask hierarchy (prepared for Phase 3).",
    )
    projects = models.ManyToManyField(
        Project,
        blank=True,
        related_name="tasks",
        help_text="Projects this task belongs to (multi-project support).",
    )

    # Authorship
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
        help_text="User who originally created this task.",
    )

    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_tasks",
        help_text="User who marked this task as done.",
    )
    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="watched_tasks",
        help_text="Users who receive notifications about changes to this task.",
    )

    # Content
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text="Plain-text description (legacy).")
    description_html = models.TextField(
        blank=True,
        help_text="Rich-text HTML description from TipTap editor.",
    )
    description_added_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the rich-text description was last set.",
    )

    # Classification
    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO,
        db_index=True,
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tag strings.",
    )

    # Dates
    due_date = models.DateTimeField(null=True, blank=True)
    due_date_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of date range when 'Rozsah termínů' toggle is on.",
    )

    # State flags
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary structured data (e.g. extra assignees from @mentions).",
    )

    class Meta(TenantModel.Meta):
        verbose_name = "task"
        verbose_name_plural = "tasks"
        ordering = ["due_date", "created_at"]
        indexes = [
            models.Index(fields=["firm", "is_completed"]),
            models.Index(fields=["firm", "status"]),
            models.Index(fields=["firm", "priority"]),
            models.Index(fields=["firm", "is_archived"]),
        ]

    def __str__(self):
        done = "✓" if self.is_completed else "○"
        return f"{done} {self.title}"


# ---------------------------------------------------------------------------
# Task Favourite (per-user ⭐)
# ---------------------------------------------------------------------------

class TaskFavourite(models.Model):
    """Tracks which tasks a user has starred as favourite."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="favourites")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_favourites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "task favourite"
        verbose_name_plural = "task favourites"
        unique_together = [("task", "user")]

    def __str__(self):
        return f"Favourite: {self.task_id} by {self.user_id}"


# ---------------------------------------------------------------------------
# Task Reminder (personal reminder per user)
# ---------------------------------------------------------------------------

class TaskReminder(models.Model):
    """Personal reminder for a task — triggers a notification at remind_at."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="reminders")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_reminders",
    )
    remind_at = models.DateTimeField(db_index=True)
    is_sent = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "task reminder"
        verbose_name_plural = "task reminders"
        ordering = ["remind_at"]

    def __str__(self):
        return f"Reminder for task {self.task_id} at {self.remind_at}"


# ---------------------------------------------------------------------------
# Task Comment
# ---------------------------------------------------------------------------

class TaskComment(models.Model):
    """
    A rich-text comment on a Task, authored by a Firm member.

    The ``content_html`` field stores sanitised HTML produced by the
    Tiptap rich-text editor (supports @mentions, bullet lists, checklists, etc.).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_comments",
    )
    content_html = models.TextField(help_text="Sanitised HTML content from the rich-text editor.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "task comment"
        verbose_name_plural = "task comments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"]),
        ]

    def __str__(self):
        return f"Comment on Task#{self.task_id} by {self.author_id}"


# ---------------------------------------------------------------------------
# Task Attachment
# ---------------------------------------------------------------------------

def _task_attachment_upload_to(instance, filename):
    """Store task attachments under media/task_attachments/<task_id>/<filename>."""
    return f"task_attachments/{instance.task_id}/{filename}"


class TaskAttachment(models.Model):
    """A file attached to a Task."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_attachments",
    )
    file = models.FileField(upload_to=_task_attachment_upload_to)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "task attachment"
        verbose_name_plural = "task attachments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task", "-created_at"]),
        ]

    def __str__(self):
        return self.original_filename


# ---------------------------------------------------------------------------
# Task Checklist Item
# ---------------------------------------------------------------------------

class TaskChecklistItem(models.Model):
    """A single checkbox item inside a Task's built-in checklist."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="checklist_items")
    text = models.CharField(max_length=500)
    is_checked = models.BooleanField(default=False, db_index=True)
    position = models.PositiveSmallIntegerField(default=0, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_checklist_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "task checklist item"
        verbose_name_plural = "task checklist items"
        ordering = ["position", "created_at"]
        indexes = [
            models.Index(fields=["task", "position"]),
        ]

    def __str__(self):
        checked = "☑" if self.is_checked else "☐"
        return f"{checked} {self.text}"


# ---------------------------------------------------------------------------
# Task Dependency
# ---------------------------------------------------------------------------

class TaskDependencyType(models.TextChoices):
    BLOCKS = "blocks", "Blocks"
    RELATED_TO = "related_to", "Related To"


class TaskDependency(models.Model):
    """
    A directed dependency between two tasks.

    ``type=blocks``    — from_task blocks to_task (to_task cannot start until from_task is done)
    ``type=related_to`` — loose relation without blocking semantics
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="outgoing_dependencies",
        help_text="The task that is the source of the dependency.",
    )
    to_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="incoming_dependencies",
        help_text="The task that is the target of the dependency.",
    )
    type = models.CharField(
        max_length=20,
        choices=TaskDependencyType.choices,
        default=TaskDependencyType.BLOCKS,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_task_dependencies",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "task dependency"
        verbose_name_plural = "task dependencies"
        unique_together = [("from_task", "to_task", "type")]
        indexes = [
            models.Index(fields=["from_task", "type"]),
            models.Index(fields=["to_task", "type"]),
        ]

    def __str__(self):
        return f"Task {self.from_task_id} {self.type} Task {self.to_task_id}"


# ---------------------------------------------------------------------------
# Phase 2 — Unified task timeline
# ---------------------------------------------------------------------------

class TimelineEventType(models.TextChoices):
    """
    All possible event types in a task timeline.

    ``comment``                — user-authored rich-text comment
    ``file_upload``            — file attached to the task
    ``status_change``          — task status was changed
    ``priority_change``        — task priority was changed
    ``assignee_change``        — task was (re-)assigned
    ``due_date_change``        — due date or range was updated
    ``sub_task_added``         — a sub-task was created under this task
    ``task_created``           — the task itself was created
    ``task_assigned``          — task first-assigned to a user
    ``task_completed``         — task was marked as completed
    ``task_archived``          — task was archived
    ``approval_requested``     — approval workflow started
    ``approval_resolved``      — approval was accepted or rejected
    ``time_logged``            — time was manually logged or timer stopped
    ``checklist_item_checked`` — a checklist item was ticked/unticked
    """

    COMMENT = "comment", "Comment"
    FILE_UPLOAD = "file_upload", "File Upload"
    STATUS_CHANGE = "status_change", "Status Change"
    PRIORITY_CHANGE = "priority_change", "Priority Change"
    ASSIGNEE_CHANGE = "assignee_change", "Assignee Change"
    DUE_DATE_CHANGE = "due_date_change", "Due Date Change"
    SUB_TASK_ADDED = "sub_task_added", "Sub-task Added"
    TASK_CREATED = "task_created", "Task Created"
    TASK_ASSIGNED = "task_assigned", "Task Assigned"
    TASK_COMPLETED = "task_completed", "Task Completed"
    TASK_ARCHIVED = "task_archived", "Task Archived"
    APPROVAL_REQUESTED = "approval_requested", "Approval Requested"
    APPROVAL_RESOLVED = "approval_resolved", "Approval Resolved"
    TIME_LOGGED = "time_logged", "Time Logged"
    CHECKLIST_ITEM_CHECKED = "checklist_item_checked", "Checklist Item Checked"


class TaskTimelineEntry(models.Model):
    """
    A single entry in the unified task timeline.

    Covers both user-authored comments (``event_type=comment``) and automatic
    system events such as status changes, assignments, completions, etc.

    ``content_html`` is non-empty only for ``comment`` events.
    ``metadata``     carries structured data that varies per event type:
        - status_change:   {"from": "todo", "to": "in_progress"}
        - priority_change: {"from": "low",  "to": "high"}
        - assignee_change: {"from_name": "...", "to_name": "..."}
        - due_date_change: {"old": "ISO", "new": "ISO"}
        - sub_task_added:  {"subtask_id": "...", "title": "..."}
        - time_logged:     {"minutes": 30, "description": "..."}
    ``parent_entry`` enables shallow reply-threading on comment entries.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="timeline_entries",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_timeline_entries",
        help_text="User who created this entry (null for automated system events).",
    )
    event_type = models.CharField(
        max_length=30,
        choices=TimelineEventType.choices,
        default=TimelineEventType.COMMENT,
        db_index=True,
    )
    content_html = models.TextField(
        blank=True,
        help_text="Sanitised HTML from TipTap; only populated for comment entries.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured event data (varies by event_type).",
    )
    parent_entry = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
        help_text="Parent comment entry for reply threading.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "task timeline entry"
        verbose_name_plural = "task timeline entries"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"]),
            models.Index(fields=["task", "event_type"]),
        ]

    def __str__(self):
        return f"[{self.event_type}] on Task#{self.task_id} at {self.created_at}"


class TaskCommentReaction(models.Model):
    """
    An emoji reaction (e.g. 👍 ❤️ 😂) on a TaskTimelineEntry comment.

    The ``unique_together`` constraint ensures one user can only add each
    emoji once per comment; toggling sends the same request to remove it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(
        TaskTimelineEntry,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_comment_reactions",
    )
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "task comment reaction"
        verbose_name_plural = "task comment reactions"
        unique_together = [("entry", "user", "emoji")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.emoji} by {self.user_id} on entry {self.entry_id}"


def _voice_attachment_upload_to(instance, filename):
    """Store voice attachments under media/task_voice/<entry_id>/<filename>."""
    return f"task_voice/{instance.timeline_entry_id}/{filename}"


class TaskVoiceAttachment(models.Model):
    """
    An audio recording (voice message) attached to a TaskTimelineEntry comment.

    ``duration_seconds`` is set by the frontend recorder before upload.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timeline_entry = models.ForeignKey(
        TaskTimelineEntry,
        on_delete=models.CASCADE,
        related_name="voice_attachments",
    )
    file = models.FileField(upload_to=_voice_attachment_upload_to)
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of the recording in seconds (provided by the client).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "task voice attachment"
        verbose_name_plural = "task voice attachments"

    def __str__(self):
        return f"Voice msg on entry {self.timeline_entry_id}"


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
# Lead Status History (pipeline velocity tracking)
# ---------------------------------------------------------------------------

class LeadStatusHistory(models.Model):
    """
    Immutable record of every status transition on a Lead.

    Created automatically whenever a Lead's status changes (via the
    STATUS_CHANGE activity or direct ``update_lead`` API call).  Used to
    compute pipeline velocity — the average time a lead spends in each status.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(
        max_length=20,
        choices=LeadStatus.choices,
        blank=True,
        help_text="Empty string on the very first entry (initial status at creation).",
    )
    to_status = models.CharField(max_length=20, choices=LeadStatus.choices)
    changed_at = models.DateTimeField(db_index=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_status_changes",
    )

    class Meta:
        verbose_name = "lead status history"
        verbose_name_plural = "lead status histories"
        ordering = ["lead", "changed_at"]
        indexes = [
            models.Index(fields=["lead", "changed_at"]),
            models.Index(fields=["lead", "to_status"]),
        ]

    def __str__(self):
        return f"Lead#{self.lead_id}: {self.from_status} → {self.to_status} @ {self.changed_at:%Y-%m-%d %H:%M}"


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


# ---------------------------------------------------------------------------
# Push Notification Subscription (Web Push API)
# ---------------------------------------------------------------------------

class PushSubscription(models.Model):
    """
    Stores a browser Web Push subscription for a specific user.

    Each browser/device that opts in creates one record.  The ``endpoint``,
    ``p256dh`` key, and ``auth`` secret come from the browser's
    PushSubscription object and are required to encrypt and deliver a push
    notification via the Web Push protocol (RFC 8030).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField(help_text="Browser public key (base64url).")
    auth = models.TextField(help_text="Authentication secret (base64url).")
    user_agent = models.CharField(max_length=500, blank=True)
    push_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Set to False to soft-disable without removing the subscription.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "push subscription"
        verbose_name_plural = "push subscriptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "push_enabled"]),
        ]

    def __str__(self):
        return f"PushSubscription({self.user}, endpoint=…{self.endpoint[-20:]})"


# ---------------------------------------------------------------------------
# Dashboard Layout (per-user adaptive widget layout)
# ---------------------------------------------------------------------------

class DashboardLayout(models.Model):
    """
    Persists each user's dashboard widget arrangement.

    ``layout`` is a list of widget config objects, e.g.:
    [{"id": "pipeline_value", "visible": true, "order": 0}, ...]
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_layouts",
    )
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="dashboard_layouts",
    )
    layout = models.JSONField(
        default=list,
        help_text="Ordered list of widget config objects.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "dashboard layout"
        verbose_name_plural = "dashboard layouts"
        unique_together = [("user", "firm")]

    def __str__(self):
        return f"DashboardLayout({self.user}, {self.firm})"


# ---------------------------------------------------------------------------
# Lead Scoring Rule
# ---------------------------------------------------------------------------

class LeadScoringRule(TenantModel):
    """
    A single rule that contributes a delta to a lead's score (0–100).

    ``field``      — which lead attribute to test: 'status', 'source',
                     'value_gte', 'last_activity_days_lte'
    ``operand``    — JSON-encoded comparison value (string, number, etc.)
    ``score_delta``— points added when the rule matches (may be negative)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.CharField(
        max_length=50,
        help_text="Lead attribute to test.",
    )
    operand = models.JSONField(
        help_text="Comparison value for the field.",
    )
    score_delta = models.IntegerField(
        help_text="Points contributed when this rule matches.",
    )

    class Meta(TenantModel.Meta):
        verbose_name = "lead scoring rule"
        verbose_name_plural = "lead scoring rules"
        ordering = ["field"]

    def __str__(self):
        return f"LeadScoringRule(field={self.field}, delta={self.score_delta:+d}) [{self.firm}]"


# ---------------------------------------------------------------------------
# Saved View (named filter + sort preset)
# ---------------------------------------------------------------------------

class SavedView(models.Model):
    """
    A named combination of filters and sort settings saved by a user for
    the Leads or Customers list.
    """

    ENTITY_LEADS = "leads"
    ENTITY_CUSTOMERS = "customers"
    ENTITY_CHOICES = [
        (ENTITY_LEADS, "Leads"),
        (ENTITY_CUSTOMERS, "Customers"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    name = models.CharField(max_length=100)
    entity = models.CharField(max_length=20, choices=ENTITY_CHOICES)
    filters = models.JSONField(
        default=dict,
        help_text="Serialised filter state, e.g. {\"status\": \"new\", \"source\": \"web\"}.",
    )
    sort_by = models.CharField(max_length=50, blank=True)
    sort_dir = models.CharField(max_length=4, default="asc")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "saved view"
        verbose_name_plural = "saved views"
        ordering = ["entity", "name"]
        unique_together = [("user", "firm", "entity", "name")]

    def __str__(self):
        return f'SavedView("{self.name}", {self.entity}) [{self.user}]'


# ---------------------------------------------------------------------------
# Proposal Template (reusable line-item sets, scoped to Firm)
# ---------------------------------------------------------------------------

class ProposalTemplate(TenantModel):
    """
    A reusable proposal template scoped to a Firm.  Team members can apply a
    template to a new Proposal with one click to pre-populate line items and
    intro/closing text.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    intro_text = models.TextField(blank=True)
    closing_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantModel.Meta):
        verbose_name = "proposal template"
        verbose_name_plural = "proposal templates"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.firm}]"


class ProposalTemplateItem(models.Model):
    """A single line item belonging to a ProposalTemplate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ProposalTemplate,
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        help_text="Discount percentage (0–100).",
    )
    vat_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        help_text="VAT rate percentage (e.g. 21 for 21%).",
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "proposal template item"
        verbose_name_plural = "proposal template items"
        ordering = ["position"]

    def __str__(self):
        return f"{self.description} (template: {self.template_id})"


# ---------------------------------------------------------------------------
# Proposal (scoped to a Lead)
# ---------------------------------------------------------------------------

class Proposal(TenantModel):
    """
    A business proposal attached to a Lead.

    ``public_token`` is a UUID used to construct the signed public URL;
    it is regenerated each time the proposal is re-sent so that old links expire.
    ``view_count`` / ``first_viewed_at`` power the proposal analytics.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="proposals",
    )
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=ProposalStatus.choices,
        default=ProposalStatus.DRAFT,
        db_index=True,
    )
    expiry_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="CZK")
    notes = models.TextField(blank=True)
    intro_text = models.TextField(blank=True)
    closing_text = models.TextField(blank=True)

    # Public link
    public_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        help_text="Token used in the public (no-auth) proposal URL.",
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the public link expires.  Null = link never auto-expires.",
    )

    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantModel.Meta):
        verbose_name = "proposal"
        verbose_name_plural = "proposals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "-created_at"]),
            models.Index(fields=["firm", "status"]),
        ]

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    @property
    def total_value(self) -> Decimal:
        """Sum of all item totals (after discount + VAT)."""
        return sum(
            (item.total for item in self.items.all()),
            Decimal("0"),
        )


class ProposalItem(models.Model):
    """
    A single line item in a Proposal.

    Computed fields (subtotal, tax, total) are returned by the API as
    read-only values derived from quantity, unit_price, discount, vat_rate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        help_text="Discount percentage (0–100).",
    )
    vat_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        help_text="VAT rate percentage (e.g. 21 for 21%).",
    )
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "proposal item"
        verbose_name_plural = "proposal items"
        ordering = ["position", "created_at"]

    def __str__(self):
        return f"{self.description} (proposal: {self.proposal_id})"

    @property
    def subtotal(self) -> Decimal:
        """Quantity × unit price before discount."""
        return self.quantity * self.unit_price

    @property
    def discount_amount(self) -> Decimal:
        return self.subtotal * self.discount / Decimal("100")

    @property
    def after_discount(self) -> Decimal:
        return self.subtotal - self.discount_amount

    @property
    def tax(self) -> Decimal:
        return self.after_discount * self.vat_rate / Decimal("100")

    @property
    def total(self) -> Decimal:
        return self.after_discount + self.tax


# ---------------------------------------------------------------------------
# Email Sequence (v2.4 — Email Sequences plugin)
# ---------------------------------------------------------------------------

class EmailSequence(TenantModel):
    """
    A named drip campaign that is triggered when a lead transitions to a
    specific status.

    Steps are evaluated in ``step_order`` order, with each step sent
    ``delay_days`` after the previous one (or after enrollment for step 1).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    trigger_status = models.CharField(
        max_length=20,
        choices=LeadStatus.choices,
        db_index=True,
        help_text="Lead status that triggers enrollment into this sequence.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantModel.Meta):
        verbose_name = "email sequence"
        verbose_name_plural = "email sequences"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["firm", "trigger_status", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} (trigger: {self.trigger_status})"


class EmailSequenceStep(models.Model):
    """
    A single email in an EmailSequence.

    ``delay_days`` is relative to the previous step (or to enrollment for
    the first step).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(
        EmailSequence,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    step_order = models.PositiveSmallIntegerField(default=0)
    delay_days = models.PositiveIntegerField(
        default=0,
        help_text="Days after the previous step (or after enrollment for step 1) before this email is sent.",
    )
    subject = models.CharField(max_length=255)
    body_template = models.TextField(
        help_text="Plain-text email body. Supports {{lead_title}}, {{customer_name}} placeholders.",
    )

    class Meta:
        verbose_name = "email sequence step"
        verbose_name_plural = "email sequence steps"
        ordering = ["sequence", "step_order"]
        unique_together = [("sequence", "step_order")]

    def __str__(self):
        return f"Step {self.step_order}: {self.subject[:50]}"


class SequenceEnrollmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class SequenceEnrollment(TenantModel):
    """
    Records that a specific Lead is enrolled in a specific EmailSequence.

    ``next_step`` points to the next EmailSequenceStep to be sent.
    ``next_send_at`` is the datetime when that step should be dispatched.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(
        EmailSequence,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="sequence_enrollments",
    )
    status = models.CharField(
        max_length=20,
        choices=SequenceEnrollmentStatus.choices,
        default=SequenceEnrollmentStatus.ACTIVE,
        db_index=True,
    )
    current_step = models.PositiveSmallIntegerField(default=0)
    next_send_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the next sequence email should be dispatched.",
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantModel.Meta):
        verbose_name = "sequence enrollment"
        verbose_name_plural = "sequence enrollments"
        ordering = ["-enrolled_at"]
        indexes = [
            models.Index(fields=["status", "next_send_at"]),
        ]

    def __str__(self):
        return f"Enrollment: {self.lead} → {self.sequence} (step {self.current_step})"


# ---------------------------------------------------------------------------
# Workflow Automation (v2.5)
# ---------------------------------------------------------------------------

class AutomationTrigger(models.TextChoices):
    LEAD_CREATED = "lead_created", "Lead Created"
    LEAD_STATUS_CHANGE = "lead_status_change", "Lead Status Changed"
    TASK_OVERDUE = "task_overdue", "Task Overdue"
    PROPOSAL_SENT = "proposal_sent", "Proposal Sent"
    PROPOSAL_ACCEPTED = "proposal_accepted", "Proposal Accepted"
    LEAD_INACTIVE = "lead_inactive", "Lead Inactive (N days)"
    WEBHOOK_RECEIVED = "webhook_received", "Custom Webhook Received"


class AutomationRunStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"
    SKIPPED = "skipped", "Skipped"


class AutomationRule(TenantModel):
    """
    A trigger → condition(s) → action(s) automation rule scoped to a Firm.

    ``trigger``        — which event fires the rule
    ``trigger_config`` — trigger-specific settings (e.g. ``inactive_days`` for
                         LEAD_INACTIVE, ``warning_days`` for TASK_OVERDUE)
    ``conditions``     — list of ``{field, operator, value}`` dicts; ALL must
                         match (logical AND) for actions to run
    ``actions``        — ordered list of action dicts executed when triggered
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, db_index=True)
    trigger = models.CharField(
        max_length=50,
        choices=AutomationTrigger.choices,
        db_index=True,
    )
    trigger_config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Trigger-specific configuration. "
            "LEAD_INACTIVE: {inactive_days: 30}. "
            "TASK_OVERDUE: {warning_days: 1}."
        ),
    )
    conditions = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of {field, operator, value} condition objects. "
            "Supported operators: eq, neq, gt, gte, lt, lte, contains. "
            "All conditions must match (AND)."
        ),
    )
    actions = models.JSONField(
        default=list,
        help_text=(
            "Ordered list of action objects. Each action has a 'type' key: "
            "send_email, create_task, update_field, call_webhook, run_plugin_action."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantModel.Meta):
        verbose_name = "automation rule"
        verbose_name_plural = "automation rules"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["firm", "trigger", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.trigger}) [{self.firm}]"


class AutomationRun(models.Model):
    """
    Immutable execution log for an AutomationRule firing.

    Created for every trigger evaluation — whether the rule ran successfully,
    was skipped (conditions not met), or failed with an error.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    status = models.CharField(
        max_length=20,
        choices=AutomationRunStatus.choices,
        db_index=True,
    )
    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    context = models.JSONField(
        default=dict,
        help_text="Serialised event context that fired this run.",
    )
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = "automation run"
        verbose_name_plural = "automation runs"
        ordering = ["-triggered_at"]
        indexes = [
            models.Index(fields=["rule", "-triggered_at"]),
        ]

    def __str__(self):
        return (
            f"AutomationRun({self.rule.name}, {self.status}) "
            f"@ {self.triggered_at:%Y-%m-%d %H:%M}"
        )


# ---------------------------------------------------------------------------
# Task Public Share
# ---------------------------------------------------------------------------

class TaskPublicShare(models.Model):
    """Public share link for a task — allows readonly access without auth."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(Task, on_delete=models.CASCADE, related_name="public_share")
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "task public share"
        verbose_name_plural = "task public shares"

    def __str__(self):
        return f"Public share for task {self.task_id}"
