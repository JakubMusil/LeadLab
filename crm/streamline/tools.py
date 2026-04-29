from __future__ import annotations

from typing import Any, TYPE_CHECKING

from crm.streamline.base import StreamlineTool

if TYPE_CHECKING:
    from crm.models import Activity


_MENTION_PREVIEW_LENGTH = 120


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------

class CommentTool(StreamlineTool):
    activity_type = "comment"
    label = "Comment"
    icon = "ChatBubbleLeftIcon"

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
    label = "Call"
    icon = "PhoneIcon"

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
    label = "Meeting"
    icon = "UsersIcon"

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
    label = "Email (Outbound)"
    icon = "PaperAirplaneIcon"

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
    label = "Email (Inbound)"
    icon = "InboxArrowDownIcon"

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
    label = "Status Change"
    icon = "ArrowsRightLeftIcon"

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
        from crm.models import LeadStatus, LeadStatusHistory

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
        LeadStatusHistory.objects.create(
            lead=lead,
            from_status=old_status,
            to_status=new_status,
            changed_at=activity.created_at,
            changed_by=context["user"],
        )

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
    label = "File Upload"
    icon = "PaperClipIcon"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "title": "Filename"},
                "url": {"type": "string", "format": "uri", "title": "URL"},
                "size_bytes": {
                    "type": "integer",
                    "title": "Size (bytes)",
                    "minimum": 0,
                },
            },
            "required": ["url"],
        }

    def process_action(
        self, activity: "Activity", entity: Any, payload: dict, context: dict
    ) -> None:
        pass

    def render_payload(self, activity: "Activity") -> dict:
        return {
            "filename": activity.metadata.get("filename", ""),
            "url": activity.metadata.get("url", ""),
            "size_bytes": activity.metadata.get("size_bytes", 0),
        }


# ---------------------------------------------------------------------------
# Task Assigned
# ---------------------------------------------------------------------------

class TaskAssignedTool(StreamlineTool):
    activity_type = "task_assigned"
    label = "Task Assigned"
    icon = "ClipboardDocumentListIcon"

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
    label = "Task Completed"
    icon = "CheckCircleIcon"

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
    label = "Proposal Created"
    icon = "DocumentTextIcon"

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
    label = "Proposal Accepted"
    icon = "DocumentCheckIcon"

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
    label = "Proposal Rejected"
    icon = "DocumentTextIcon"

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
    label = "Field Changed"
    icon = "PencilSquareIcon"

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
    TaskAssignedTool(),
    TaskCompletedTool(),
    ProposalCreatedTool(),
    ProposalAcceptedTool(),
    ProposalRejectedTool(),
    EntityChangeTool(),
]
