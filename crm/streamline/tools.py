from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

from crm.streamline.base import StreamlineTool

if TYPE_CHECKING:
    from crm.models import Activity


_MENTION_PREVIEW_LENGTH = 120


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

class CommentTool(StreamlineTool):
    activity_type = "comment"
    label = _("Comment")
    icon = "ChatBubbleLeftIcon"
    category = "communication"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content_text": {
                    "type": "string",
                    "format": "html",
                    "title": "Comment",
                },
                "mentions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Mentions",
                },
            },
            "required": ["content_text"],
        }

    def process_action(
        self,
        activity: "Activity",
        entity: Any,
        payload: dict,
        context: dict,
    ) -> None:
        from crm.models import Notification
        from django.contrib.auth import get_user_model

        firm = context["firm"]
        user = context["user"]
        entity_title = context.get("entity_title", "")
        lead = activity.lead

        mention_ids = payload.get("metadata", {}).get("mentions", [])
        if not mention_ids:
            return

        _User = get_user_model()
        mentioned_users = (
            _User.objects.filter(id__in=[str(uid) for uid in mention_ids])
            .filter(membership__firm=firm)
            .exclude(id=user.id)
            .distinct()
        )
        notification_payload = {
            "activity_id": str(activity.id),
            "entity_type": activity.entity_type,
            "entity_id": activity.entity_id,
            "entity_title": entity_title,
            "lead_id": str(lead.id) if lead else None,
            "lead_title": lead.title if lead else None,
            "by_user": getattr(user, "full_name", None) or user.email,
            "content_preview": activity.content_text[:_MENTION_PREVIEW_LENGTH],
        }
        for mentioned_user in mentioned_users:
            Notification.objects.create(
                firm=firm,
                user=mentioned_user,
                event="activity.mention",
                payload=notification_payload,
            )

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "mentions": activity.metadata.get("mentions", []),
        }


# ---------------------------------------------------------------------------
# Call
# ---------------------------------------------------------------------------

class CallTool(StreamlineTool):
    activity_type = "call"
    label = _("Call")
    icon = "PhoneIcon"
    category = "communication"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content_text": {"type": "string", "title": "Notes"},
                "duration_minutes": {
                    "type": "integer",
                    "title": "Duration (minutes)",
                    "minimum": 0,
                },
                "recording_url": {
                    "type": "string",
                    "format": "uri",
                    "title": "Recording URL",
                },
                "recording_filename": {
                    "type": "string",
                    "title": "Recording Filename",
                },
                "recording_size_bytes": {
                    "type": "integer",
                    "title": "Recording Size (bytes)",
                    "minimum": 0,
                },
                "transcript": {
                    "type": "string",
                    "title": "Transcript",
                },
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "duration_minutes": activity.metadata.get("duration_minutes"),
            "notes": activity.content_text,
            "recording_url": activity.metadata.get("recording_url"),
            "recording_filename": activity.metadata.get("recording_filename"),
            "recording_size_bytes": activity.metadata.get("recording_size_bytes"),
            "transcript": activity.metadata.get("transcript"),
        }


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------

class MeetingTool(StreamlineTool):
    activity_type = "meeting"
    label = _("Meeting")
    icon = "UsersIcon"
    category = "communication"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content_text": {"type": "string", "title": "Notes"},
                "duration_minutes": {
                    "type": "integer",
                    "title": "Duration (minutes)",
                    "minimum": 0,
                },
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "duration_minutes": activity.metadata.get("duration_minutes"),
            "notes": activity.content_text,
        }


# ---------------------------------------------------------------------------
# Email Outbound
# ---------------------------------------------------------------------------

class EmailOutTool(StreamlineTool):
    activity_type = "email_out"
    label = _("Email (Outbound)")
    icon = "PaperAirplaneIcon"
    category = "communication"
    default_visibility = "important"
    channel = "email"
    direction = "out"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content_text": {
                    "type": "string",
                    "format": "html",
                    "title": "Message",
                },
                "subject": {"type": "string", "title": "Subject"},
                "to": {"type": "string", "format": "email", "title": "To"},
            },
            "required": ["content_text"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        if activity.lead is not None:
            _trigger_email_task(activity)

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "subject": activity.metadata.get("subject", ""),
            "to": activity.metadata.get("to", ""),
            "message_id": activity.metadata.get("message_id", ""),
        }


# ---------------------------------------------------------------------------
# Email Inbound
# ---------------------------------------------------------------------------

class EmailInTool(StreamlineTool):
    activity_type = "email_in"
    label = _("Email (Inbound)")
    icon = "InboxArrowDownIcon"
    category = "communication"
    default_visibility = "important"
    channel = "email"
    direction = "in"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content_text": {
                    "type": "string",
                    "format": "html",
                    "title": "Message",
                },
                "subject": {"type": "string", "title": "Subject"},
                "from_address": {
                    "type": "string",
                    "format": "email",
                    "title": "From",
                },
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "subject": activity.metadata.get("subject", ""),
            "from_address": activity.metadata.get("from", ""),
        }


# ---------------------------------------------------------------------------
# Status Change
# ---------------------------------------------------------------------------

class StatusChangeTool(StreamlineTool):
    activity_type = "status_change"
    label = _("Status Change")
    icon = "ArrowsRightLeftIcon"
    category = "system"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "new_status": {
                    "type": "string",
                    "title": "New Status",
                    "enum": [
                        "new",
                        "contacted",
                        "proposal",
                        "negotiation",
                        "won",
                        "lost",
                        "canceled",
                    ],
                },
            },
            "required": ["new_status"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        from crm.models import LeadStatus

        lead = activity.lead
        if lead is None:
            return

        metadata = payload.get("metadata", {})
        new_status = metadata.get("new_status")
        if not new_status or new_status not in [s.value for s in LeadStatus]:
            return

        old_status = lead.status
        lead.status = new_status
        lead.save(update_fields=["status", "updated_at"])
        activity.metadata = {**activity.metadata, "old_status": old_status}
        activity.save(update_fields=["metadata"])

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "old_status": activity.metadata.get("old_status", ""),
            "new_status": activity.metadata.get("new_status", ""),
        }


