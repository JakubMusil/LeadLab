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
# Priority Change
# ---------------------------------------------------------------------------

class PriorityChangeTool(StreamlineTool):
    activity_type = "priority_change"
    label = "Priority Change"
    icon = "FlagIcon"

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
    label = "Assignee Change"
    icon = "UserCircleIcon"

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
    label = "Due Date Change"
    icon = "CalendarIcon"

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
    label = "Sub-task Added"
    icon = "Squares2X2Icon"

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
    label = "Task Created"
    icon = "PlusCircleIcon"

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
    label = "Task Archived"
    icon = "ArchiveBoxIcon"

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
    label = "Approval Requested"
    icon = "ShieldExclamationIcon"

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
    label = "Approval Resolved"
    icon = "ShieldCheckIcon"

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
    label = "Time Logged"
    icon = "ClockIcon"

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
    label = "Checklist Item Checked"
    icon = "CheckIcon"

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
    label = "Voice Memo"
    icon = "MicrophoneIcon"

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
]
