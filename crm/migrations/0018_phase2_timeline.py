# Generated for Phase 2 — Unified task timeline (TaskTimelineEntry,
# TaskCommentReaction, TaskVoiceAttachment).
#
# NOTE: This migration is numbered 0018 even though it implements "Phase 2"
# of the product roadmap.  Phase 3 (0017) was merged first.  The migration
# sequence follows the order of database history, not the product roadmap.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
import crm.models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0017_phase3_checklist_dependencies"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------
        # TaskTimelineEntry
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="TaskTimelineEntry",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("comment", "Comment"),
                            ("file_upload", "File Upload"),
                            ("status_change", "Status Change"),
                            ("priority_change", "Priority Change"),
                            ("assignee_change", "Assignee Change"),
                            ("due_date_change", "Due Date Change"),
                            ("sub_task_added", "Sub-task Added"),
                            ("task_created", "Task Created"),
                            ("task_assigned", "Task Assigned"),
                            ("task_completed", "Task Completed"),
                            ("task_archived", "Task Archived"),
                            ("approval_requested", "Approval Requested"),
                            ("approval_resolved", "Approval Resolved"),
                            ("time_logged", "Time Logged"),
                            ("checklist_item_checked", "Checklist Item Checked"),
                        ],
                        db_index=True,
                        default="comment",
                        max_length=30,
                    ),
                ),
                ("content_html", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="task_timeline_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="replies",
                        to="crm.tasktimelineentry",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timeline_entries",
                        to="crm.task",
                    ),
                ),
            ],
            options={
                "verbose_name": "task timeline entry",
                "verbose_name_plural": "task timeline entries",
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(
                        fields=["task", "created_at"],
                        name="crm_taskti_task_id_created_idx",
                    ),
                    models.Index(
                        fields=["task", "event_type"],
                        name="crm_taskti_task_id_evtype_idx",
                    ),
                ],
            },
        ),
        # ------------------------------------------------------------------
        # TaskCommentReaction
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="TaskCommentReaction",
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
                ("emoji", models.CharField(max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "entry",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reactions",
                        to="crm.tasktimelineentry",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_comment_reactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "task comment reaction",
                "verbose_name_plural": "task comment reactions",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="taskcommentreaction",
            constraint=models.UniqueConstraint(
                fields=("entry", "user", "emoji"),
                name="unique_task_comment_reaction",
            ),
        ),
        # ------------------------------------------------------------------
        # TaskVoiceAttachment
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="TaskVoiceAttachment",
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
                    "file",
                    models.FileField(
                        upload_to=crm.models._voice_attachment_upload_to,
                    ),
                ),
                (
                    "duration_seconds",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "timeline_entry",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="voice_attachments",
                        to="crm.tasktimelineentry",
                    ),
                ),
            ],
            options={
                "verbose_name": "task voice attachment",
                "verbose_name_plural": "task voice attachments",
            },
        ),
    ]