# ---------------------------------------------------------------------------
# File Upload
# ---------------------------------------------------------------------------

class FileUploadTool(StreamlineTool):
    activity_type = "file_upload"
    label = _("File Upload")
    icon = "PaperClipIcon"
    category = "system"
    default_visibility = "important"

    def get_schema(self) -> dict:
        # Schema notes:
        #   * ``title`` is the user-facing label of the file as a whole
        #     (NOT the filename) — the SPA renders it required.
        #   * ``source_kind`` distinguishes between an externally hosted
        #     URL reference and a binary the user uploaded directly.
        #   * ``store_locally`` only applies to ``source_kind="url"``: when
        #     true, the backend asynchronously downloads the resource into
        #     our Document storage; when false, we keep just the link.
        #   * ``filename`` / ``size_bytes`` / ``mime_type`` are populated
        #     server-side from the upload (or the async URL fetch) and
        #     deliberately hidden in the user-facing form.
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "title": "Title"},
                "url": {"type": "string", "format": "uri", "title": "URL"},
                "source_kind": {
                    "type": "string",
                    "enum": ["url", "upload"],
                    "title": "Source",
                },
                "store_locally": {
                    "type": "boolean",
                    "title": "Store locally",
                    "default": True,
                },
                "filename": {"type": "string", "title": "Filename"},
                "size_bytes": {
                    "type": "integer",
                    "title": "Size (bytes)",
                    "minimum": 0,
                },
                "mime_type": {"type": "string", "title": "MIME Type"},
            },
            "required": ["title", "url"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        # When the user pasted a URL and asked us to store the file
        # locally, hand the heavy lifting off to a Celery worker so the
        # API request returns immediately.  The activity's metadata will
        # be patched in-place once the download finishes.
        meta = activity.metadata or {}
        if (
            meta.get("source_kind") == "url"
            and meta.get("store_locally")
            and meta.get("url")
        ):
            try:
                from crm.tasks import fetch_remote_file_for_activity

                fetch_remote_file_for_activity.delay(str(activity.id))
            except Exception:  # pragma: no cover — Celery broker may be unavailable in dev
                pass

    def render_payload(self, activity: "Activity") -> dict:
        meta = activity.metadata or {}
        return {
            "title": meta.get("title", ""),
            "filename": meta.get("filename", ""),
            "url": meta.get("url", ""),
            "size_bytes": meta.get("size_bytes", 0),
            "mime_type": meta.get("mime_type", ""),
            "source_kind": meta.get("source_kind", "upload"),
            "store_locally": meta.get("store_locally", True),
            "document_id": meta.get("document_id", ""),
            "fetch_status": meta.get("fetch_status", ""),
        }


# ---------------------------------------------------------------------------
# Task Assigned
# ---------------------------------------------------------------------------

class TaskAssignedTool(StreamlineTool):
    activity_type = "task_assigned"
    label = _("Task Assigned")
    icon = "ClipboardDocumentListIcon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "title": "Task ID"},
                "task_title": {"type": "string", "title": "Task Title"},
                "due_date": {
                    "type": "string",
                    "format": "date",
                    "title": "Due Date",
                },
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "task_id": activity.metadata.get("task_id", ""),
            "task_title": activity.metadata.get("task_title", ""),
            "due_date": activity.metadata.get("due_date"),
        }


# ---------------------------------------------------------------------------
# Task Completed
# ---------------------------------------------------------------------------

class TaskCompletedTool(StreamlineTool):
    activity_type = "task_completed"
    label = _("Task Completed")
    icon = "CheckCircleIcon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "title": "Task ID"},
                "task_title": {"type": "string", "title": "Task Title"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "task_id": activity.metadata.get("task_id", ""),
            "task_title": activity.metadata.get("task_title", ""),
        }


# ---------------------------------------------------------------------------
# Proposal Created
# ---------------------------------------------------------------------------

class ProposalCreatedTool(StreamlineTool):
    activity_type = "proposal_created"
    label = _("Proposal Created")
    icon = "DocumentTextIcon"
    category = "commerce"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "title": "Proposal ID"},
                "proposal_title": {"type": "string", "title": "Proposal Title"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "proposal_id": activity.metadata.get("proposal_id", ""),
            "proposal_title": activity.metadata.get("proposal_title", ""),
        }


# ---------------------------------------------------------------------------
# Proposal Accepted
# ---------------------------------------------------------------------------

class ProposalAcceptedTool(StreamlineTool):
    activity_type = "proposal_accepted"
    label = _("Proposal Accepted")
    icon = "DocumentCheckIcon"
    category = "commerce"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "title": "Proposal ID"},
                "proposal_title": {"type": "string", "title": "Proposal Title"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "proposal_id": activity.metadata.get("proposal_id", ""),
            "proposal_title": activity.metadata.get("proposal_title", ""),
        }


# ---------------------------------------------------------------------------
# Proposal Rejected
# ---------------------------------------------------------------------------

class ProposalRejectedTool(StreamlineTool):
    activity_type = "proposal_rejected"
    label = _("Proposal Rejected")
    icon = "DocumentTextIcon"
    category = "commerce"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "title": "Proposal ID"},
                "proposal_title": {"type": "string", "title": "Proposal Title"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "proposal_id": activity.metadata.get("proposal_id", ""),
            "proposal_title": activity.metadata.get("proposal_title", ""),
        }


# ---------------------------------------------------------------------------
# Entity Change (auto-logged by signals — not user-composable)
# ---------------------------------------------------------------------------

class EntityChangeTool(StreamlineTool):
    """
    Records an automatic field-level change on any CRM entity.

    Created by Django ``pre_save``/``post_save`` signals — not via user
    action, so ``process_action`` is a no-op and the schema intentionally
    omits ``content_text`` to keep it out of the composer action picker.
    """

    activity_type = "entity_change"
    label = _("Field Changed")
    icon = "PencilSquareIcon"
    category = "system"
    default_visibility = "secondary"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "field": {"type": "string", "title": "Field"},
                "field_label": {"type": "string", "title": "Field Label"},
                "old_value": {"type": "string", "title": "Old Value"},
                "new_value": {"type": "string", "title": "New Value"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass  # auto-logged; no side-effects needed

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "field": activity.metadata.get("field", ""),
            "field_label": activity.metadata.get("field_label", ""),
            "old_value": activity.metadata.get("old_value", ""),
            "new_value": activity.metadata.get("new_value", ""),
        }


# ---------------------------------------------------------------------------
# Priority Change
# ---------------------------------------------------------------------------

class PriorityChangeTool(StreamlineTool):
    activity_type = "priority_change"
    label = _("Priority Change")
    icon = "FlagIcon"
    category = "system"
    default_visibility = "secondary"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "old_priority": {"type": "string", "title": "Old Priority"},
                "new_priority": {"type": "string", "title": "New Priority"},
            },
            "required": ["new_priority"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass  # log only; the priority change itself is performed by the caller

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "old_priority": activity.metadata.get("old_priority", ""),
            "new_priority": activity.metadata.get("new_priority", ""),
        }


# ---------------------------------------------------------------------------
# Assignee Change
# ---------------------------------------------------------------------------

class AssigneeChangeTool(StreamlineTool):
    activity_type = "assignee_change"
    label = _("Assignee Change")
    icon = "UserCircleIcon"
    category = "system"
    default_visibility = "secondary"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "old_assignee_id": {"type": "string", "title": "Old Assignee"},
                "new_assignee_id": {"type": "string", "title": "New Assignee"},
                "old_assignee_name": {"type": "string", "title": "Old Assignee Name"},
                "new_assignee_name": {"type": "string", "title": "New Assignee Name"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        """Notify the new assignee, if any, that they have been assigned."""
        from crm.models import Notification
        from django.contrib.auth import get_user_model

        firm = context["firm"]
        actor = context.get("user")
        metadata = payload.get("metadata", {}) or {}
        new_assignee_id = metadata.get("new_assignee_id")
        if not new_assignee_id:
            return

        _User = get_user_model()
        try:
            new_assignee = _User.objects.filter(
                id=str(new_assignee_id),
                memberships__firm=firm,
            ).distinct().first()
        except Exception:
            new_assignee = None
        if new_assignee is None or (actor and new_assignee.id == actor.id):
            return

        Notification.objects.create(
            firm=firm,
            user=new_assignee,
            event="activity.assigned",
            payload={
                "activity_id": str(activity.id),
                "entity_type": activity.entity_type,
                "entity_id": activity.entity_id,
                "entity_title": context.get("entity_title", ""),
                "by_user": getattr(actor, "full_name", None) or (actor.email if actor else None),
            },
        )

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "old_assignee_id": activity.metadata.get("old_assignee_id", ""),
            "new_assignee_id": activity.metadata.get("new_assignee_id", ""),
            "old_assignee_name": activity.metadata.get("old_assignee_name", ""),
            "new_assignee_name": activity.metadata.get("new_assignee_name", ""),
        }


# ---------------------------------------------------------------------------
# Due Date Change
# ---------------------------------------------------------------------------

class DueDateChangeTool(StreamlineTool):
    activity_type = "due_date_change"
    label = _("Due Date Change")
    icon = "CalendarIcon"
    category = "task"
    default_visibility = "secondary"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "old_due_date": {"type": "string", "title": "Old Due Date"},
                "new_due_date": {"type": "string", "title": "New Due Date"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "old_due_date": activity.metadata.get("old_due_date", ""),
            "new_due_date": activity.metadata.get("new_due_date", ""),
        }


# ---------------------------------------------------------------------------
# Sub-task Added
# ---------------------------------------------------------------------------

class SubTaskAddedTool(StreamlineTool):
    activity_type = "sub_task_added"
    label = _("Sub-task Added")
    icon = "Squares2X2Icon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "subtask_id": {"type": "string", "title": "Subtask ID"},
                "subtask_title": {"type": "string", "title": "Subtask Title"},
            },
            "required": ["subtask_title"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "subtask_id": activity.metadata.get("subtask_id", ""),
            "subtask_title": activity.metadata.get("subtask_title", ""),
        }


# ---------------------------------------------------------------------------
# Task Created
# ---------------------------------------------------------------------------

class TaskCreatedTool(StreamlineTool):
    activity_type = "task_created"
    label = _("Task Created")
    icon = "PlusCircleIcon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "title": "Task ID"},
                "task_title": {"type": "string", "title": "Task Title"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "task_id": activity.metadata.get("task_id", ""),
            "task_title": activity.metadata.get("task_title", ""),
        }


# ---------------------------------------------------------------------------
# Task Archived
# ---------------------------------------------------------------------------

class TaskArchivedTool(StreamlineTool):
    activity_type = "task_archived"
    label = _("Task Archived")
    icon = "ArchiveBoxIcon"
    category = "task"
    default_visibility = "secondary"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "title": "Task ID"},
                "task_title": {"type": "string", "title": "Task Title"},
                "archived": {"type": "boolean", "title": "Archived"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "task_id": activity.metadata.get("task_id", ""),
            "task_title": activity.metadata.get("task_title", ""),
            "archived": activity.metadata.get("archived", True),
        }


# ---------------------------------------------------------------------------
# Approval Requested
# ---------------------------------------------------------------------------

class ApprovalRequestedTool(StreamlineTool):
    activity_type = "approval_requested"
    label = _("Approval Requested")
    icon = "ShieldExclamationIcon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "approver_id": {"type": "string", "title": "Approver"},
                "approver_name": {"type": "string", "title": "Approver Name"},
                "note": {"type": "string", "title": "Note"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "approver_id": activity.metadata.get("approver_id", ""),
            "approver_name": activity.metadata.get("approver_name", ""),
            "note": activity.metadata.get("note", ""),
        }


# ---------------------------------------------------------------------------
# Approval Resolved
# ---------------------------------------------------------------------------

class ApprovalResolvedTool(StreamlineTool):
    activity_type = "approval_resolved"
    label = _("Approval Resolved")
    icon = "ShieldCheckIcon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "approver_id": {"type": "string", "title": "Approver"},
                "approver_name": {"type": "string", "title": "Approver Name"},
                "decision": {
                    "type": "string",
                    "title": "Decision",
                    "enum": ["accepted", "rejected"],
                },
                "note": {"type": "string", "title": "Note"},
            },
            "required": ["decision"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "approver_id": activity.metadata.get("approver_id", ""),
            "approver_name": activity.metadata.get("approver_name", ""),
            "decision": activity.metadata.get("decision", ""),
            "note": activity.metadata.get("note", ""),
        }


# ---------------------------------------------------------------------------
# Time Logged
# ---------------------------------------------------------------------------

class TimeLoggedTool(StreamlineTool):
    activity_type = "time_logged"
    label = _("Time Logged")
    icon = "ClockIcon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "title": "Minutes",
                    "minimum": 0,
                },
                "description": {"type": "string", "title": "Description"},
                "started_at": {"type": "string", "format": "date-time", "title": "Started At"},
                "ended_at": {"type": "string", "format": "date-time", "title": "Ended At"},
            },
            "required": ["minutes"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "minutes": activity.metadata.get("minutes", 0),
            "description": activity.metadata.get("description", ""),
            "started_at": activity.metadata.get("started_at"),
            "ended_at": activity.metadata.get("ended_at"),
        }


# ---------------------------------------------------------------------------
# Checklist Item Checked
# ---------------------------------------------------------------------------

class ChecklistItemCheckedTool(StreamlineTool):
    activity_type = "checklist_item_checked"
    label = _("Checklist Item Checked")
    icon = "CheckIcon"
    category = "task"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "title": "Item ID"},
                "item_text": {"type": "string", "title": "Item Text"},
                "is_checked": {"type": "boolean", "title": "Checked"},
            },
            "required": ["item_text"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "item_id": activity.metadata.get("item_id", ""),
            "item_text": activity.metadata.get("item_text", ""),
            "is_checked": activity.metadata.get("is_checked", False),
        }


# ---------------------------------------------------------------------------
# Voice Memo
# ---------------------------------------------------------------------------

class VoiceMemoTool(StreamlineTool):
    activity_type = "voice_memo"
    label = _("Voice Memo")
    icon = "MicrophoneIcon"
    category = "communication"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri", "title": "Audio URL"},
                "filename": {"type": "string", "title": "Filename"},
                "duration_seconds": {
                    "type": "integer",
                    "title": "Duration (seconds)",
                    "minimum": 0,
                },
                "size_bytes": {
                    "type": "integer",
                    "title": "Size (bytes)",
                    "minimum": 0,
                },
                "transcript": {"type": "string", "title": "Transcript"},
            },
            "required": ["url"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "url": activity.metadata.get("url", ""),
            "filename": activity.metadata.get("filename", ""),
            "duration_seconds": activity.metadata.get("duration_seconds"),
            "size_bytes": activity.metadata.get("size_bytes"),
            "transcript": activity.metadata.get("transcript", ""),
        }


# ---------------------------------------------------------------------------
# Phase 6 — Bonus tools (communication / workflow / system)
# ---------------------------------------------------------------------------
# These tools extend the unified Streamline timeline beyond the core
# unification scope.  Most are pure logging tools (no side-effects); a few
# perform lightweight side-effects (notifications, stamping ``viewed_at``).
# Side-effect logic stays minimal and idempotent so any of these tools can
# be invoked from webhooks / Celery tasks as well as the SPA composer.
# ---------------------------------------------------------------------------


class _SimpleLogTool(StreamlineTool):
    """
    Helper base class for tools that only log a structured event into the
    timeline (no side-effects, schema fields are mirrored 1:1 into the
    rendered payload).

    Subclasses set:

    * ``activity_type`` / ``label`` / ``icon``
    * ``schema_properties``  — JSON Schema property dict
    * ``required_fields``    — list of required property names
    * ``payload_fields``     — list of metadata keys to surface in
                               ``render_payload`` (defaults to keys of
                               ``schema_properties``)
    """

    schema_properties: dict = {}
    required_fields: list[str] = []
    payload_fields: list[str] | None = None

    def get_schema(self) -> dict:
        schema: dict = {"type": "object", "properties": dict(self.schema_properties)}
        if self.required_fields:
            schema["required"] = list(self.required_fields)
        return schema

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        keys = self.payload_fields or list(self.schema_properties.keys())
        return {k: activity.metadata.get(k) for k in keys}


# --- SMS -------------------------------------------------------------------

class SmsOutTool(_SimpleLogTool):
    activity_type = "sms_out"
    label = _("SMS (Outbound)")
    icon = "DevicePhoneMobileIcon"
    category = "communication"
    default_visibility = "important"
    channel = "sms"
    direction = "out"
    schema_properties = {
        "content_text": {"type": "string", "title": "Message"},
        "to": {"type": "string", "title": "To"},
        "from_number": {"type": "string", "title": "From"},
        "provider_message_id": {"type": "string", "title": "Provider Message ID"},
    }
    required_fields = ["content_text", "to"]
    payload_fields = ["to", "from_number", "provider_message_id"]


class SmsInTool(_SimpleLogTool):
    activity_type = "sms_in"
    label = _("SMS (Inbound)")
    icon = "DevicePhoneMobileIcon"
    category = "communication"
    default_visibility = "important"
    channel = "sms"
    direction = "in"
    schema_properties = {
        "content_text": {"type": "string", "title": "Message"},
        "from_number": {"type": "string", "title": "From"},
        "to": {"type": "string", "title": "To"},
        "provider_message_id": {"type": "string", "title": "Provider Message ID"},
    }
    required_fields = ["content_text", "from_number"]
    payload_fields = ["from_number", "to", "provider_message_id"]


# --- WhatsApp / Chat -------------------------------------------------------

class WhatsAppOutTool(_SimpleLogTool):
    activity_type = "whatsapp_out"
    label = _("WhatsApp (Outbound)")
    icon = "ChatBubbleOvalLeftEllipsisIcon"
    category = "communication"
    default_visibility = "important"
    channel = "whatsapp"
    direction = "out"
    schema_properties = {
        "content_text": {"type": "string", "title": "Message"},
        "to": {"type": "string", "title": "To"},
        "from_number": {"type": "string", "title": "From"},
        "provider_message_id": {"type": "string", "title": "Provider Message ID"},
    }
    required_fields = ["content_text", "to"]
    payload_fields = ["to", "from_number", "provider_message_id"]


class WhatsAppInTool(_SimpleLogTool):
    activity_type = "whatsapp_in"
    label = _("WhatsApp (Inbound)")
    icon = "ChatBubbleOvalLeftEllipsisIcon"
    category = "communication"
    default_visibility = "important"
    channel = "whatsapp"
    direction = "in"
    schema_properties = {
        "content_text": {"type": "string", "title": "Message"},
        "from_number": {"type": "string", "title": "From"},
        "to": {"type": "string", "title": "To"},
        "provider_message_id": {"type": "string", "title": "Provider Message ID"},
    }
    required_fields = ["content_text", "from_number"]
    payload_fields = ["from_number", "to", "provider_message_id"]


class ChatTool(_SimpleLogTool):
    """Generic IM channel — distinguishes itself via ``metadata.channel``."""

    activity_type = "chat"
    label = _("Chat Message")
    icon = "ChatBubbleLeftRightIcon"
    category = "communication"
    default_visibility = "important"
    # ``channel`` is "chat" at the tool level (the unified composer surfaces
    # this as a single "Chat" option); the *specific* IM channel (slack, teams,
    # …) is captured per-activity inside ``schema_properties.channel`` below.
    # ``direction`` is left "none" because ChatTool covers both inbound and
    # outbound chat messages — the direction is captured per-activity in the
    # schema field.
    channel = "chat"
    direction = "none"
    schema_properties = {
        "content_text": {"type": "string", "title": "Message"},
        "channel": {
            "type": "string",
            "title": "Channel",
            "enum": ["slack", "teams", "telegram", "messenger", "discord", "other"],
        },
        "direction": {
            "type": "string",
            "title": "Direction",
            "enum": ["in", "out"],
        },
        "from_handle": {"type": "string", "title": "From"},
        "to_handle": {"type": "string", "title": "To"},
        "provider_message_id": {"type": "string", "title": "Provider Message ID"},
    }
    required_fields = ["content_text", "channel"]
    payload_fields = [
        "channel", "direction", "from_handle", "to_handle", "provider_message_id"
    ]


# --- Scheduled (calendar invite) tools -------------------------------------
#
# Scheduled-activity tools (Meeting Scheduled, Call Scheduled, …) act as
# parent objects: when invoked they (a) log the immutable Activity into
# the timeline as before, and (b) create a ``Task`` of the appropriate
# ``kind`` so the engagement appears in the user's calendar / agenda and
# can be auto-closed on expiry.  The Activity is linked to the Task via
# the existing ``Activity.task`` FK so the timeline keeps full history.


class _ScheduledActivityTool(_SimpleLogTool):
    """
    Base class for "X Scheduled" tools that own a child ``Task``.

    Subclasses set ``task_kind`` to one of ``TaskKind`` values and may
    override ``task_title_prefix``.  ``process_action`` parses
    ``start_at`` / ``end_at`` from the activity metadata and creates a
    Task linked to the same CRM entity as the activity.  The activity is
    then re-linked to the new Task via ``Activity.task``.
    """

    task_kind: str = ""
    task_title_prefix: str = ""

    def _parse_dt(self, value):
        if not value:
            return None
        if hasattr(value, "tzinfo"):
            return value
        from datetime import datetime
        from django.utils import timezone as _tz
        try:
            # Accept trailing 'Z' as UTC for ISO-8601 strings.
            iso = value.replace("Z", "+00:00") if isinstance(value, str) else value
            dt = datetime.fromisoformat(iso) if isinstance(iso, str) else iso
        except (TypeError, ValueError):
            return None
        if dt is not None and _tz.is_naive(dt):
            dt = _tz.make_aware(dt, _tz.get_current_timezone())
        return dt

    def render_payload(self, activity: "Activity") -> dict:
        # Surface raw schema-mapped metadata fields plus the linked
        # parent Task's status/kind so the SPA can render a badge or
        # state pill inline without a second request.
        payload = super().render_payload(activity)
        task = getattr(activity, "task", None)
        if task is not None:
            payload["task_id"] = str(task.id)
            payload["task_status"] = task.status
            payload["task_kind"] = task.kind
            payload["task_is_completed"] = task.is_completed
        else:
            payload["task_id"] = None
            payload["task_status"] = None
            payload["task_kind"] = None
            payload["task_is_completed"] = False
        return payload

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        from crm.models import Task

        firm = context.get("firm") or getattr(entity, "firm", None)
        if firm is None:
            return  # No tenant context — skip task creation defensively.

        metadata = payload.get("metadata") or {}
        start_at = self._parse_dt(metadata.get("start_at"))
        end_at = self._parse_dt(metadata.get("end_at"))

        title_bits = [self.task_title_prefix or str(self.label)]
        entity_title = (context.get("entity_title") or "").strip()
        if entity_title:
            title_bits.append(entity_title)
        title = " — ".join(b for b in title_bits if b)[:255]

        attendees_raw = metadata.get("attendees") or []
        attendees = [str(a) for a in attendees_raw if a is not None]

        task = Task.objects.create(
            firm=firm,
            kind=self.task_kind,
            title=title,
            description=activity.content_text or "",
            status="todo",
            priority="medium",
            due_date=start_at,
            due_date_end=end_at,
            location=str(metadata.get("location") or "")[:255],
            attendees=attendees,
            auto_close_on_expiry=True,
            assigned_to=context.get("user"),
            created_by=context.get("user"),
            lead=activity.lead,
            realization=activity.realization,
            management=activity.management,
            customer=activity.customer,
            proposal=activity.proposal,
            metadata={
                "source_activity_id": str(activity.id),
                "source_activity_type": activity.type,
                "ics_url": metadata.get("ics_url") or "",
                "provider_event_id": metadata.get("provider_event_id") or "",
            },
        )
        # Link the activity back to the freshly-created task.  We do not
        # overwrite an existing link (the activity may already belong to
        # a different task surface).
        if activity.task_id is None:
            activity.task = task
            activity.save(update_fields=["task"])


class MeetingScheduledTool(_ScheduledActivityTool):
    """
    Records a *future* calendar invite, distinct from ``meeting`` which
    records a meeting that already happened.  Creates a Task of kind
    ``meeting`` so the engagement is visible in the calendar / agenda.
    """

    activity_type = "meeting_scheduled"
    label = _("Meeting Scheduled")
    icon = "CalendarDaysIcon"
    category = "communication"
    default_visibility = "important"
    task_kind = "meeting"
    task_title_prefix = "Meeting"
    schema_properties = {
        "content_text": {"type": "string", "title": "Subject / Notes"},
        "start_at": {"type": "string", "format": "date-time", "title": "Start"},
        "end_at": {"type": "string", "format": "date-time", "title": "End"},
        "location": {"type": "string", "title": "Location"},
        "attendees": {
            "type": "array",
            "items": {"type": "string"},
            "title": "Attendees",
        },
        "ics_url": {"type": "string", "format": "uri", "title": "ICS URL"},
        "provider_event_id": {"type": "string", "title": "Provider Event ID"},
    }
    required_fields = ["start_at"]


class CallScheduledTool(_ScheduledActivityTool):
    """
    Records a *future* scheduled call, distinct from ``call`` which
    records a call that already happened.  Creates a Task of kind
    ``call`` so the engagement is visible in the calendar / agenda.
    """

    activity_type = "call_scheduled"
    label = _("Call Scheduled")
    icon = "PhoneIcon"
    category = "communication"
    default_visibility = "important"
    task_kind = "call"
    task_title_prefix = "Call"
    schema_properties = {
        "content_text": {"type": "string", "title": "Subject / Notes"},
        "start_at": {"type": "string", "format": "date-time", "title": "Start"},
        "end_at": {"type": "string", "format": "date-time", "title": "End"},
        "phone_number": {"type": "string", "title": "Phone number"},
        "attendees": {
            "type": "array",
            "items": {"type": "string"},
            "title": "Attendees",
        },
        "provider_event_id": {"type": "string", "title": "Provider Event ID"},
    }
    required_fields = ["start_at"]


# --- Link ------------------------------------------------------------------

class LinkTool(_SimpleLogTool):
    """A saved external link with optional Open Graph preview metadata."""

    activity_type = "link"
    label = _("Link")
    icon = "LinkIcon"
    category = "system"
    default_visibility = "secondary"
    schema_properties = {
        "url": {"type": "string", "format": "uri", "title": "URL"},
        "title": {"type": "string", "title": "Title"},
        "description": {"type": "string", "title": "Description"},
        "thumbnail_url": {
            "type": "string",
            "format": "uri",
            "title": "Thumbnail URL",
        },
    }
    required_fields = ["url"]


# --- Payment / Invoice -----------------------------------------------------

class PaymentReceivedTool(_SimpleLogTool):
    activity_type = "payment_received"
    label = _("Payment Received")
    icon = "BanknotesIcon"
    category = "commerce"
    default_visibility = "important"
    schema_properties = {
        "amount": {"type": "number", "title": "Amount"},
        "currency": {"type": "string", "title": "Currency"},
        "invoice_id": {"type": "string", "title": "Invoice ID"},
        "paid_at": {"type": "string", "format": "date-time", "title": "Paid At"},
        "method": {"type": "string", "title": "Method"},
        "provider": {"type": "string", "title": "Provider"},
    }
    required_fields = ["amount", "currency"]


class InvoiceSentTool(_SimpleLogTool):
    activity_type = "invoice_sent"
    label = _("Invoice Sent")
    icon = "DocumentCurrencyDollarIcon"
    category = "commerce"
    default_visibility = "important"
    schema_properties = {
        "invoice_id": {"type": "string", "title": "Invoice ID"},
        "invoice_number": {"type": "string", "title": "Invoice Number"},
        "amount": {"type": "number", "title": "Amount"},
        "currency": {"type": "string", "title": "Currency"},
        "due_date": {"type": "string", "format": "date", "title": "Due Date"},
        "url": {"type": "string", "format": "uri", "title": "Invoice URL"},
        "provider": {"type": "string", "title": "Provider"},
    }
    required_fields = ["invoice_id"]


# --- Signature workflow ----------------------------------------------------

class SignatureRequestedTool(_SimpleLogTool):
    activity_type = "signature_requested"
    label = _("Signature Requested")
    icon = "PencilSquareIcon"
    category = "commerce"
    default_visibility = "important"
    schema_properties = {
        "document_id": {"type": "string", "title": "Document ID"},
        "document_title": {"type": "string", "title": "Document Title"},
        "signer_email": {
            "type": "string",
            "format": "email",
            "title": "Signer Email",
        },
        "provider": {"type": "string", "title": "Provider"},
        "provider_request_id": {"type": "string", "title": "Provider Request ID"},
    }
    required_fields = ["document_id", "signer_email"]


class SignatureCompletedTool(_SimpleLogTool):
    activity_type = "signature_completed"
    label = _("Signature Completed")
    icon = "CheckBadgeIcon"
    category = "commerce"
    default_visibility = "important"
    schema_properties = {
        "document_id": {"type": "string", "title": "Document ID"},
        "document_title": {"type": "string", "title": "Document Title"},
        "signer_email": {
            "type": "string",
            "format": "email",
            "title": "Signer Email",
        },
        "signed_at": {"type": "string", "format": "date-time", "title": "Signed At"},
        "provider": {"type": "string", "title": "Provider"},
        "provider_request_id": {"type": "string", "title": "Provider Request ID"},
    }
    required_fields = ["document_id"]


# --- Proposal Viewed (passive tracking) ------------------------------------

class ProposalViewedTool(StreamlineTool):
    """
    Logs that a recipient opened a proposal.  Side-effect: stamp
    ``Proposal.first_viewed_at`` if not already set and bump ``view_count``.
    """

    activity_type = "proposal_viewed"
    label = _("Proposal Viewed")
    icon = "EyeIcon"
    category = "commerce"
    default_visibility = "secondary"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "title": "Proposal ID"},
                "proposal_title": {"type": "string", "title": "Proposal Title"},
                "viewer_email": {
                    "type": "string",
                    "format": "email",
                    "title": "Viewer Email",
                },
                "viewer_ip": {"type": "string", "title": "Viewer IP"},
                "user_agent": {"type": "string", "title": "User Agent"},
            },
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        from django.utils import timezone

        proposal = activity.proposal
        if proposal is None:
            return
        update_fields: list[str] = []
        if hasattr(proposal, "first_viewed_at") and proposal.first_viewed_at is None:
            proposal.first_viewed_at = timezone.now()
            update_fields.append("first_viewed_at")
        if hasattr(proposal, "view_count"):
            proposal.view_count = (proposal.view_count or 0) + 1
            update_fields.append("view_count")
        if update_fields:
            proposal.save(update_fields=update_fields)

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "proposal_id": activity.metadata.get("proposal_id", ""),
            "proposal_title": activity.metadata.get("proposal_title", ""),
            "viewer_email": activity.metadata.get("viewer_email", ""),
            "viewer_ip": activity.metadata.get("viewer_ip", ""),
            "user_agent": activity.metadata.get("user_agent", ""),
        }


# --- AI tools --------------------------------------------------------------

class AiSummaryTool(_SimpleLogTool):
    activity_type = "ai_summary"
    label = _("AI Summary")
    icon = "SparklesIcon"
    category = "ai"
    default_visibility = "secondary"
    schema_properties = {
        "content_text": {"type": "string", "title": "Summary"},
        "model": {"type": "string", "title": "Model"},
        "prompt_version": {"type": "string", "title": "Prompt Version"},
        "source_activity_ids": {
            "type": "array",
            "items": {"type": "string"},
            "title": "Source Activities",
        },
    }
    required_fields = ["content_text"]
    payload_fields = ["model", "prompt_version", "source_activity_ids"]


class AiSuggestedActionTool(_SimpleLogTool):
    activity_type = "ai_suggested_action"
    label = _("AI Suggested Action")
    icon = "LightBulbIcon"
    category = "ai"
    default_visibility = "secondary"
    schema_properties = {
        "content_text": {"type": "string", "title": "Suggestion"},
        "model": {"type": "string", "title": "Model"},
        "prompt_version": {"type": "string", "title": "Prompt Version"},
        "suggested_action": {"type": "string", "title": "Suggested Action"},
        "confidence": {
            "type": "number",
            "title": "Confidence",
            "minimum": 0,
            "maximum": 1,
        },
    }
    required_fields = ["suggested_action"]
    payload_fields = ["model", "prompt_version", "suggested_action", "confidence"]


# --- System Note -----------------------------------------------------------

class SystemNoteTool(_SimpleLogTool):
    """
    Generic system-generated note (no user-facing composer).

    Examples: "Imported from CSV", "Migrated from Pipedrive",
    "Auto-merged duplicate".  Surfaces ``source`` so the timeline can group
    or filter by origin.
    """

    activity_type = "system_note"
    label = _("System Note")
    icon = "InformationCircleIcon"
    category = "system"
    default_visibility = "secondary"
    schema_properties = {
        "content_text": {"type": "string", "title": "Note"},
        "source": {"type": "string", "title": "Source"},
        "code": {"type": "string", "title": "Code"},
    }
    required_fields = ["content_text"]
    payload_fields = ["source", "code"]


# --- Tags ------------------------------------------------------------------

class TagAddedTool(_SimpleLogTool):
    activity_type = "tag_added"
    label = _("Tag Added")
    icon = "TagIcon"
    category = "system"
    default_visibility = "secondary"
    schema_properties = {
        "tag": {"type": "string", "title": "Tag"},
    }
    required_fields = ["tag"]


class TagRemovedTool(_SimpleLogTool):
    activity_type = "tag_removed"
    label = _("Tag Removed")
    icon = "TagIcon"
    category = "system"
    default_visibility = "secondary"
    schema_properties = {
        "tag": {"type": "string", "title": "Tag"},
    }
    required_fields = ["tag"]


# --- Mention ---------------------------------------------------------------

class MentionTool(StreamlineTool):
    """
    Standalone "you were mentioned" activity.

    Distinct from a comment that incidentally contains a mention — this tool
    is the explicit, primary record of the mention, with a side-effect of
    creating a ``Notification`` for the mentioned user.
    """

    activity_type = "mention"
    label = _("Mention")
    icon = "AtSymbolIcon"
    category = "communication"
    default_visibility = "important"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content_text": {"type": "string", "title": "Context"},
                "mentioned_user_id": {
                    "type": "string",
                    "title": "Mentioned User ID",
                },
                "source_activity_id": {
                    "type": "string",
                    "title": "Source Activity ID",
                },
            },
            "required": ["mentioned_user_id"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        from crm.models import Notification
        from django.contrib.auth import get_user_model

        firm = context["firm"]
        actor = context.get("user")
        metadata = payload.get("metadata", {}) or {}
        mentioned_id = metadata.get("mentioned_user_id")
        if not mentioned_id:
            return

        _User = get_user_model()
        try:
            mentioned_user = (
                _User.objects.filter(id=str(mentioned_id), memberships__firm=firm)
                .distinct()
                .first()
            )
        except Exception:
            mentioned_user = None
        if mentioned_user is None or (actor and mentioned_user.id == actor.id):
            return

        Notification.objects.create(
            firm=firm,
            user=mentioned_user,
            event="activity.mention",
            payload={
                "activity_id": str(activity.id),
                "entity_type": activity.entity_type,
                "entity_id": activity.entity_id,
                "entity_title": context.get("entity_title", ""),
                "by_user": getattr(actor, "full_name", None)
                or (actor.email if actor else None),
                "content_preview": activity.content_text[:_MENTION_PREVIEW_LENGTH],
            },
        )

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "mentioned_user_id": activity.metadata.get("mentioned_user_id", ""),
            "source_activity_id": activity.metadata.get("source_activity_id", ""),
        }


# --- Pin / Unpin -----------------------------------------------------------

class PinnedTool(_SimpleLogTool):
    activity_type = "pinned"
    label = _("Pinned")
    icon = "BookmarkIcon"
    category = "system"
    default_visibility = "secondary"
    schema_properties = {
        "target_activity_id": {"type": "string", "title": "Pinned Activity ID"},
        "reason": {"type": "string", "title": "Reason"},
    }
    required_fields = ["target_activity_id"]


class UnpinnedTool(_SimpleLogTool):
    activity_type = "unpinned"
    label = _("Unpinned")
    icon = "BookmarkSlashIcon"
    category = "system"
    default_visibility = "secondary"
    schema_properties = {
        "target_activity_id": {"type": "string", "title": "Unpinned Activity ID"},
        "reason": {"type": "string", "title": "Reason"},
    }
    required_fields = ["target_activity_id"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trigger_email_task(activity: "Activity") -> None:
    """Fire-and-forget Celery task for sending outbound emails."""
    try:
        from crm.tasks import send_activity_email
        send_activity_email.delay(str(activity.id))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Convenience: list of all built-in tool instances for bulk registration
# ---------------------------------------------------------------------------

BUILTIN_TOOLS: list[StreamlineTool] = [
    CommentTool(),
    CallTool(),
    MeetingTool(),
    EmailOutTool(),
    EmailInTool(),
    StatusChangeTool(),
    FileUploadTool(),
    TaskCreatedTool(),
    TaskAssignedTool(),
    TaskCompletedTool(),
    TaskArchivedTool(),
    SubTaskAddedTool(),
    PriorityChangeTool(),
    AssigneeChangeTool(),
    DueDateChangeTool(),
    ApprovalRequestedTool(),
    ApprovalResolvedTool(),
    TimeLoggedTool(),
    ChecklistItemCheckedTool(),
    VoiceMemoTool(),
    ProposalCreatedTool(),
    ProposalAcceptedTool(),
    ProposalRejectedTool(),
    EntityChangeTool(),
    # Phase 6 — bonus tools
    SmsOutTool(),
    SmsInTool(),
    WhatsAppOutTool(),
    WhatsAppInTool(),
    ChatTool(),
    MeetingScheduledTool(),
    CallScheduledTool(),
    LinkTool(),
    PaymentReceivedTool(),
    InvoiceSentTool(),
    SignatureRequestedTool(),
    SignatureCompletedTool(),
    ProposalViewedTool(),
    AiSummaryTool(),
    AiSuggestedActionTool(),
    SystemNoteTool(),
    TagAddedTool(),
    TagRemovedTool(),
    MentionTool(),
    PinnedTool(),
    UnpinnedTool(),
]
