from django.db import connection
from django.test import TestCase
from django.utils import timezone
import datetime as dt
from decimal import Decimal
from unittest.mock import patch

from crm.models import (
    Activity,
    ActivityType,
    Category,
    CategoryField,
    ConditionEffectType,
    ConditionRule,
    ConditionScopeType,
    ConditionSeverity,
    ConditionTriggerType,
    ContactType,
    Customer,
    PipelineRecord,
    Proposal,
    RecordSource,
    RecordStatus,
    RuleEvaluationLog,
    RuleEvaluationResult,
    Stage,
    StageRequirement,
    StageScenario,
    Task,
)
from firms.models import Firm, Membership, InvitationRole, PermissionAuditLog
from users.models import User


class CRMFixtureMixin:
    """Mixin that sets up a firm with an owner and a worker."""

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@crm.com", password="pass")
        self.worker = User.objects.create_user(email="worker@crm.com", password="pass")
        self.firm = Firm.objects.create(name="CRM Firm", subscription_tier="pro")
        Membership.objects.create(user=self.owner, firm=self.firm, role=InvitationRole.OWNER)
        Membership.objects.create(user=self.worker, firm=self.firm, role=InvitationRole.MEMBER)

        self.customer = Customer.objects.create(
            firm=self.firm,
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )
        self.record = PipelineRecord.objects.create(
            firm=self.firm,
            customer=self.customer,
            title="Demo Deal",
            status=RecordStatus.NEW,
            source=RecordSource.WEB,
        )


class CustomerModelTest(CRMFixtureMixin, TestCase):
    def test_customer_str(self):
        self.assertIn("Jane", str(self.customer))

    def test_customer_firm_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm")
        other_customer = Customer.objects.create(firm=other_firm, first_name="Bob")
        self.assertEqual(Customer.objects.filter(firm=self.firm).count(), 1)
        self.assertEqual(Customer.objects.filter(firm=other_firm).count(), 1)
        self.assertNotEqual(self.customer.firm, other_customer.firm)

    def test_customer_tags_default_empty_list(self):
        self.assertEqual(self.customer.tags, [])

    def test_customer_metadata_default_empty_dict(self):
        self.assertEqual(self.customer.metadata, {})


class RecordModelTest(CRMFixtureMixin, TestCase):
    def test_record_str(self):
        self.assertIn("Demo Deal", str(self.record))

    def test_record_default_status(self):
        record = PipelineRecord.objects.create(firm=self.firm, title="Quick PipelineRecord")
        self.assertEqual(record.status, RecordStatus.NEW)

    def test_record_nullable_customer(self):
        record = PipelineRecord.objects.create(firm=self.firm, title="Quick Entry")
        self.assertIsNone(record.customer)

    def test_record_choices(self):
        valid_statuses = [s.value for s in RecordStatus]
        self.assertIn(self.record.status, valid_statuses)

    def test_record_firm_isolation(self):
        other_firm = Firm.objects.create(name="Isolate Firm")
        PipelineRecord.objects.create(firm=other_firm, title="Other PipelineRecord")
        self.assertEqual(PipelineRecord.objects.filter(firm=self.firm).count(), 1)


class ActivityModelTest(CRMFixtureMixin, TestCase):
    def test_create_comment_activity(self):
        activity = Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=ActivityType.COMMENT,
            content_text="First contact made.",
        )
        self.assertEqual(activity.type, ActivityType.COMMENT)
        self.assertEqual(activity.record, self.record)

    def test_create_status_change_activity(self):
        activity = Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=ActivityType.STATUS_CHANGE,
            metadata={"old_status": "new", "new_status": "contacted"},
        )
        self.assertEqual(activity.metadata["old_status"], "new")
        self.assertEqual(activity.metadata["new_status"], "contacted")

    def test_create_email_out_activity(self):
        activity = Activity.objects.create(
            record=self.record,
            user=self.worker,
            type=ActivityType.EMAIL_OUT,
            content_text="Hi Jane, following up...",
            metadata={"subject": "Follow-up", "to": "jane@example.com"},
        )
        self.assertEqual(activity.metadata["subject"], "Follow-up")

    def test_activities_ordered_newest_first(self):
        a1 = Activity.objects.create(record=self.record, type=ActivityType.COMMENT, content_text="A1")
        a2 = Activity.objects.create(record=self.record, type=ActivityType.CALL, content_text="A2")
        activities = list(Activity.objects.filter(record=self.record))
        self.assertEqual(activities[0].pk, a2.pk)  # newest first

    def test_activity_str(self):
        activity = Activity.objects.create(
            record=self.record, type=ActivityType.COMMENT, content_text="test"
        )
        self.assertIn("Comment", str(activity))

    def test_activity_record_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm 2")
        other_record = PipelineRecord.objects.create(firm=other_firm, title="Other PipelineRecord")
        Activity.objects.create(record=other_record, type=ActivityType.COMMENT, content_text="x")
        self.assertEqual(Activity.objects.filter(record=self.record).count(), 0)


class TaskModelTest(CRMFixtureMixin, TestCase):
    def test_create_task(self):
        task = Task.objects.create(
            firm=self.firm,
            record=self.record,
            assigned_to=self.worker,
            title="Send proposal",
        )
        self.assertFalse(task.is_completed)
        self.assertIsNone(task.completed_at)

    def test_complete_task(self):
        task = Task.objects.create(firm=self.firm, record=self.record, title="Call back")
        task.is_completed = True
        task.completed_at = timezone.now()
        task.save()
        task.refresh_from_db()
        self.assertTrue(task.is_completed)
        self.assertIsNotNone(task.completed_at)

    def test_task_str(self):
        task = Task.objects.create(firm=self.firm, record=self.record, title="Follow up")
        self.assertIn("Follow up", str(task))
        self.assertIn("○", str(task))
        task.is_completed = True
        task.save()
        self.assertIn("✓", str(task))


# ---------------------------------------------------------------------------
# Streamline Tools (Phase 0 + 1) — schema / render / side-effects
# ---------------------------------------------------------------------------

class StreamlineToolsTest(CRMFixtureMixin, TestCase):
    """Validate every registered StreamlineTool exposes a sane schema and
    correctly renders its tool_payload.  Phase 0 + 1 unification."""

    def _build_activity(self, type_value, metadata=None, **kwargs):
        return Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=type_value,
            metadata=metadata or {},
            **kwargs,
        )

    def test_all_builtin_tools_registered(self):
        from crm.streamline.registry import all_tools, get_tool
        registered_types = {t.activity_type for t in all_tools()}
        expected_new = {
            "priority_change", "assignee_change", "due_date_change",
            "task_created", "task_archived",
            "approval_requested", "approval_resolved", "time_logged",
            "voice_memo",
            "streamline_items_added", "streamline_item_resolved", "streamline_item_reopened",
        }
        self.assertTrue(expected_new.issubset(registered_types))
        # All registered tools also have a schema
        for at in registered_types:
            tool = get_tool(at)
            self.assertIsNotNone(tool)
            schema = tool.get_schema()
            self.assertIsInstance(schema, dict)
            self.assertEqual(schema.get("type"), "object")

    def test_activity_is_internal_default_false(self):
        """Newly created activities default to is_internal=False."""
        a = self._build_activity(ActivityType.COMMENT, content_text="public note")
        self.assertFalse(a.is_internal)

    def test_activity_is_internal_persisted(self):
        """is_internal=True round-trips through the DB."""
        a = self._build_activity(
            ActivityType.COMMENT, content_text="internal-only", is_internal=True,
        )
        a.refresh_from_db()
        self.assertTrue(a.is_internal)
        # Filter index works (smoke).
        self.assertEqual(
            Activity.objects.filter(record=self.record, is_internal=True).count(), 1,
        )

    # ------------------------------------------------------------------
    # F-3 — validate_payload unit tests (tool-independent edge cases)
    # ------------------------------------------------------------------

    def test_validate_payload_unknown_type_is_noop(self):
        """Unknown activity types short-circuit cleanly (no exception)."""
        from crm.streamline.validation import validate_payload
        # Must not raise — caller (create_activity) handles unknown types.
        validate_payload("definitely_not_a_tool", "", {})

    def test_validate_payload_invalid_schema_is_noop(self):
        """If a tool's schema is malformed we log and skip rather than 500."""
        from crm.streamline.registry import _tool_registry
        from crm.streamline.validation import validate_payload
        from crm.streamline.base import StreamlineTool

        class BrokenTool(StreamlineTool):
            activity_type = "broken_test_tool"
            label = "Broken"
            icon = "X"

            def get_schema(self):
                # "type" must be a string or array of strings — not an int.
                return {"type": 123}

            def process_action(self, *a, **k):
                pass

            def render_payload(self, *a, **k):
                return {}

        original = _tool_registry.get("broken_test_tool")
        _tool_registry["broken_test_tool"] = BrokenTool()
        try:
            # Should NOT raise.
            validate_payload("broken_test_tool", "anything", {"x": 1})
        finally:
            if original is None:
                _tool_registry.pop("broken_test_tool", None)
            else:
                _tool_registry["broken_test_tool"] = original

    def test_validate_payload_message_includes_field_path(self):
        """Validation errors mention the offending JSON path."""
        from crm.streamline.validation import (
            PayloadValidationError, validate_payload,
        )
        with self.assertRaises(PayloadValidationError) as cm:
            validate_payload("status_change", "", {})
        self.assertIn("status_change", str(cm.exception))
        self.assertIn("new_status", str(cm.exception))

    def test_priority_change_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.PRIORITY_CHANGE,
            metadata={"old_priority": "low", "new_priority": "high"},
        )
        out = get_tool("priority_change").render_payload(a)
        self.assertEqual(out["new_priority"], "high")
        self.assertEqual(out["old_priority"], "low")

    def test_due_date_change_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.DUE_DATE_CHANGE,
            metadata={"old_due_date": "2024-01-01", "new_due_date": "2024-02-01"},
        )
        out = get_tool("due_date_change").render_payload(a)
        self.assertEqual(out["new_due_date"], "2024-02-01")

    def test_streamline_items_added_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.STREAMLINE_ITEMS_ADDED,
            metadata={"count": 3, "items": ["Buy milk", "Call Alice", "Fix bug"], "kind": "todo"},
        )
        out = get_tool("streamline_items_added").render_payload(a)
        self.assertEqual(out["count"], 3)
        self.assertEqual(out["kind"], "todo")

    def test_task_created_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.TASK_CREATED,
            metadata={"task_id": "t1", "task_title": "T"},
        )
        out = get_tool("task_created").render_payload(a)
        self.assertEqual(out["task_title"], "T")

    def test_task_archived_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.TASK_ARCHIVED,
            metadata={"task_id": "t1", "task_title": "T", "archived": True},
        )
        out = get_tool("task_archived").render_payload(a)
        self.assertTrue(out["archived"])

    def test_approval_resolved_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.APPROVAL_RESOLVED,
            metadata={"decision": "accepted", "approver_name": "Alice"},
        )
        out = get_tool("approval_resolved").render_payload(a)
        self.assertEqual(out["decision"], "accepted")

    def test_time_logged_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.TIME_LOGGED,
            metadata={"minutes": 45, "description": "Pair programming"},
        )
        out = get_tool("time_logged").render_payload(a)
        self.assertEqual(out["minutes"], 45)

    def test_streamline_item_resolved_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.STREAMLINE_ITEM_RESOLVED,
            metadata={"item_text": "Buy milk", "resolved": True, "kind": "todo"},
        )
        out = get_tool("streamline_item_resolved").render_payload(a)
        self.assertTrue(out["resolved"])
        self.assertEqual(out["item_text"], "Buy milk")

    def test_voice_memo_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.VOICE_MEMO,
            metadata={"url": "/m/v.webm", "duration_seconds": 17, "transcript": "hello"},
        )
        out = get_tool("voice_memo").render_payload(a)
        self.assertEqual(out["duration_seconds"], 17)
        self.assertEqual(out["url"], "/m/v.webm")

    def test_assignee_change_creates_notification_for_new_assignee(self):
        from crm.models import Notification
        from crm.streamline.registry import get_tool

        activity = self._build_activity(
            ActivityType.ASSIGNEE_CHANGE,
            metadata={
                "old_assignee_id": str(self.owner.id),
                "new_assignee_id": str(self.worker.id),
            },
        )
        tool = get_tool("assignee_change")
        tool.process_action(
            activity,
            self.record,
            {"metadata": {
                "old_assignee_id": str(self.owner.id),
                "new_assignee_id": str(self.worker.id),
            }},
            {"firm": self.firm, "user": self.owner, "entity_title": self.record.title},
        )
        self.assertEqual(
            Notification.objects.filter(
                user=self.worker, event="activity.assigned"
            ).count(),
            1,
        )

    def test_assignee_change_does_not_notify_self(self):
        from crm.models import Notification
        from crm.streamline.registry import get_tool

        activity = self._build_activity(
            ActivityType.ASSIGNEE_CHANGE,
            metadata={"new_assignee_id": str(self.owner.id)},
        )
        get_tool("assignee_change").process_action(
            activity,
            self.record,
            {"metadata": {"new_assignee_id": str(self.owner.id)}},
            {"firm": self.firm, "user": self.owner, "entity_title": ""},
        )
        self.assertEqual(
            Notification.objects.filter(event="activity.assigned").count(), 0
        )


class StreamlinePhase6ToolsTest(CRMFixtureMixin, TestCase):
    """Phase 6 — bonus Streamline tools (SMS / WhatsApp / Chat / Meeting
    Scheduled / Link / Payment / Invoice / Signature / Proposal Viewed /
    AI / System Note / Tag / Mention / Pin)."""

    def _build_activity(self, type_value, metadata=None, **kwargs):
        return Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=type_value,
            metadata=metadata or {},
            **kwargs,
        )

    def test_phase6_tools_registered(self):
        from crm.streamline.registry import all_tools
        registered = {t.activity_type for t in all_tools()}
        expected = {
            "sms_out", "sms_in", "whatsapp_out", "whatsapp_in", "chat",
            "meeting_scheduled", "link",
            "payment_received", "invoice_sent",
            "signature_requested", "signature_completed",
            "proposal_viewed",
            "ai_summary", "ai_suggested_action",
            "system_note",
            "tag_added", "tag_removed",
            "mention",
            "pinned", "unpinned",
        }
        self.assertTrue(expected.issubset(registered))

    def test_phase6_schemas_are_well_formed(self):
        from crm.streamline.registry import get_tool
        for at in [
            "sms_out", "sms_in", "whatsapp_out", "whatsapp_in", "chat",
            "meeting_scheduled", "link", "payment_received", "invoice_sent",
            "signature_requested", "signature_completed", "proposal_viewed",
            "ai_summary", "ai_suggested_action", "system_note",
            "tag_added", "tag_removed", "mention", "pinned", "unpinned",
        ]:
            tool = get_tool(at)
            self.assertIsNotNone(tool, f"{at} not registered")
            schema = tool.get_schema()
            self.assertEqual(schema.get("type"), "object")
            self.assertIn("properties", schema)

    def test_sms_out_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.SMS_OUT,
            metadata={
                "to": "+420777111222",
                "from_number": "+420555000111",
                "provider_message_id": "twilio_abc",
            },
        )
        out = get_tool("sms_out").render_payload(a)
        self.assertEqual(out["to"], "+420777111222")
        self.assertEqual(out["provider_message_id"], "twilio_abc")

    def test_link_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.LINK,
            metadata={
                "url": "https://example.com",
                "title": "Example",
                "description": "An example link",
                "thumbnail_url": "https://example.com/og.png",
            },
        )
        out = get_tool("link").render_payload(a)
        self.assertEqual(out["url"], "https://example.com")
        self.assertEqual(out["title"], "Example")

    def test_invoice_sent_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.INVOICE_SENT,
            metadata={
                "invoice_id": "inv_42",
                "invoice_number": "2026-001",
                "amount": 1500,
                "currency": "CZK",
                "due_date": "2026-05-15",
            },
        )
        out = get_tool("invoice_sent").render_payload(a)
        self.assertEqual(out["invoice_id"], "inv_42")
        self.assertEqual(out["amount"], 1500)
        self.assertEqual(out["currency"], "CZK")

    def test_system_note_render_filters_to_metadata_keys(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.SYSTEM_NOTE,
            metadata={"source": "csv_import", "code": "imported"},
        )
        out = get_tool("system_note").render_payload(a)
        self.assertEqual(out, {"source": "csv_import", "code": "imported"})

    def test_tag_added_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.TAG_ADDED, metadata={"tag": "vip"}
        )
        self.assertEqual(get_tool("tag_added").render_payload(a)["tag"], "vip")

    def test_proposal_viewed_stamps_first_viewed_at(self):
        from crm.models import Proposal
        from crm.streamline.registry import get_tool

        proposal = Proposal.objects.create(
            firm=self.firm,
            record=self.record,
            title="Test Proposal",
        )
        self.assertIsNone(proposal.first_viewed_at)
        previous_count = proposal.view_count or 0

        activity = Activity.objects.create(
            proposal=proposal,
            type=ActivityType.PROPOSAL_VIEWED,
            metadata={"proposal_id": str(proposal.id)},
        )
        get_tool("proposal_viewed").process_action(
            activity, proposal, {"metadata": {}},
            {"firm": self.firm, "user": self.owner, "entity_title": proposal.title},
        )
        proposal.refresh_from_db()
        self.assertIsNotNone(proposal.first_viewed_at)
        self.assertEqual(proposal.view_count, previous_count + 1)

    def test_proposal_viewed_does_not_overwrite_first_viewed_at(self):
        from crm.models import Proposal
        from crm.streamline.registry import get_tool
        from django.utils import timezone
        from datetime import timedelta

        original = timezone.now() - timedelta(days=3)
        proposal = Proposal.objects.create(
            firm=self.firm,
            record=self.record,
            title="Test",
            first_viewed_at=original,
            view_count=5,
        )
        activity = Activity.objects.create(
            proposal=proposal,
            type=ActivityType.PROPOSAL_VIEWED,
            metadata={},
        )
        get_tool("proposal_viewed").process_action(
            activity, proposal, {"metadata": {}},
            {"firm": self.firm, "user": self.owner, "entity_title": ""},
        )
        proposal.refresh_from_db()
        self.assertEqual(proposal.first_viewed_at, original)
        self.assertEqual(proposal.view_count, 6)

    def test_mention_tool_creates_notification(self):
        from crm.models import Notification
        from crm.streamline.registry import get_tool

        activity = self._build_activity(
            ActivityType.MENTION,
            metadata={"mentioned_user_id": str(self.worker.id)},
            content_text="Hey @worker — please look at this",
        )
        get_tool("mention").process_action(
            activity,
            self.record,
            {"metadata": {"mentioned_user_id": str(self.worker.id)}},
            {"firm": self.firm, "user": self.owner, "entity_title": self.record.title},
        )
        self.assertEqual(
            Notification.objects.filter(
                user=self.worker, event="activity.mention"
            ).count(),
            1,
        )

    def test_mention_tool_does_not_notify_self(self):
        from crm.models import Notification
        from crm.streamline.registry import get_tool

        activity = self._build_activity(
            ActivityType.MENTION,
            metadata={"mentioned_user_id": str(self.owner.id)},
        )
        get_tool("mention").process_action(
            activity,
            self.record,
            {"metadata": {"mentioned_user_id": str(self.owner.id)}},
            {"firm": self.firm, "user": self.owner, "entity_title": ""},
        )
        self.assertEqual(
            Notification.objects.filter(event="activity.mention").count(), 0
        )


class ActivityTaskLinkTest(CRMFixtureMixin, TestCase):
    """Phase 0 — Activity can now be linked to a Task entity."""

    def test_activity_can_be_linked_to_task(self):
        task = Task.objects.create(firm=self.firm, record=self.record, title="T")
        a = Activity.objects.create(
            task=task,
            user=self.owner,
            type=ActivityType.COMMENT,
            content_text="Note on task",
        )
        self.assertEqual(a.entity_type, "task")
        self.assertEqual(a.entity_id, str(task.id))
        self.assertEqual(task.activities.count(), 1)


class ActivityReactionModelTest(CRMFixtureMixin, TestCase):
    def test_create_and_unique_per_user_emoji(self):
        from crm.models import ActivityReaction
        a = Activity.objects.create(
            record=self.record, user=self.owner, type=ActivityType.COMMENT, content_text="x"
        )
        ActivityReaction.objects.create(activity=a, user=self.owner, emoji="👍")
        # Same user, same emoji → unique constraint should kick in
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ActivityReaction.objects.create(activity=a, user=self.owner, emoji="👍")
        # Different emoji is fine
        ActivityReaction.objects.create(activity=a, user=self.owner, emoji="❤️")
        self.assertEqual(a.reactions.count(), 2)


# ---------------------------------------------------------------------------
# CRM API integration tests
# ---------------------------------------------------------------------------

import json


class CRMAPIFixtureMixin:
    """Sets up two users, a firm with owner + worker, a customer and a record."""

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@crm-api.com", password="pass")
        self.worker = User.objects.create_user(email="worker@crm-api.com", password="pass")
        self.firm = Firm.objects.create(name="CRM API Firm", subscription_tier="pro")
        self.owner_membership = Membership.objects.create(
            user=self.owner, firm=self.firm, role=InvitationRole.OWNER
        )
        self.worker_membership = Membership.objects.create(
            user=self.worker, firm=self.firm, role=InvitationRole.MEMBER
        )
        self.customer = Customer.objects.create(
            firm=self.firm,
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            phone="123456",
            company_name="Acme",
            tags=["vip"],
        )
        self.record = PipelineRecord.objects.create(
            firm=self.firm,
            customer=self.customer,
            title="Test PipelineRecord",
            status=RecordStatus.NEW,
            source=RecordSource.WEB,
        )
        self.client.login(username="owner@crm-api.com", password="pass")

    def firm_headers(self):
        return {"HTTP_X_FIRM_ID": str(self.firm.id)}

    def _get(self, url, data=None):
        return self.client.get(url, data or {}, **self.firm_headers())

    def _post(self, url, data):
        return self.client.post(
            url, data=json.dumps(data), content_type="application/json",
            **self.firm_headers(),
        )

    def _put(self, url, data):
        return self.client.put(
            url, data=json.dumps(data), content_type="application/json",
            **self.firm_headers(),
        )

    def _patch(self, url, data):
        return self.client.patch(
            url, data=json.dumps(data), content_type="application/json",
            **self.firm_headers(),
        )

    def _delete(self, url):
        return self.client.delete(url, content_type="application/json", **self.firm_headers())


class NotificationsMarkReadAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/notifications/mark-read"

    def _make_notification(self):
        from crm.models import Notification
        return Notification.objects.create(
            firm=self.firm,
            user=self.owner,
            event="task.completed",
            payload={"title": "Demo"},
            is_read=False,
        )

    def test_mark_read_accepts_ids_object_payload(self):
        n1 = self._make_notification()
        n2 = self._make_notification()

        resp = self._post(self.URL, {"ids": [str(n1.id)]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["updated"], 1)

        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertFalse(n2.is_read)

    def test_mark_read_with_empty_body_marks_all(self):
        n1 = self._make_notification()
        n2 = self._make_notification()

        resp = self._post(self.URL, {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["updated"], 2)

        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertTrue(n2.is_read)


# -- Customers ---------------------------------------------------------------

class CustomerListAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/directory"

    def test_list_customers_returns_firm_customers(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["first_name"], "Jane")

    def test_list_customers_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm")
        Customer.objects.create(firm=other_firm, first_name="Bob")
        resp = self._get(self.URL)
        self.assertEqual(len(resp.json()), 1)  # only Jane

    def test_search_by_first_name(self):
        resp = self._get(self.URL, {"search": "Jane"})
        self.assertEqual(len(resp.json()), 1)

    def test_search_by_last_name(self):
        resp = self._get(self.URL, {"search": "Doe"})
        self.assertEqual(len(resp.json()), 1)

    def test_search_by_email(self):
        resp = self._get(self.URL, {"search": "jane@"})
        self.assertEqual(len(resp.json()), 1)

    def test_search_by_company_name(self):
        resp = self._get(self.URL, {"search": "Acme"})
        self.assertEqual(len(resp.json()), 1)

    def test_search_by_phone(self):
        resp = self._get(self.URL, {"search": "123456"})
        self.assertEqual(len(resp.json()), 1)

    def test_search_no_match_returns_empty(self):
        resp = self._get(self.URL, {"search": "ZZZNOMATCH"})
        self.assertEqual(len(resp.json()), 0)

    def test_pagination_page_size(self):
        # Create 5 more customers
        for i in range(5):
            Customer.objects.create(firm=self.firm, first_name=f"User{i}")
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)

    def test_pagination_second_page(self):
        for i in range(5):
            Customer.objects.create(firm=self.firm, first_name=f"User{i}")
        resp1 = self._get(self.URL, {"page": 1, "page_size": 3})
        resp2 = self._get(self.URL, {"page": 2, "page_size": 3})
        ids1 = {c["id"] for c in resp1.json()}
        ids2 = {c["id"] for c in resp2.json()}
        self.assertTrue(ids1.isdisjoint(ids2))

    def test_requires_firm_header(self):
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, [403, 401])


class CustomerCreateAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/directory"

    def test_create_customer_returns_201(self):
        resp = self._post(self.URL, {"first_name": "Bob", "last_name": "Smith"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["first_name"], "Bob")
        self.assertTrue(Customer.objects.filter(firm=self.firm, first_name="Bob").exists())

    def test_create_customer_worker_allowed(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._post(self.URL, {"first_name": "Worker", "last_name": "Create"})
        self.assertEqual(resp.status_code, 201)

    def test_create_customer_unauthenticated_returns_error(self):
        self.client.logout()
        resp = self._post(self.URL, {"first_name": "Anon"})
        self.assertIn(resp.status_code, [401, 403])


class CustomerGetAPITest(CRMAPIFixtureMixin, TestCase):
    def test_get_existing_customer(self):
        resp = self._get(f"/api/v1/crm/directory/{self.customer.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email"], "jane@example.com")

    def test_get_nonexistent_customer_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/directory/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)

    def test_get_other_firm_customer_returns_404(self):
        other_firm = Firm.objects.create(name="Other")
        other_cust = Customer.objects.create(firm=other_firm, first_name="Eve")
        resp = self._get(f"/api/v1/crm/directory/{other_cust.id}")
        self.assertEqual(resp.status_code, 404)


class CustomerUpdateAPITest(CRMAPIFixtureMixin, TestCase):
    def test_update_customer(self):
        resp = self._put(
            f"/api/v1/crm/directory/{self.customer.id}",
            {"first_name": "Janet", "last_name": "Doe", "email": "janet@example.com",
             "phone": "", "company_name": "", "tags": [], "metadata": {}},
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Janet")

    def test_update_nonexistent_customer_returns_404(self):
        import uuid
        resp = self._put(
            f"/api/v1/crm/directory/{uuid.uuid4()}",
            {"first_name": "X", "last_name": "", "email": "", "phone": "",
             "company_name": "", "tags": [], "metadata": {}},
        )
        self.assertEqual(resp.status_code, 404)


class CustomerDeleteAPITest(CRMAPIFixtureMixin, TestCase):
    def test_delete_customer_admin_succeeds(self):
        resp = self._delete(f"/api/v1/crm/directory/{self.customer.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Customer.objects.filter(id=self.customer.id).exists())

    def test_delete_customer_worker_returns_403(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(f"/api/v1/crm/directory/{self.customer.id}")
        self.assertEqual(resp.status_code, 403)


# -- Records -----------------------------------------------------------------

class RecordListAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/records"

    def test_list_records_returns_firm_records(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_filter_by_status(self):
        PipelineRecord.objects.create(firm=self.firm, title="Won PipelineRecord", status=RecordStatus.WON)
        resp = self._get(self.URL, {"status": "won"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "won")

    def test_filter_by_source(self):
        PipelineRecord.objects.create(firm=self.firm, title="Referral PipelineRecord", source=RecordSource.REFERRAL)
        resp = self._get(self.URL, {"source": "referral"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source"], "referral")

    def test_filter_by_tag(self):
        # self.record has customer with tag "vip"
        PipelineRecord.objects.create(firm=self.firm, title="Untagged PipelineRecord")
        resp = self._get(self.URL, {"tag": "vip"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(self.record.id))

    def test_filter_by_created_after(self):
        from django.utils import timezone
        import datetime
        future = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        resp = self._get(self.URL, {"created_after": future})
        self.assertEqual(len(resp.json()), 0)

    def test_filter_by_created_before(self):
        from django.utils import timezone
        import datetime
        past = (timezone.now() - datetime.timedelta(days=1)).isoformat()
        resp = self._get(self.URL, {"created_before": past})
        self.assertEqual(len(resp.json()), 0)

    def test_pagination(self):
        for i in range(5):
            PipelineRecord.objects.create(firm=self.firm, title=f"PipelineRecord {i}")
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm")
        PipelineRecord.objects.create(firm=other_firm, title="Foreign PipelineRecord")
        resp = self._get(self.URL)
        self.assertEqual(len(resp.json()), 1)


class RecordCreateAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/records"

    def test_create_record_returns_201(self):
        resp = self._post(self.URL, {"title": "New PipelineRecord"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["title"], "New PipelineRecord")

    def test_create_record_with_customer(self):
        resp = self._post(self.URL, {
            "title": "PipelineRecord With Customer",
            "customer_id": str(self.customer.id),
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["customer_id"], str(self.customer.id))

    def test_create_record_invalid_customer_returns_400(self):
        import uuid
        resp = self._post(self.URL, {"title": "Bad", "customer_id": str(uuid.uuid4())})
        self.assertEqual(resp.status_code, 400)

    def test_create_record_worker_allowed(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._post(self.URL, {"title": "Worker PipelineRecord"})
        self.assertEqual(resp.status_code, 201)


class RecordGetAPITest(CRMAPIFixtureMixin, TestCase):
    def test_get_record(self):
        resp = self._get(f"/api/v1/crm/records/{self.record.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Test PipelineRecord")

    def test_get_nonexistent_record_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/records/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)


class RecordUpdateAPITest(CRMAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(firm=self.firm, name="Sales")
        self.stage_new = Stage.objects.create(category=self.category, name="New", order=0)
        self.stage_won = Stage.objects.create(category=self.category, name="Won", order=1)
        self.record.category = self.category
        self.record.current_stage = self.stage_new
        self.record.status = RecordStatus.NEW
        self.record.save(update_fields=["category", "current_stage", "status"])

    def test_patch_record_title(self):
        resp = self._patch(f"/api/v1/crm/records/{self.record.id}", {"title": "Updated"})
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.title, "Updated")

    def test_patch_status_creates_activity(self):
        resp = self._patch(f"/api/v1/crm/records/{self.record.id}", {"status": "contacted"})
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, RecordStatus.CONTACTED)
        self.assertTrue(
            Activity.objects.filter(
                record=self.record, type=ActivityType.STATUS_CHANGE
            ).exists()
        )

    def test_patch_nonexistent_record_returns_404(self):
        import uuid
        resp = self._patch(f"/api/v1/crm/records/{uuid.uuid4()}", {"title": "X"})
        self.assertEqual(resp.status_code, 404)

    def test_stage_change_blocked_returns_400_and_logs(self):
        rule = ConditionRule.objects.create(
            firm=self.firm,
            name="Block move to won",
            trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
            scope_type=ConditionScopeType.STAGE_TRANSITION,
            source_stage=self.stage_new,
            target_stage=self.stage_won,
            condition_tree={"field": "status", "operator": "eq", "value": "new"},
            effect=ConditionEffectType.BLOCK,
            severity=ConditionSeverity.ERROR,
            effect_config={"message": "Missing preconditions"},
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"current_stage_id": str(self.stage_won.id)},
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body.get("code"), "stage_change_blocked")
        self.assertIn("stage_change_evaluation", body)
        self.assertEqual(len(body["stage_change_evaluation"]["requested"]["blocking"]), 1)

        self.record.refresh_from_db()
        self.assertEqual(self.record.current_stage_id, self.stage_new.id)
        self.assertTrue(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
                rule=rule,
                result=RuleEvaluationResult.BLOCKED,
            ).exists()
        )

    def test_stage_change_warning_returns_200_with_evaluation(self):
        ConditionRule.objects.create(
            firm=self.firm,
            name="Warn move to won",
            trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
            scope_type=ConditionScopeType.STAGE_TRANSITION,
            source_stage=self.stage_new,
            target_stage=self.stage_won,
            condition_tree={"field": "status", "operator": "eq", "value": "new"},
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Double-check checklist"},
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"current_stage_id": str(self.stage_won.id)},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("stage_change_evaluation", payload)
        requested_eval = payload["stage_change_evaluation"]["requested"]
        self.assertEqual(len(requested_eval["blocking"]), 0)
        self.assertEqual(len(requested_eval["warnings"]), 1)

        self.record.refresh_from_db()
        self.assertEqual(self.record.current_stage_id, self.stage_won.id)
        self.assertTrue(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
                result=RuleEvaluationResult.WARNING,
            ).exists()
        )

    def test_stage_changed_rules_run_after_successful_change(self):
        changed_rule = ConditionRule.objects.create(
            firm=self.firm,
            name="Post change warning",
            trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGED,
            scope_type=ConditionScopeType.STAGE,
            stage=self.stage_won,
            condition_tree={"field": "status", "operator": "eq", "value": "new"},
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Post change warning"},
        )
        StageScenario.objects.create(
            firm=self.firm,
            category=self.category,
            stage=self.stage_won,
            name="Won scenario",
            activation_condition={},
            is_active=True,
            priority=1,
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"current_stage_id": str(self.stage_won.id)},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        changed_eval = payload["stage_change_evaluation"]["changed"]
        self.assertEqual(len(changed_eval["warnings"]), 1)
        self.assertEqual(changed_eval["warnings"][0]["rule_id"], str(changed_rule.id))

        self.record.refresh_from_db()
        self.assertEqual(self.record.current_stage_id, self.stage_won.id)
        self.assertIn("active_stage_scenario_id", self.record.extra_data)
        self.assertTrue(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGED,
                rule=changed_rule,
                result=RuleEvaluationResult.WARNING,
            ).exists()
        )

    def test_stage_change_block_does_not_trigger_stage_changed_rules(self):
        ConditionRule.objects.create(
            firm=self.firm,
            name="Block move to won",
            trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
            scope_type=ConditionScopeType.STAGE_TRANSITION,
            source_stage=self.stage_new,
            target_stage=self.stage_won,
            condition_tree={"field": "status", "operator": "eq", "value": RecordStatus.NEW},
            effect=ConditionEffectType.BLOCK,
            severity=ConditionSeverity.ERROR,
            effect_config={"message": "Blocked"},
        )
        changed_rule = ConditionRule.objects.create(
            firm=self.firm,
            name="Should not run",
            trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGED,
            scope_type=ConditionScopeType.STAGE,
            stage=self.stage_won,
            condition_tree={},
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Should not be logged"},
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"current_stage_id": str(self.stage_won.id)},
        )
        self.assertEqual(resp.status_code, 400)
        self.record.refresh_from_db()
        self.assertEqual(self.record.current_stage_id, self.stage_new.id)
        self.assertFalse(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGED,
                rule=changed_rule,
            ).exists()
        )

    def test_patch_without_stage_change_does_not_write_stage_logs(self):
        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"title": "Only title update"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type__in=[
                    ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
                    ConditionTriggerType.RECORD_STAGE_CHANGED,
                ],
            ).exists()
        )

    def test_patch_standard_field_change_evaluates_rules_and_logs(self):
        rule = ConditionRule.objects.create(
            firm=self.firm,
            name="Warn title changed",
            trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
            scope_type=ConditionScopeType.FIRM,
            condition_tree={
                "source_type": "field_change",
                "field": "title",
                "operator": "changed_to",
                "value": "Updated by rule",
            },
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Title updated"},
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"title": "Updated by rule"},
        )
        self.assertEqual(resp.status_code, 200)

        payload = resp.json()
        self.assertIn("field_change_evaluation", payload)
        self.assertIn("title", payload["field_change_evaluation"])
        warnings = payload["field_change_evaluation"]["title"]["warnings"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["rule_id"], str(rule.id))

        self.assertTrue(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
                rule=rule,
                result=RuleEvaluationResult.WARNING,
            ).exists()
        )

    def test_patch_same_standard_field_value_does_not_evaluate_field_change(self):
        ConditionRule.objects.create(
            firm=self.firm,
            name="Warn any title change",
            trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
            scope_type=ConditionScopeType.FIRM,
            condition_tree={
                "source_type": "field_change",
                "field": "title",
                "operator": "changed",
            },
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Title changed"},
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"title": self.record.title},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json().get("field_change_evaluation"))
        self.assertFalse(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
            ).exists()
        )

    def test_patch_standard_field_change_refreshes_active_stage_scenario(self):
        scenario = StageScenario.objects.create(
            firm=self.firm,
            category=self.category,
            stage=self.stage_new,
            name="Title scenario",
            activation_condition={
                "field": "title",
                "operator": "eq",
                "value": "Scenario activated",
            },
            is_active=True,
            priority=1,
        )
        requirement = StageRequirement.objects.create(
            firm=self.firm,
            scenario=scenario,
            name="Title is set",
            requirement_type="field",
            condition={"field": "title", "operator": "eq", "value": "Scenario activated"},
            blocking=True,
            visible_to_user=True,
            sort_order=1,
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"title": "Scenario activated"},
        )
        self.assertEqual(resp.status_code, 200)

        self.record.refresh_from_db()
        self.assertIn("active_stage_scenario_id", self.record.extra_data)
        self.assertIn("active_stage_requirements", self.record.extra_data)
        self.assertEqual(len(self.record.extra_data["active_stage_requirements"]), 1)
        self.assertEqual(
            self.record.extra_data["active_stage_requirements"][0]["id"],
            str(requirement.id),
        )
        self.assertTrue(self.record.extra_data["active_stage_requirements"][0]["is_met"])

    def test_patch_standard_field_change_prefers_higher_priority_matching_scenario(self):
        low_priority = StageScenario.objects.create(
            firm=self.firm,
            category=self.category,
            stage=self.stage_new,
            name="Fallback scenario",
            activation_condition={},
            is_active=True,
            priority=50,
        )
        low_req = StageRequirement.objects.create(
            firm=self.firm,
            scenario=low_priority,
            name="Fallback requirement",
            requirement_type="field",
            condition={},
            blocking=False,
            visible_to_user=True,
            sort_order=1,
        )
        high_priority = StageScenario.objects.create(
            firm=self.firm,
            category=self.category,
            stage=self.stage_new,
            name="Branch by title",
            activation_condition={"field": "title", "operator": "eq", "value": "Priority branch"},
            is_active=True,
            priority=1,
        )
        high_req = StageRequirement.objects.create(
            firm=self.firm,
            scenario=high_priority,
            name="Branch requirement",
            requirement_type="field",
            condition={"field": "title", "operator": "eq", "value": "Priority branch"},
            blocking=True,
            visible_to_user=True,
            sort_order=1,
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"title": "Priority branch"},
        )
        self.assertEqual(resp.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(
            self.record.extra_data.get("active_stage_scenario_id"),
            str(high_priority.id),
        )
        self.assertEqual(
            self.record.extra_data.get("active_stage_requirements", [{}])[0].get("id"),
            str(high_req.id),
        )
        self.assertNotEqual(str(low_req.id), str(high_req.id))

    def test_patch_standard_field_change_clears_stage_requirements_when_scenario_not_active(self):
        StageScenario.objects.create(
            firm=self.firm,
            category=self.category,
            stage=self.stage_new,
            name="Title scenario",
            activation_condition={"field": "title", "operator": "eq", "value": "Scenario activated"},
            is_active=True,
            priority=1,
        )
        self.record.extra_data = {
            "active_stage_scenario_id": "stale-id",
            "active_stage_requirements": [{"id": "stale-req", "is_met": True}],
        }
        self.record.save(update_fields=["extra_data"])

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"title": "Different title"},
        )
        self.assertEqual(resp.status_code, 200)

        self.record.refresh_from_db()
        self.assertNotIn("active_stage_scenario_id", self.record.extra_data)
        self.assertNotIn("active_stage_requirements", self.record.extra_data)

    def test_patch_standard_field_change_clears_orphan_stage_requirements_without_scenario_id(self):
        self.record.category = None
        self.record.current_stage = None
        self.record.extra_data = {
            "active_stage_requirements": [{"id": "stale-req", "is_met": True}],
        }
        self.record.save(update_fields=["category", "current_stage", "extra_data"])

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"title": "Different title"},
        )
        self.assertEqual(resp.status_code, 200)

        self.record.refresh_from_db()
        self.assertNotIn("active_stage_requirements", self.record.extra_data)

    def test_patch_category_field_change_evaluates_rules_and_logs(self):
        CategoryField.objects.create(
            category=self.category,
            field_key="notes",
            is_visible=True,
            is_required=False,
            order=1,
        )
        rule = ConditionRule.objects.create(
            firm=self.firm,
            name="Warn category notes changed",
            trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
            scope_type=ConditionScopeType.CATEGORY,
            category=self.category,
            condition_tree={
                "source_type": "category_field_change",
                "category_field_key": "notes",
                "operator": "changed_to",
                "value": "Updated category note",
            },
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Category field updated"},
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"extra_data": {"category_fields": {"notes": "Updated category note"}}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
                rule=rule,
                result=RuleEvaluationResult.WARNING,
            ).exists()
        )

    def test_patch_same_category_field_value_does_not_evaluate_category_field_change(self):
        CategoryField.objects.create(
            category=self.category,
            field_key="notes",
            is_visible=True,
            is_required=False,
            order=1,
        )
        ConditionRule.objects.create(
            firm=self.firm,
            name="Warn any category notes change",
            trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
            scope_type=ConditionScopeType.CATEGORY,
            category=self.category,
            condition_tree={
                "source_type": "category_field_change",
                "category_field_key": "notes",
                "operator": "changed",
            },
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Category notes changed"},
        )
        self.record.extra_data = {"category_fields": {"notes": "Same value"}}
        self.record.save(update_fields=["extra_data"])

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"extra_data": {"category_fields": {"notes": "Same value"}}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
            ).exists()
        )

    def test_patch_category_field_change_rejects_unknown_field_for_category(self):
        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"extra_data": {"category_fields": {"unknown_field": "x"}}},
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertEqual(payload.get("code"), "invalid_category_field_key")
        self.assertFalse(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
            ).exists()
        )

    def test_patch_category_field_change_refreshes_active_stage_requirements(self):
        CategoryField.objects.create(
            category=self.category,
            field_key="notes",
            is_visible=True,
            is_required=False,
            order=1,
        )
        scenario = StageScenario.objects.create(
            firm=self.firm,
            category=self.category,
            stage=self.stage_new,
            name="Category field scenario",
            activation_condition={"source_type": "category_field", "category_field_key": "notes", "operator": "eq", "value": "done"},
            is_active=True,
            priority=1,
        )
        requirement = StageRequirement.objects.create(
            firm=self.firm,
            scenario=scenario,
            name="Notes completed",
            requirement_type="field",
            condition={"source_type": "category_field", "category_field_key": "notes", "operator": "eq", "value": "done"},
            blocking=True,
            visible_to_user=True,
            sort_order=1,
        )

        resp = self._patch(
            f"/api/v1/crm/records/{self.record.id}",
            {"extra_data": {"category_fields": {"notes": "done"}}},
        )
        self.assertEqual(resp.status_code, 200)

        self.record.refresh_from_db()
        self.assertIn("active_stage_scenario_id", self.record.extra_data)
        self.assertIn("active_stage_requirements", self.record.extra_data)
        self.assertEqual(self.record.extra_data["active_stage_requirements"][0]["id"], str(requirement.id))
        self.assertTrue(self.record.extra_data["active_stage_requirements"][0]["is_met"])
        self.assertEqual(
            self.record.extra_data["active_stage_requirements"][0]["relevant_field_key"],
            "notes",
        )


class RecordDeleteAPITest(CRMAPIFixtureMixin, TestCase):
    def test_delete_record_admin_succeeds(self):
        resp = self._delete(f"/api/v1/crm/records/{self.record.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(PipelineRecord.objects.filter(id=self.record.id).exists())

    def test_delete_record_worker_returns_403(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(f"/api/v1/crm/records/{self.record.id}")
        self.assertEqual(resp.status_code, 403)


# -- Activities --------------------------------------------------------------

class ActivityListAPITest(CRMAPIFixtureMixin, TestCase):
    def test_list_activities_empty(self):
        resp = self._get(f"/api/v1/crm/records/{self.record.id}/activities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_activities_after_comment(self):
        Activity.objects.create(
            record=self.record, user=self.owner, type=ActivityType.COMMENT, content_text="Hello"
        )
        resp = self._get(f"/api/v1/crm/records/{self.record.id}/activities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_list_activities_pagination(self):
        for i in range(5):
            Activity.objects.create(
                record=self.record, type=ActivityType.COMMENT, content_text=f"msg {i}"
            )
        resp = self._get(
            f"/api/v1/crm/records/{self.record.id}/activities",
            {"page": 1, "page_size": 3},
        )
        self.assertEqual(len(resp.json()), 3)

    def test_list_activities_nonexistent_record_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/records/{uuid.uuid4()}/activities")
        self.assertEqual(resp.status_code, 404)


class ActivityCreateAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/activities"

    def test_create_comment_activity(self):
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": "comment",
            "content_text": "First contact",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["type"], "comment")

    def test_create_activity_invalid_record_returns_400(self):
        import uuid
        resp = self._post(self.URL, {
            "record_id": str(uuid.uuid4()),
            "type": "comment",
            "content_text": "Orphan",
        })
        self.assertEqual(resp.status_code, 400)

    def test_create_activity_invalid_type_returns_400(self):
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": "invalid_type",
        })
        self.assertEqual(resp.status_code, 400)

    def test_status_change_activity_updates_record(self):
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": "status_change",
            "metadata": {"new_status": "contacted"},
        })
        self.assertEqual(resp.status_code, 201)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "contacted")

    def test_create_activity_record_evaluates_streamline_rules_and_logs(self):
        category = Category.objects.create(firm=self.firm, name="Sales")
        stage = Stage.objects.create(category=category, name="New", order=0)
        self.record.category = category
        self.record.current_stage = stage
        self.record.save(update_fields=["category", "current_stage"])
        rule = ConditionRule.objects.create(
            firm=self.firm,
            name="Warn on comment activity",
            trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
            scope_type=ConditionScopeType.STAGE,
            stage=stage,
            activity_type=ActivityType.COMMENT,
            condition_tree={
                "source_type": "streamline_activity",
                "activity_type": ActivityType.COMMENT,
                "operator": "exists",
            },
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "Comment activity detected"},
        )

        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": ActivityType.COMMENT,
            "content_text": "First contact",
        })
        self.assertEqual(resp.status_code, 201)
        log = RuleEvaluationLog.objects.filter(
            firm=self.firm,
            record=self.record,
            trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
            rule=rule,
            result=RuleEvaluationResult.WARNING,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.input_context.get("streamline_event", {}).get("entity_type"), "record")
        self.assertEqual(log.input_context.get("streamline_event", {}).get("type"), ActivityType.COMMENT)

    def test_create_activity_customer_refreshes_linked_record_requirements(self):
        category = Category.objects.create(firm=self.firm, name="Sales")
        stage = Stage.objects.create(category=category, name="New", order=0)
        self.record.category = category
        self.record.current_stage = stage
        self.record.save(update_fields=["category", "current_stage"])
        scenario = StageScenario.objects.create(
            firm=self.firm,
            category=category,
            stage=stage,
            name="Customer activity scenario",
            activation_condition={},
            is_active=True,
            priority=1,
        )
        requirement = StageRequirement.objects.create(
            firm=self.firm,
            scenario=scenario,
            name="Customer comment exists",
            requirement_type="activity",
            condition={
                "source_type": "activity",
                "activity_type": ActivityType.COMMENT,
                "entity_type": "customer",
                "operator": "exists",
            },
            blocking=True,
            visible_to_user=True,
            sort_order=1,
        )

        resp = self._post(self.URL, {
            "customer_id": str(self.customer.id),
            "type": ActivityType.COMMENT,
            "content_text": "Customer note",
        })
        self.assertEqual(resp.status_code, 201)
        self.record.refresh_from_db()
        self.assertEqual(
            self.record.extra_data.get("active_stage_requirements", [{}])[0].get("id"),
            str(requirement.id),
        )
        self.assertTrue(
            self.record.extra_data.get("active_stage_requirements", [{}])[0].get("is_met"),
        )

    def test_create_activity_proposal_and_task_refresh_linked_record_requirements(self):
        category = Category.objects.create(firm=self.firm, name="Sales")
        stage = Stage.objects.create(category=category, name="New", order=0)
        self.record.category = category
        self.record.current_stage = stage
        self.record.save(update_fields=["category", "current_stage"])
        proposal = Proposal.objects.create(
            firm=self.firm,
            title="Offer",
            record=self.record,
            customer=self.customer,
        )
        task = Task.objects.create(
            firm=self.firm,
            title="Follow-up",
            record=self.record,
            proposal=proposal,
            customer=self.customer,
        )
        scenario = StageScenario.objects.create(
            firm=self.firm,
            category=category,
            stage=stage,
            name="Proposal/task activity scenario",
            activation_condition={},
            is_active=True,
            priority=1,
        )
        StageRequirement.objects.create(
            firm=self.firm,
            scenario=scenario,
            name="Proposal comment exists",
            requirement_type="activity",
            condition={
                "source_type": "activity",
                "activity_type": ActivityType.COMMENT,
                "entity_type": "proposal",
                "operator": "exists",
            },
            blocking=True,
            visible_to_user=True,
            sort_order=1,
        )

        proposal_resp = self._post(self.URL, {
            "proposal_id": str(proposal.id),
            "type": ActivityType.COMMENT,
            "content_text": "Proposal note",
        })
        self.assertEqual(proposal_resp.status_code, 201)
        self.record.refresh_from_db()
        self.assertTrue(self.record.extra_data.get("active_stage_requirements", [{}])[0].get("is_met"))

        StageRequirement.objects.all().delete()
        StageRequirement.objects.create(
            firm=self.firm,
            scenario=scenario,
            name="Task comment exists",
            requirement_type="activity",
            condition={
                "source_type": "activity",
                "activity_type": ActivityType.COMMENT,
                "entity_type": "task",
                "operator": "exists",
            },
            blocking=True,
            visible_to_user=True,
            sort_order=1,
        )

        task_resp = self._post(self.URL, {
            "task_id": str(task.id),
            "type": ActivityType.COMMENT,
            "content_text": "Task note",
        })
        self.assertEqual(task_resp.status_code, 201)
        self.record.refresh_from_db()
        self.assertTrue(self.record.extra_data.get("active_stage_requirements", [{}])[0].get("is_met"))

    def test_create_activity_condition_evaluation_failure_is_fail_open(self):
        category = Category.objects.create(firm=self.firm, name="Sales")
        stage = Stage.objects.create(category=category, name="New", order=0)
        self.record.category = category
        self.record.current_stage = stage
        self.record.save(update_fields=["category", "current_stage"])
        ConditionRule.objects.create(
            firm=self.firm,
            name="Any streamline rule",
            trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
            scope_type=ConditionScopeType.FIRM,
            condition_tree={},
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
        )

        with patch("crm.condition_rules.evaluate_condition_rule_outputs", side_effect=RuntimeError("boom")):
            resp = self._post(self.URL, {
                "record_id": str(self.record.id),
                "type": ActivityType.COMMENT,
                "content_text": "First contact",
            })

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            RuleEvaluationLog.objects.filter(
                firm=self.firm,
                record=self.record,
                trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
                result=RuleEvaluationResult.ERROR,
            ).exists()
        )

    # ------------------------------------------------------------------
    # F-3 — payload validation against tool JSON Schema
    # ------------------------------------------------------------------

    def test_payload_missing_required_field_returns_400(self):
        """status_change requires metadata.new_status — empty metadata fails."""
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": "status_change",
            "metadata": {},
        })
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("status_change", body["detail"])
        self.assertIn("new_status", body["detail"])

    def test_payload_invalid_enum_returns_400(self):
        """status_change has new_status enum — bogus value fails."""
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": "status_change",
            "metadata": {"new_status": "not_a_real_status"},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("new_status", resp.json()["detail"])

    def test_payload_negative_minimum_returns_400(self):
        """call.duration_minutes has minimum: 0 — negative value fails."""
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": "call",
            "content_text": "Quick chat",
            "metadata": {"duration_minutes": -5},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("duration_minutes", resp.json()["detail"])

    def test_payload_unknown_metadata_keys_allowed(self):
        """Unknown metadata properties should pass (additionalProperties: true)."""
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "type": "comment",
            "content_text": "Hello",
            "metadata": {"some_future_key": "anything"},
        })
        self.assertEqual(resp.status_code, 201)


# -- Tasks -------------------------------------------------------------------

class TaskListAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/tasks"

    def test_list_tasks_empty(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_tasks_returns_firm_tasks(self):
        Task.objects.create(firm=self.firm, record=self.record, title="Do something")
        resp = self._get(self.URL)
        self.assertEqual(len(resp.json()), 1)

    def test_filter_by_completed(self):
        Task.objects.create(firm=self.firm, record=self.record, title="Done", is_completed=True)
        Task.objects.create(firm=self.firm, record=self.record, title="Pending")
        resp = self._get(self.URL, {"completed": "true"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["is_completed"])

    def test_pagination(self):
        for i in range(5):
            Task.objects.create(firm=self.firm, record=self.record, title=f"Task {i}")
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)


class TaskCreateAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/tasks"

    def test_create_task_returns_201(self):
        resp = self._post(self.URL, {
            "record_id": str(self.record.id),
            "title": "Send proposal",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.json()["is_completed"])

    def test_create_task_logs_task_assigned_activity(self):
        self._post(self.URL, {"record_id": str(self.record.id), "title": "Task A"})
        self.assertTrue(
            Activity.objects.filter(
                record=self.record, type=ActivityType.TASK_ASSIGNED
            ).exists()
        )

    def test_create_task_invalid_record_returns_400(self):
        import uuid
        resp = self._post(self.URL, {"record_id": str(uuid.uuid4()), "title": "Orphan"})
        self.assertEqual(resp.status_code, 400)


class TaskCompleteAPITest(CRMAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.task = Task.objects.create(
            firm=self.firm, record=self.record, title="Call client"
        )

    def test_complete_task_returns_200(self):
        resp = self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_completed"])

    def test_complete_task_logs_activity(self):
        self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        self.assertTrue(
            Activity.objects.filter(
                record=self.record, type=ActivityType.TASK_COMPLETED
            ).exists()
        )

    def test_complete_already_completed_task_is_idempotent(self):
        self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        resp = self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        self.assertEqual(resp.status_code, 200)
        # Only one TASK_COMPLETED activity should exist
        count = Activity.objects.filter(
            record=self.record, type=ActivityType.TASK_COMPLETED
        ).count()
        self.assertEqual(count, 1)

    def test_complete_nonexistent_task_returns_404(self):
        import uuid
        resp = self._post(f"/api/v1/crm/tasks/{uuid.uuid4()}/complete", {})
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Tier limit enforcement for record creation
# ---------------------------------------------------------------------------


class TierLimitRecordCreateAPITest(TestCase):
    """create_record enforces the Free-tier 50-record limit."""

    URL = "/api/v1/crm/records"

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@record_tier.com", password="pass")
        # Free-tier firm with only 1 member to avoid hitting the member limit.
        self.firm = Firm.objects.create(name="Free PipelineRecord Firm", subscription_tier="free")
        Membership.objects.create(user=self.owner, firm=self.firm, role=InvitationRole.OWNER)
        self.client.login(username="owner@record_tier.com", password="pass")

    def _firm_headers(self):
        return {"HTTP_X_FIRM_ID": str(self.firm.id)}

    def test_create_record_blocked_when_50_records_exist(self):
        # Pre-fill 50 records directly in the DB.
        PipelineRecord.objects.bulk_create([
            PipelineRecord(firm=self.firm, title=f"PipelineRecord {i}") for i in range(50)
        ])
        resp = self.client.post(
            self.URL,
            data=json.dumps({"title": "Over limit"}),
            content_type="application/json",
            **self._firm_headers(),
        )
        self.assertEqual(resp.status_code, 402)
        self.assertIn("50 records", resp.json()["detail"])

    def test_create_record_allowed_at_49_records(self):
        PipelineRecord.objects.bulk_create([
            PipelineRecord(firm=self.firm, title=f"PipelineRecord {i}") for i in range(49)
        ])
        resp = self.client.post(
            self.URL,
            data=json.dumps({"title": "Just within limit"}),
            content_type="application/json",
            **self._firm_headers(),
        )
        self.assertEqual(resp.status_code, 201)


# ---------------------------------------------------------------------------
# PipelineRecord Attachments API tests (now backed by Document)
# ---------------------------------------------------------------------------

import io
import uuid as uuid_module

from django.core.files.uploadedfile import SimpleUploadedFile

from crm.models import Document


class AttachmentAPIFixtureMixin(CRMAPIFixtureMixin):
    """Extends CRMAPIFixtureMixin with a pre-built SimpleUploadedFile helper."""

    def _make_file(self, name="test.txt", content=b"hello world", content_type="text/plain"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def _upload(self, record_id, name="test.txt", content=b"hello world"):
        f = self._make_file(name=name, content=content)
        return self.client.post(
            f"/api/v1/crm/records/{record_id}/attachments",
            data={"file": f},
            **self.firm_headers(),
        )


class AttachmentListAPITest(AttachmentAPIFixtureMixin, TestCase):
    def test_list_attachments_empty(self):
        resp = self._get(f"/api/v1/crm/records/{self.record.id}/attachments")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_attachments_nonexistent_record_returns_404(self):
        resp = self._get(f"/api/v1/crm/records/{uuid_module.uuid4()}/attachments")
        self.assertEqual(resp.status_code, 404)

    def test_list_attachments_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm Attach")
        other_record = PipelineRecord.objects.create(firm=other_firm, title="Other PipelineRecord")
        # Upload directly to DB for other firm's record — should not appear in our list.
        Document.objects.create(
            firm=other_firm,
            record=other_record,
            name="secret.pdf",
            content_type="application/pdf",
            size_bytes=100,
        )
        resp = self._get(f"/api/v1/crm/records/{self.record.id}/attachments")
        self.assertEqual(resp.json(), [])

    def test_list_attachments_pagination(self):
        for i in range(5):
            Document.objects.create(
                firm=self.firm,
                record=self.record,
                name=f"file{i}.txt",
                content_type="text/plain",
                size_bytes=i,
            )
        resp = self._get(
            f"/api/v1/crm/records/{self.record.id}/attachments",
            {"page": 1, "page_size": 3},
        )
        self.assertEqual(len(resp.json()), 3)


class AttachmentUploadAPITest(AttachmentAPIFixtureMixin, TestCase):
    def tearDown(self):
        # Clean up any files written to MEDIA_ROOT during tests.
        for doc in Document.objects.filter(record=self.record):
            doc.file.delete(save=False)
        super().tearDown()

    def test_upload_returns_201(self):
        resp = self._upload(self.record.id)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["original_filename"], "test.txt")
        self.assertEqual(data["record_id"], str(self.record.id))
        self.assertIn("url", data)

    def test_upload_creates_db_record(self):
        self._upload(self.record.id)
        self.assertEqual(Document.objects.filter(record=self.record).count(), 1)

    def test_upload_logs_file_upload_activity(self):
        self._upload(self.record.id)
        self.assertTrue(
            Activity.objects.filter(
                record=self.record, type=ActivityType.FILE_UPLOAD
            ).exists()
        )

    def test_upload_activity_metadata_contains_filename(self):
        self._upload(self.record.id, name="report.pdf", content=b"PDF")
        activity = Activity.objects.get(record=self.record, type=ActivityType.FILE_UPLOAD)
        self.assertEqual(activity.metadata["filename"], "report.pdf")

    def test_upload_worker_allowed(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._upload(self.record.id)
        self.assertEqual(resp.status_code, 201)

    def test_upload_nonexistent_record_returns_404(self):
        resp = self._upload(uuid_module.uuid4())
        self.assertEqual(resp.status_code, 404)

    def test_upload_requires_authentication(self):
        self.client.logout()
        resp = self._upload(self.record.id)
        self.assertIn(resp.status_code, [401, 403])

    def test_upload_file_too_large_returns_400(self):
        large_content = b"x" * (20 * 1024 * 1024 + 1)
        resp = self._upload(self.record.id, content=large_content)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("20 MB", resp.json()["detail"])


class AttachmentDeleteAPITest(AttachmentAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Create a Document record without a physical file for delete tests.
        self.attachment = Document.objects.create(
            firm=self.firm,
            record=self.record,
            name="deleteme.txt",
            content_type="text/plain",
            size_bytes=5,
        )

    def test_delete_attachment_admin_succeeds(self):
        resp = self._delete(
            f"/api/v1/crm/records/{self.record.id}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Document.objects.filter(id=self.attachment.id).exists())

    def test_delete_attachment_worker_returns_403(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(
            f"/api/v1/crm/records/{self.record.id}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_nonexistent_attachment_returns_404(self):
        resp = self._delete(
            f"/api/v1/crm/records/{self.record.id}/attachments/{uuid_module.uuid4()}"
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_attachment_wrong_record_returns_404(self):
        other_record = PipelineRecord.objects.create(firm=self.firm, title="Other PipelineRecord")
        resp = self._delete(
            f"/api/v1/crm/records/{other_record.id}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_attachment_nonexistent_record_returns_404(self):
        resp = self._delete(
            f"/api/v1/crm/records/{uuid_module.uuid4()}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Voice Memo upload API tests
# ---------------------------------------------------------------------------


class VoiceMemoUploadAPITest(AttachmentAPIFixtureMixin, TestCase):
    """Smoke tests for ``POST /api/v1/crm/voice-memos/upload``."""

    def _upload_voice(
        self,
        *,
        record_id=None,
        content=b"FAKEAUDIO",
        content_type="audio/webm",
        filename="memo.webm",
    ):
        f = SimpleUploadedFile(filename, content, content_type=content_type)
        url = "/api/v1/crm/voice-memos/upload"
        if record_id:
            url = f"{url}?record_id={record_id}"
        return self.client.post(url, data={"file": f}, **self.firm_headers())

    def test_upload_voice_memo_returns_metadata_without_creating_activity(self):
        before = Activity.objects.filter(type=ActivityType.VOICE_MEMO).count()
        resp = self._upload_voice(record_id=str(self.record.id))
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertIn("document_id", body)
        self.assertTrue(body["url"])
        self.assertEqual(body["size_bytes"], len(b"FAKEAUDIO"))
        self.assertEqual(body["content_type"], "audio/webm")
        # The endpoint stores a Document but deliberately does NOT create
        # an Activity — the SPA follows up with a regular activities POST.
        after = Activity.objects.filter(type=ActivityType.VOICE_MEMO).count()
        self.assertEqual(before, after)
        self.assertTrue(
            Document.objects.filter(id=body["document_id"], firm=self.firm).exists()
        )

    def test_upload_voice_memo_works_without_entity(self):
        resp = self._upload_voice()
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        doc = Document.objects.get(id=body["document_id"])
        self.assertIsNone(doc.record_id)

    def test_upload_voice_memo_rejects_non_audio(self):
        resp = self._upload_voice(content_type="text/plain", filename="memo.txt")
        self.assertEqual(resp.status_code, 400)

    def test_upload_voice_memo_invalid_record_returns_404(self):
        resp = self._upload_voice(record_id=str(uuid_module.uuid4()))
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# File Upload composer API tests (Fáze 7.2)
# ---------------------------------------------------------------------------


class FileUploadComposerAPITest(AttachmentAPIFixtureMixin, TestCase):
    """Smoke tests for ``POST /api/v1/crm/file-uploads/upload``."""

    URL = "/api/v1/crm/file-uploads/upload"

    def _upload_files(self, *files, record_id=None):
        payload = [("files", f) for f in files]
        url = self.URL
        if record_id:
            url = f"{url}?record_id={record_id}"
        return self.client.post(url, dict(payload), **self.firm_headers())

    def test_multi_file_upload_returns_one_entry_per_file_no_activity(self):
        before = Activity.objects.filter(type=ActivityType.FILE_UPLOAD).count()
        f1 = SimpleUploadedFile("a.pdf", b"PDF1", content_type="application/pdf")
        f2 = SimpleUploadedFile("b.png", b"PNGDATA", content_type="image/png")
        resp = self.client.post(
            f"{self.URL}?record_id={self.record.id}",
            data={"files": [f1, f2]},
            **self.firm_headers(),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(len(body["files"]), 2)
        # Endpoint must NOT auto-create file_upload Activities — the SPA
        # follows up with one POST /activities per returned entry.
        self.assertEqual(
            Activity.objects.filter(type=ActivityType.FILE_UPLOAD).count(),
            before,
        )
        for entry in body["files"]:
            self.assertTrue(entry["url"])
            self.assertTrue(entry["document_id"])
            self.assertTrue(
                Document.objects.filter(id=entry["document_id"], firm=self.firm).exists()
            )

    def test_upload_rejects_oversize_for_free_plan(self):
        # Fixture firm is `pro` (100 MB cap); flip it to `free` so the
        # 15 MB ceiling kicks in for this test only.
        self.firm.subscription_tier = "free"
        self.firm.save(update_fields=["subscription_tier"])
        # Build a 16 MB blob — one byte over the free-plan cap.
        blob = b"x" * (16 * 1024 * 1024)
        f = SimpleUploadedFile("huge.bin", blob, content_type="application/octet-stream")
        resp = self.client.post(
            self.URL,
            data={"files": f},
            **self.firm_headers(),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("MB", resp.json()["detail"])

    def test_upload_invalid_record_returns_404(self):
        f = SimpleUploadedFile("a.txt", b"hi", content_type="text/plain")
        resp = self.client.post(
            f"{self.URL}?record_id={uuid_module.uuid4()}",
            data={"files": f},
            **self.firm_headers(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_upload_works_without_entity(self):
        f = SimpleUploadedFile("standalone.txt", b"hi", content_type="text/plain")
        resp = self.client.post(self.URL, data={"files": f}, **self.firm_headers())
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(len(body["files"]), 1)
        doc = Document.objects.get(id=body["files"][0]["document_id"])
        self.assertIsNone(doc.record_id)


class FileUploadToolSchemaTest(TestCase):
    """The expanded `file_upload` schema is the contract the SPA renders."""

    def test_schema_advertises_title_and_source_kind(self):
        from crm.streamline.tools import FileUploadTool

        schema = FileUploadTool().get_schema()
        self.assertIn("title", schema["properties"])
        self.assertIn("source_kind", schema["properties"])
        self.assertIn("store_locally", schema["properties"])
        self.assertIn("mime_type", schema["properties"])
        self.assertIn("title", schema["required"])
        self.assertIn("url", schema["required"])
        self.assertEqual(
            schema["properties"]["source_kind"]["enum"],
            ["url", "upload"],
        )

    def test_render_payload_exposes_user_facing_fields(self):
        from crm.streamline.tools import FileUploadTool

        firm = Firm.objects.create(name="FUT firm")
        record = PipelineRecord.objects.create(firm=firm, title="FUT record")
        activity = Activity.objects.create(
            record=record,
            type=ActivityType.FILE_UPLOAD,
            metadata={
                "title": "Q4 brief",
                "filename": "brief.pdf",
                "url": "https://example.org/brief.pdf",
                "size_bytes": 1024,
                "mime_type": "application/pdf",
                "source_kind": "url",
                "store_locally": False,
            },
        )
        payload = FileUploadTool().render_payload(activity)
        self.assertEqual(payload["title"], "Q4 brief")
        self.assertEqual(payload["source_kind"], "url")
        self.assertFalse(payload["store_locally"])
        self.assertEqual(payload["mime_type"], "application/pdf")


class FileUploadRemoteFetchTaskTest(TestCase):
    """The Celery task that downloads remote URLs into Document storage."""

    def setUp(self):
        self.firm = Firm.objects.create(name="Fetch firm")
        self.record = PipelineRecord.objects.create(firm=self.firm, title="Fetch record")

    def _make_activity(self, **metadata):
        return Activity.objects.create(
            record=self.record,
            type=ActivityType.FILE_UPLOAD,
            metadata=metadata,
        )

    def test_task_populates_document_and_metadata_on_success(self):
        from unittest.mock import MagicMock, patch

        activity = self._make_activity(
            title="Remote brief",
            url="https://example.org/foo.pdf",
            source_kind="url",
            store_locally=True,
        )

        body = b"%PDF-1.4 fake-bytes"
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/pdf", "Content-Length": str(len(body))}
        mock_response.iter_content = MagicMock(return_value=[body])
        mock_response.raise_for_status = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("requests.get", return_value=mock_response):
            from crm.tasks import fetch_remote_file_for_activity

            fetch_remote_file_for_activity(str(activity.id))

        activity.refresh_from_db()
        self.assertEqual(activity.metadata.get("fetch_status"), "ok")
        self.assertEqual(activity.metadata.get("size_bytes"), len(body))
        self.assertEqual(activity.metadata.get("mime_type"), "application/pdf")
        self.assertTrue(activity.metadata.get("document_id"))
        self.assertEqual(
            activity.metadata.get("source_url"), "https://example.org/foo.pdf"
        )

    def test_task_records_failure_without_corrupting_url(self):
        from unittest.mock import patch

        activity = self._make_activity(
            title="Broken",
            url="https://example.org/missing.pdf",
            source_kind="url",
            store_locally=True,
        )

        with patch("requests.get", side_effect=RuntimeError("boom")):
            from crm.tasks import fetch_remote_file_for_activity

            fetch_remote_file_for_activity(str(activity.id))

        activity.refresh_from_db()
        self.assertEqual(activity.metadata.get("fetch_status"), "failed")
        self.assertIn("boom", activity.metadata.get("fetch_error", ""))
        # Original URL is preserved so the user can still click through.
        self.assertEqual(
            activity.metadata.get("url"), "https://example.org/missing.pdf"
        )


# ---------------------------------------------------------------------------
# Task Documents API tests (Phase 6 — /tasks/{id}/documents endpoints)
# ---------------------------------------------------------------------------


class TaskDocumentAPIFixtureMixin(CRMAPIFixtureMixin):
    """Adds a Task + file-upload helper for /tasks/{id}/documents tests."""

    def setUp(self):
        super().setUp()
        self.task = Task.objects.create(
            firm=self.firm, record=self.record, title="Doc test task"
        )

    def _upload_doc(self, task_id, name="task.txt", content=b"task body"):
        f = SimpleUploadedFile(name, content, content_type="text/plain")
        return self.client.post(
            f"/api/v1/crm/tasks/{task_id}/documents",
            data={"file": f},
            **self.firm_headers(),
        )


class TaskDocumentListAPITest(TaskDocumentAPIFixtureMixin, TestCase):
    def test_list_empty(self):
        resp = self._get(f"/api/v1/crm/tasks/{self.task.id}/documents")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_nonexistent_task_returns_404(self):
        resp = self._get(f"/api/v1/crm/tasks/{uuid_module.uuid4()}/documents")
        self.assertEqual(resp.status_code, 404)

    def test_list_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm Task Doc")
        other_record = PipelineRecord.objects.create(firm=other_firm, title="Other PipelineRecord")
        other_task = Task.objects.create(firm=other_firm, record=other_record, title="Other")
        Document.objects.create(
            firm=other_firm, task=other_task, name="hidden.pdf",
            content_type="application/pdf", size_bytes=10,
        )
        # Hitting our firm with their task ID must 404 (cross-tenant).
        resp = self._get(f"/api/v1/crm/tasks/{other_task.id}/documents")
        self.assertEqual(resp.status_code, 404)

    def test_list_returns_only_task_documents(self):
        # One doc on our task, one on the record — only the task one must appear.
        Document.objects.create(
            firm=self.firm, task=self.task, name="mine.txt",
            content_type="text/plain", size_bytes=4,
        )
        Document.objects.create(
            firm=self.firm, record=self.record, name="recordonly.txt",
            content_type="text/plain", size_bytes=8,
        )
        resp = self._get(f"/api/v1/crm/tasks/{self.task.id}/documents")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["original_filename"], "mine.txt")


class TaskDocumentUploadAPITest(TaskDocumentAPIFixtureMixin, TestCase):
    def tearDown(self):
        for doc in Document.objects.filter(task=self.task):
            doc.file.delete(save=False)
        super().tearDown()

    def test_upload_returns_201(self):
        resp = self._upload_doc(self.task.id, name="hello.txt", content=b"hi")
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["original_filename"], "hello.txt")
        self.assertEqual(body["task_id"], str(self.task.id))
        self.assertEqual(body["size_bytes"], 2)

    def test_upload_creates_file_upload_activity(self):
        resp = self._upload_doc(self.task.id, name="audit.txt", content=b"x")
        self.assertEqual(resp.status_code, 201)
        doc_id = resp.json()["id"]
        activity = Activity.objects.get(task=self.task, type=ActivityType.FILE_UPLOAD)
        self.assertEqual(activity.metadata.get("document_id"), doc_id)
        self.assertEqual(activity.metadata.get("filename"), "audit.txt")

    def test_upload_nonexistent_task_returns_404(self):
        f = SimpleUploadedFile("x.txt", b"x", content_type="text/plain")
        resp = self.client.post(
            f"/api/v1/crm/tasks/{uuid_module.uuid4()}/documents",
            data={"file": f},
            **self.firm_headers(),
        )
        self.assertEqual(resp.status_code, 404)


class TaskDocumentDeleteAPITest(TaskDocumentAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.doc = Document.objects.create(
            firm=self.firm, task=self.task,
            uploaded_by=self.owner,
            name="deleteme.txt", content_type="text/plain", size_bytes=5,
        )

    def test_delete_owner_succeeds(self):
        resp = self._delete(
            f"/api/v1/crm/tasks/{self.task.id}/documents/{self.doc.id}"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Document.objects.filter(id=self.doc.id).exists())

    def test_delete_other_user_doc_as_worker_returns_403(self):
        # Doc was uploaded by owner — worker can't delete it.
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(
            f"/api/v1/crm/tasks/{self.task.id}/documents/{self.doc.id}"
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_nonexistent_doc_returns_404(self):
        resp = self._delete(
            f"/api/v1/crm/tasks/{self.task.id}/documents/{uuid_module.uuid4()}"
        )
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# v0.6 Reporting API tests
# ---------------------------------------------------------------------------


class PipelineSummaryAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/reports/pipeline"

    def test_returns_200(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_all_statuses_present(self):
        resp = self._get(self.URL)
        data = resp.json()
        returned_statuses = {row["status"] for row in data["statuses"]}
        from crm.models import RecordStatus
        expected = {s.value for s in RecordStatus}
        self.assertEqual(returned_statuses, expected)

    def test_counts_reflect_records(self):
        # setUp creates one NEW record; add a WON record with a value
        PipelineRecord.objects.create(firm=self.firm, title="Won Deal", status=RecordStatus.WON, value="5000.00")
        resp = self._get(self.URL)
        data = resp.json()
        rows_by_status = {row["status"]: row for row in data["statuses"]}
        self.assertEqual(rows_by_status["new"]["count"], 1)
        self.assertEqual(rows_by_status["won"]["count"], 1)
        self.assertEqual(rows_by_status["lost"]["count"], 0)

    def test_total_value_sums_all_statuses(self):
        PipelineRecord.objects.create(firm=self.firm, title="L1", status=RecordStatus.NEW, value="1000.00")
        PipelineRecord.objects.create(firm=self.firm, title="L2", status=RecordStatus.WON, value="2000.00")
        resp = self._get(self.URL)
        data = resp.json()
        self.assertAlmostEqual(data["total_value"], 3000.0, places=2)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Report Other Firm")
        PipelineRecord.objects.create(firm=other_firm, title="Foreign PipelineRecord", status=RecordStatus.WON)
        resp = self._get(self.URL)
        data = resp.json()
        rows_by_status = {row["status"]: row for row in data["statuses"]}
        # Our firm only has one NEW record from setUp
        self.assertEqual(rows_by_status["won"]["count"], 0)

    def test_requires_authentication(self):
        self.client.logout()
        resp = self._get(self.URL)
        self.assertIn(resp.status_code, [401, 403])

    def test_requires_firm_header(self):
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, [401, 403])


class ActivityFeedAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/reports/activities"

    def setUp(self):
        super().setUp()
        # Create a second record so we can verify cross-record aggregation
        self.record2 = PipelineRecord.objects.create(firm=self.firm, title="Second PipelineRecord")
        self.a1 = Activity.objects.create(
            record=self.record, user=self.owner, type=ActivityType.COMMENT, content_text="First"
        )
        self.a2 = Activity.objects.create(
            record=self.record2, user=self.worker, type=ActivityType.CALL, content_text="Call"
        )

    def test_returns_200(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_returns_activities_across_all_records(self):
        resp = self._get(self.URL)
        data = resp.json()
        self.assertEqual(len(data), 2)

    def test_includes_record_title(self):
        resp = self._get(self.URL)
        titles = {item["record_title"] for item in resp.json()}
        self.assertIn("Test PipelineRecord", titles)
        self.assertIn("Second PipelineRecord", titles)

    def test_ordered_newest_first(self):
        resp = self._get(self.URL)
        data = resp.json()
        self.assertEqual(data[0]["id"], str(self.a2.id))
        self.assertEqual(data[1]["id"], str(self.a1.id))

    def test_filter_by_type(self):
        resp = self._get(self.URL, {"type": "call"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["type"], "call")

    def test_filter_by_type_no_match_returns_empty(self):
        resp = self._get(self.URL, {"type": "meeting"})
        self.assertEqual(resp.json(), [])

    def test_pagination(self):
        for i in range(5):
            Activity.objects.create(record=self.record, type=ActivityType.COMMENT, content_text=f"m{i}")
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Feed Other Firm")
        other_record = PipelineRecord.objects.create(firm=other_firm, title="Spy PipelineRecord")
        Activity.objects.create(record=other_record, type=ActivityType.COMMENT, content_text="spy")
        resp = self._get(self.URL)
        record_ids = {item["record_id"] for item in resp.json()}
        self.assertNotIn(str(other_record.id), record_ids)

    def test_requires_authentication(self):
        self.client.logout()
        resp = self._get(self.URL)
        self.assertIn(resp.status_code, [401, 403])


class UserTimelineReportAPITest(CRMAPIFixtureMixin, TestCase):
    URL_TEMPLATE = "/api/v1/crm/reports/users/{membership_id}/timeline"

    def setUp(self):
        super().setUp()
        self.proposal = Proposal.objects.create(
            firm=self.firm,
            record=self.record,
            title="Demo Proposal",
            status="draft",
        )
        self.task = Task.objects.create(
            firm=self.firm,
            record=self.record,
            title="Follow up task",
            created_by=self.owner,
        )

        self.owner_record_activity = Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=ActivityType.COMMENT,
            content_text="Owner record",
        )
        self.owner_customer_activity = Activity.objects.create(
            customer=self.customer,
            user=self.owner,
            type=ActivityType.MEETING,
            content_text="Owner customer",
        )
        self.owner_proposal_activity = Activity.objects.create(
            proposal=self.proposal,
            user=self.owner,
            type=ActivityType.EMAIL_OUT,
            content_text="Owner proposal",
        )
        self.owner_task_activity = Activity.objects.create(
            task=self.task,
            user=self.owner,
            type=ActivityType.TASK_COMPLETED,
            content_text="Owner task",
        )
        Activity.objects.create(
            record=self.record,
            user=self.worker,
            type=ActivityType.CALL,
            content_text="Worker activity",
        )

    def _url(self, membership_id):
        return self.URL_TEMPLATE.format(membership_id=membership_id)

    def test_returns_200(self):
        resp = self._get(self._url(self.owner_membership.id))
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("items", payload)
        self.assertIn("total_count", payload)

    def test_returns_only_target_member_activities_across_entities(self):
        resp = self._get(self._url(self.owner_membership.id))
        payload = resp.json()
        data = payload["items"]
        self.assertTrue(len(data) >= 4)
        types = {item["entity_type"] for item in data}
        self.assertTrue({"record", "customer", "proposal", "task"}.issubset(types))
        self.assertGreaterEqual(payload["total_count"], len(data))

    def test_filters_by_entity_type(self):
        resp = self._get(self._url(self.owner_membership.id), {"entity_type": "task"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        data = payload["items"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["entity_type"], "task")
        self.assertEqual(data[0]["task_title"], "Follow up task")
        self.assertEqual(payload["total_count"], 1)

    def test_filters_by_activity_type(self):
        resp = self._get(self._url(self.owner_membership.id), {"type": ActivityType.EMAIL_OUT})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        data = payload["items"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["type"], ActivityType.EMAIL_OUT)
        self.assertEqual(payload["total_count"], 1)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm Timeline")
        other_record = PipelineRecord.objects.create(firm=other_firm, title="Other Record")
        Activity.objects.create(
            record=other_record,
            user=self.owner,
            type=ActivityType.COMMENT,
            content_text="Cross-tenant",
        )

        resp = self._get(self._url(self.owner_membership.id))
        self.assertEqual(resp.status_code, 200)
        record_ids = {item["record_id"] for item in resp.json()["items"]}
        self.assertNotIn(str(other_record.id), record_ids)

    def test_returns_404_for_unknown_membership(self):
        resp = self._get(self._url("11111111-1111-1111-1111-111111111111"))
        self.assertEqual(resp.status_code, 404)


class OverdueTasksAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/reports/tasks/overdue"

    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.overdue_task = Task.objects.create(
            firm=self.firm,
            record=self.record,
            title="Overdue",
            due_date=now - dt.timedelta(days=2),
        )
        self.future_task = Task.objects.create(
            firm=self.firm,
            record=self.record,
            title="Future",
            due_date=now + dt.timedelta(days=2),
        )
        self.completed_overdue = Task.objects.create(
            firm=self.firm,
            record=self.record,
            title="Done (was overdue)",
            due_date=now - dt.timedelta(days=1),
            is_completed=True,
        )

    def test_returns_200(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_only_returns_overdue_incomplete_tasks(self):
        resp = self._get(self.URL)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(self.overdue_task.id))

    def test_includes_record_title(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.json()[0]["record_title"], "Test PipelineRecord")

    def test_no_due_date_tasks_excluded(self):
        Task.objects.create(firm=self.firm, record=self.record, title="No Due Date")
        resp = self._get(self.URL)
        ids = {item["id"] for item in resp.json()}
        self.assertIn(str(self.overdue_task.id), ids)
        # Only the one actually overdue task
        self.assertEqual(len(ids), 1)

    def test_pagination(self):
        now = timezone.now()
        for i in range(5):
            Task.objects.create(
                firm=self.firm,
                record=self.record,
                title=f"Old task {i}",
                due_date=now - dt.timedelta(days=i + 3),
            )
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Overdue Other Firm")
        other_record = PipelineRecord.objects.create(firm=other_firm, title="Other PipelineRecord")
        Task.objects.create(
            firm=other_firm,
            record=other_record,
            title="Other Overdue",
            due_date=timezone.now() - dt.timedelta(days=1),
        )
        resp = self._get(self.URL)
        self.assertEqual(len(resp.json()), 1)  # only ours

    def test_requires_authentication(self):
        self.client.logout()
        resp = self._get(self.URL)
        self.assertIn(resp.status_code, [401, 403])



# ===========================================================================
# v1.7 — ImportJob model
# ===========================================================================

class ImportJobModelTest(CRMFixtureMixin, TestCase):
    def test_importjob_str(self):
        from crm.models import ImportJob, ImportJobType, ImportJobStatus
        import tempfile, os
        from django.core.files.base import ContentFile
        job = ImportJob(
            firm=self.firm,
            user=self.owner,
            type=ImportJobType.LEADS,
            status=ImportJobStatus.PENDING,
        )
        self.assertIn("ImportJob", str(job))

    def test_importjob_defaults(self):
        from crm.models import ImportJob, ImportJobType, ImportJobStatus
        from django.core.files.base import ContentFile
        job = ImportJob.objects.create(
            firm=self.firm,
            user=self.owner,
            type=ImportJobType.CUSTOMERS,
            file=ContentFile(b"first_name\nAlice", name="test.csv"),
            original_filename="test.csv",
        )
        self.assertEqual(job.status, ImportJobStatus.PENDING)
        self.assertEqual(job.total, 0)
        self.assertEqual(job.processed, 0)
        self.assertEqual(job.failed_count, 0)
        self.assertEqual(job.errors_json, [])


# ===========================================================================
# v1.7 — iCal endpoint
# ===========================================================================

class ICalEndpointTest(CRMFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_get_ical_token(self):
        resp = self.client.get("/api/v1/integrations/ical/token")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("token", data)
        self.assertIn("url", data)

    def test_ical_feed_valid_token(self):
        resp = self.client.get("/api/v1/integrations/ical/token")
        data = resp.json()
        url = data["url"]
        # Hit the feed URL without authentication (it's a public signed URL)
        self.client.logout()
        resp2 = self.client.get(url)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b"BEGIN:VCALENDAR", resp2.content)

    def test_ical_feed_invalid_token(self):
        resp = self.client.get(
            f"/api/v1/integrations/ical/tasks",
            data={"user_id": str(self.owner.id), "firm_id": str(self.firm.id), "token": "bad"},
        )
        self.assertEqual(resp.status_code, 403)


# ===========================================================================
# v1.7 — CSV Export endpoints
# ===========================================================================

class CSVExportTest(CRMFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_export_records_csv(self):
        resp = self.client.get("/api/v1/integrations/export/records.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        content = b"".join(resp.streaming_content).decode()
        self.assertIn("title", content)

    def test_export_customers_csv(self):
        resp = self.client.get("/api/v1/integrations/export/customers.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        content = b"".join(resp.streaming_content).decode()
        self.assertIn("first_name", content)
        self.assertIn("Jane", content)

    def test_export_customers_csv_type_filter(self):
        company = Customer.objects.create(
            firm=self.firm,
            type=ContactType.COMPANY,
            first_name="Acme Corp",
        )
        resp = self.client.get(
            "/api/v1/integrations/export/customers.csv",
            data={"type": ContactType.COMPANY},
        )
        self.assertEqual(resp.status_code, 200)
        content = b"".join(resp.streaming_content).decode()
        self.assertIn("Acme Corp", content)
        self.assertNotIn("Jane", content)

    def test_export_customers_csv_tag_filter(self):
        if connection.vendor == "sqlite":
            self.skipTest("JSONField contains lookup not supported on SQLite")
        self.customer.tags = ["vip"]
        self.customer.save()
        Customer.objects.create(
            firm=self.firm,
            first_name="Bob",
            last_name="Smith",
            email="bob@example.com",
            tags=["regular"],
        )
        resp = self.client.get(
            "/api/v1/integrations/export/customers.csv",
            data={"tag": "vip"},
        )
        self.assertEqual(resp.status_code, 200)
        content = b"".join(resp.streaming_content).decode()
        self.assertIn("Jane", content)
        self.assertNotIn("Bob", content)



# ---------------------------------------------------------------------------
# Phase 4.0 — ERP API tests
# ---------------------------------------------------------------------------

import datetime

from crm.models import ExpenseItem, RevenueItem, TimeEntry


class TimeEntryAPITest(CRMFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_create_time_entry(self):
        payload = {
            "duration_minutes": 90,
            "description": "Design session",
            "is_billable": True,
            "record_id": str(self.record.id),
        }
        resp = self.client.post(
            "/api/v1/erp/time-entries",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["duration_minutes"], 90)
        self.assertEqual(data["record_id"], str(self.record.id))

    def test_list_time_entries(self):
        TimeEntry.objects.create(
            firm=self.firm,
            user=self.owner,
            duration_minutes=30,
            record=self.record,
        )
        resp = self.client.get("/api/v1/erp/time-entries")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_update_time_entry(self):
        entry = TimeEntry.objects.create(
            firm=self.firm,
            user=self.owner,
            duration_minutes=30,
        )
        resp = self.client.patch(
            f"/api/v1/erp/time-entries/{entry.id}",
            data=json.dumps({"duration_minutes": 60, "description": "Updated"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["duration_minutes"], 60)

    def test_delete_time_entry(self):
        entry = TimeEntry.objects.create(
            firm=self.firm,
            user=self.owner,
            duration_minutes=15,
        )
        resp = self.client.delete(f"/api/v1/erp/time-entries/{entry.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(TimeEntry.objects.filter(pk=entry.pk).exists())

    def test_firm_isolation(self):
        from firms.models import Firm, Membership, InvitationRole
        other_firm = Firm.objects.create(name="Other ERP Firm", subscription_tier="pro")
        other_user = __import__("users.models", fromlist=["User"]).User.objects.create_user(
            email="erp_other@test.com", password="pass"
        )
        Membership.objects.create(user=other_user, firm=other_firm, role=InvitationRole.OWNER)
        TimeEntry.objects.create(firm=other_firm, user=other_user, duration_minutes=45)
        resp = self.client.get("/api/v1/erp/time-entries")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)


class ExpenseAPITest(CRMFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_create_expense(self):
        payload = {
            "title": "Server hosting",
            "amount": "150.00",
            "currency": "CZK",
            "date": "2025-01-15",
            "recurrence": "monthly",
        }
        resp = self.client.post(
            "/api/v1/erp/expenses",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "Server hosting")
        self.assertEqual(data["recurrence"], "monthly")

    def test_list_expenses(self):
        ExpenseItem.objects.create(
            firm=self.firm,
            user=self.owner,
            title="Test expense",
            amount="100.00",
            date=datetime.date.today(),
        )
        resp = self.client.get("/api/v1/erp/expenses")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_delete_expense(self):
        item = ExpenseItem.objects.create(
            firm=self.firm,
            user=self.owner,
            title="To delete",
            amount="50.00",
            date=datetime.date.today(),
        )
        resp = self.client.delete(f"/api/v1/erp/expenses/{item.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ExpenseItem.objects.filter(pk=item.pk).exists())


class RevenueAPITest(CRMFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_create_revenue(self):
        payload = {
            "title": "Project payment",
            "amount": "5000.00",
            "currency": "CZK",
            "date": "2025-02-01",
            "record_id": str(self.record.id),
        }
        resp = self.client.post(
            "/api/v1/erp/revenues",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "Project payment")
        self.assertEqual(data["record_id"], str(self.record.id))

    def test_list_revenues(self):
        RevenueItem.objects.create(
            firm=self.firm,
            user=self.owner,
            title="Revenue item",
            amount="200.00",
            date=datetime.date.today(),
        )
        resp = self.client.get("/api/v1/erp/revenues")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)


class ReportsSummaryAPITest(CRMFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_reports_summary(self):
        today = datetime.date.today()
        TimeEntry.objects.create(firm=self.firm, user=self.owner, duration_minutes=120, is_billable=True)
        TimeEntry.objects.create(firm=self.firm, user=self.owner, duration_minutes=30, is_billable=False)
        ExpenseItem.objects.create(firm=self.firm, user=self.owner, title="E1", amount="200.00", date=today)
        RevenueItem.objects.create(firm=self.firm, user=self.owner, title="R1", amount="500.00", date=today)
        resp = self.client.get("/api/v1/erp/reports/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_minutes"], 150)
        self.assertEqual(data["billable_minutes"], 120)
        self.assertAlmostEqual(float(data["total_expenses"]), 200.0)
        self.assertAlmostEqual(float(data["total_revenues"]), 500.0)
        self.assertAlmostEqual(float(data["profit_loss"]), 300.0)


# ---------------------------------------------------------------------------
# Calendar / Task unification — scheduled-activity tools + auto-expire job
# ---------------------------------------------------------------------------

class ScheduledActivityToolsTest(CRMFixtureMixin, TestCase):
    """
    ``MeetingScheduledTool`` and ``CallScheduledTool`` must create a child
    ``Task`` (kind=meeting/call, auto_close_on_expiry=True) AND link the
    Activity to it via ``Activity.task``.  The Activity itself remains an
    immutable timeline log.
    """

    def _invoke(self, activity_type, metadata):
        from crm.streamline.registry import get_tool
        tool = get_tool(activity_type)
        self.assertIsNotNone(tool)
        activity = Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=activity_type,
            metadata=metadata,
        )
        tool.process_action(
            activity,
            self.record,
            {"metadata": metadata},
            {"firm": self.firm, "user": self.owner, "entity_title": self.record.title},
        )
        activity.refresh_from_db()
        return activity, Task.objects.get(id=activity.task_id)

    def test_call_scheduled_creates_task_kind_call(self):
        from crm.models import TaskStatus
        start = timezone.now() + dt.timedelta(hours=2)
        activity, task = self._invoke(
            "call_scheduled",
            {"start_at": start.isoformat(), "phone_number": "+420 123"},
        )
        self.assertEqual(task.kind, "call")
        self.assertEqual(task.status, TaskStatus.TODO)
        self.assertTrue(task.auto_close_on_expiry)
        self.assertEqual(task.firm_id, self.firm.id)
        self.assertEqual(task.record_id, self.record.id)
        self.assertIsNotNone(task.due_date)
        # Activity is linked back to the task.
        self.assertEqual(activity.task_id, task.id)

    def test_meeting_scheduled_creates_task_kind_meeting(self):
        start = timezone.now() + dt.timedelta(days=1)
        end = start + dt.timedelta(hours=1)
        activity, task = self._invoke(
            "meeting_scheduled",
            {
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "location": "HQ",
                "attendees": ["alice@example.com", "bob@example.com"],
            },
        )
        self.assertEqual(task.kind, "meeting")
        self.assertTrue(task.auto_close_on_expiry)
        self.assertEqual(task.location, "HQ")
        self.assertEqual(task.attendees, ["alice@example.com", "bob@example.com"])
        self.assertIsNotNone(task.due_date_end)
        self.assertEqual(activity.task_id, task.id)

    def test_call_scheduled_tool_registered(self):
        from crm.streamline.registry import get_tool
        self.assertIsNotNone(get_tool("call_scheduled"))

    def test_event_scheduled_creates_task_kind_event(self):
        from crm.models import TaskStatus
        start = timezone.now() + dt.timedelta(days=2)
        end = start + dt.timedelta(hours=2)
        activity, task = self._invoke(
            "event_scheduled",
            {
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "location": "Conference Hall A",
                "attendees": ["alice@example.com"],
                "description": "Annual roadmap review.",
            },
        )
        self.assertEqual(task.kind, "event")
        self.assertEqual(task.status, TaskStatus.TODO)
        self.assertTrue(task.auto_close_on_expiry)
        self.assertFalse(task.is_all_day)
        self.assertEqual(task.location, "Conference Hall A")
        self.assertEqual(task.attendees, ["alice@example.com"])
        self.assertEqual(activity.task_id, task.id)

    def test_event_scheduled_with_all_day_accepts_date_only(self):
        # When `all_day=true`, the SPA submits a plain ISO date — make
        # sure the tool turns it into a midnight-tz-aware datetime and
        # propagates `is_all_day=True` onto the linked Task.
        activity, task = self._invoke(
            "event_scheduled",
            {
                "start_at": "2026-05-04",
                "end_at": "2026-05-04",
                "all_day": True,
                "location": "",
            },
        )
        self.assertEqual(task.kind, "event")
        self.assertTrue(task.is_all_day)
        self.assertIsNotNone(task.due_date)
        self.assertEqual(task.due_date.year, 2026)
        self.assertEqual(task.due_date.month, 5)
        self.assertEqual(task.due_date.day, 4)
        self.assertEqual(task.due_date.hour, 0)
        self.assertEqual(task.due_date.minute, 0)

    def test_event_scheduled_render_payload_surfaces_metadata(self):
        from crm.streamline.registry import get_tool
        start = timezone.now() + dt.timedelta(days=3)
        activity = Activity.objects.create(
            record=self.record,
            user=self.owner,
            type="event_scheduled",
            metadata={
                "start_at": start.isoformat(),
                "all_day": True,
                "location": "Studio",
                "attendees": ["x@y.com", "z@y.com"],
                "description": "Workshop kickoff.",
            },
        )
        payload = get_tool("event_scheduled").render_payload(activity)
        self.assertTrue(payload["all_day"])
        self.assertEqual(payload["location"], "Studio")
        self.assertEqual(payload["attendees"], ["x@y.com", "z@y.com"])
        self.assertEqual(payload["description"], "Workshop kickoff.")


class AutoExpireScheduledTasksTest(CRMFixtureMixin, TestCase):
    """``auto_expire_scheduled_tasks`` transitions overdue scheduled tasks."""

    def _make_task(self, **overrides):
        defaults = dict(
            firm=self.firm,
            record=self.record,
            title="Scheduled call",
            kind="call",
            auto_close_on_expiry=True,
            due_date=timezone.now() - dt.timedelta(hours=5),
            assigned_to=self.owner,
        )
        defaults.update(overrides)
        return Task.objects.create(**defaults)

    def test_expires_overdue_call_past_grace(self):
        from crm.models import TaskStatus
        from crm.tasks import auto_expire_scheduled_tasks

        task = self._make_task()  # kind=call, grace=2h, due 5h ago → expired
        auto_expire_scheduled_tasks()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.EXPIRED)
        # An Activity of type TASK_EXPIRED is logged on the same record.
        self.assertTrue(
            Activity.objects.filter(
                record=self.record, task=task, type=ActivityType.TASK_EXPIRED
            ).exists()
        )

    def test_does_not_expire_within_grace(self):
        from crm.models import TaskStatus
        from crm.tasks import auto_expire_scheduled_tasks

        # Meeting kind has 24h grace; due 1h ago → still within grace.
        task = self._make_task(
            kind="meeting",
            due_date=timezone.now() - dt.timedelta(hours=1),
        )
        auto_expire_scheduled_tasks()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.TODO)
        self.assertFalse(
            Activity.objects.filter(task=task, type=ActivityType.TASK_EXPIRED).exists()
        )

    def test_skips_already_completed_task(self):
        from crm.models import TaskStatus
        from crm.tasks import auto_expire_scheduled_tasks

        task = self._make_task(is_completed=True, status=TaskStatus.DONE)
        auto_expire_scheduled_tasks()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.DONE)

    def test_skips_tasks_without_auto_close_flag(self):
        from crm.models import TaskStatus
        from crm.tasks import auto_expire_scheduled_tasks

        task = self._make_task(auto_close_on_expiry=False)
        auto_expire_scheduled_tasks()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.TODO)

    def test_uses_due_date_end_when_set(self):
        from crm.models import TaskStatus
        from crm.tasks import auto_expire_scheduled_tasks

        # Meeting due 30h ago, end 25h ago → past 24h grace from end → expire
        task = self._make_task(
            kind="meeting",
            due_date=timezone.now() - dt.timedelta(hours=30),
            due_date_end=timezone.now() - dt.timedelta(hours=25),
        )
        auto_expire_scheduled_tasks()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.EXPIRED)

    def test_returns_count_of_expired_tasks(self):
        from crm.tasks import auto_expire_scheduled_tasks

        self._make_task()
        self._make_task(title="Second")
        # Within grace — should not be counted.
        self._make_task(due_date=timezone.now() - dt.timedelta(minutes=10))
        count = auto_expire_scheduled_tasks()
        self.assertEqual(count, 2)


# ---------------------------------------------------------------------------
# Calendar / Task unification — follow-up: data migration + ActivityOut payload
# ---------------------------------------------------------------------------

class ScheduledActivityRenderPayloadTest(CRMFixtureMixin, TestCase):
    """``MeetingScheduledTool``/``CallScheduledTool`` must surface the
    linked Task's ``id``, ``status`` and ``kind`` via ``render_payload``
    so the SPA can render an inline status badge without a second request.
    """

    def _scheduled_payload_for(self, activity_type, metadata):
        from crm.streamline.registry import get_tool
        tool = get_tool(activity_type)
        activity = Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=activity_type,
            metadata=metadata,
        )
        tool.process_action(
            activity, self.record, {"metadata": metadata},
            {"firm": self.firm, "user": self.owner, "entity_title": self.record.title},
        )
        activity.refresh_from_db()
        return tool.render_payload(activity), activity

    def test_meeting_scheduled_render_payload_includes_task(self):
        start = timezone.now() + dt.timedelta(hours=3)
        payload, activity = self._scheduled_payload_for(
            "meeting_scheduled", {"start_at": start.isoformat()},
        )
        self.assertEqual(payload["task_id"], str(activity.task_id))
        self.assertEqual(payload["task_status"], "todo")
        self.assertEqual(payload["task_kind"], "meeting")
        self.assertFalse(payload["task_is_completed"])

    def test_call_scheduled_render_payload_includes_task(self):
        start = timezone.now() + dt.timedelta(hours=4)
        payload, activity = self._scheduled_payload_for(
            "call_scheduled", {"start_at": start.isoformat()},
        )
        self.assertEqual(payload["task_id"], str(activity.task_id))
        self.assertEqual(payload["task_kind"], "call")

    def test_render_payload_for_orphan_activity_has_null_task_fields(self):
        """An Activity not linked to a Task (e.g. legacy) renders nulls."""
        from crm.streamline.registry import get_tool
        activity = Activity.objects.create(
            record=self.record,
            user=self.owner,
            type="meeting_scheduled",
            metadata={"start_at": "2026-01-01T10:00:00Z"},
        )
        # Deliberately do NOT call process_action — simulates legacy data.
        payload = get_tool("meeting_scheduled").render_payload(activity)
        self.assertIsNone(payload["task_id"])
        self.assertIsNone(payload["task_status"])
        self.assertIsNone(payload["task_kind"])


class ActivityOutTaskIdExposureTest(CRMFixtureMixin, TestCase):
    """The HTTP API must expose ``task_id`` on each ``ActivityOut`` entry."""

    def setUp(self):
        super().setUp()
        Membership.objects.get_or_create(
            user=self.owner, firm=self.firm,
            defaults={"role": InvitationRole.OWNER},
        )

    def test_activity_out_serializer_exposes_task_id(self):
        from crm.api import _activity_out
        task = Task.objects.create(firm=self.firm, record=self.record, title="Parent task")
        activity = Activity.objects.create(
            record=self.record, user=self.owner, type="comment",
            content_text="hello", task=task,
        )
        out = _activity_out(activity, self.owner)
        self.assertEqual(out["task_id"], str(task.id))

    def test_activity_out_task_id_is_none_when_unlinked(self):
        from crm.api import _activity_out
        activity = Activity.objects.create(
            record=self.record, user=self.owner, type="comment", content_text="hi",
        )
        out = _activity_out(activity, self.owner)
        self.assertIsNone(out["task_id"])


class BackfillMeetingScheduledTasksMigrationTest(TestCase):
    """The 0043 data migration must create child Tasks for legacy
    ``meeting_scheduled`` Activities while remaining idempotent.
    """

    def setUp(self):
        from firms.models import Firm
        self.firm = Firm.objects.create(name="Migration Firm", subscription_tier="pro")
        self.customer = Customer.objects.create(
            firm=self.firm, first_name="Mig", last_name="Test",
        )
        self.record = PipelineRecord.objects.create(
            firm=self.firm, customer=self.customer, title="Mig PipelineRecord",
            status=RecordStatus.NEW, source=RecordSource.WEB,
        )

    def _run_migration(self):
        # Re-apply the data-migration function directly against the live
        # apps registry — emulates what Django would do during migrate.
        from django.apps import apps
        from importlib import import_module
        mod = import_module("crm.migrations.0003_backfill_meeting_scheduled_tasks")
        mod.backfill_meeting_scheduled_tasks(apps, None)

    def test_creates_task_for_legacy_meeting_scheduled_activity(self):
        start = (timezone.now() + dt.timedelta(days=1)).isoformat()
        a = Activity.objects.create(
            record=self.record, type=ActivityType.MEETING_SCHEDULED,
            metadata={
                "start_at": start,
                "location": "HQ",
                "attendees": ["x@example.com"],
            },
        )
        self.assertIsNone(a.task_id)
        self._run_migration()
        a.refresh_from_db()
        self.assertIsNotNone(a.task_id)
        task = Task.objects.get(id=a.task_id)
        self.assertEqual(task.kind, "meeting")
        self.assertTrue(task.auto_close_on_expiry)
        self.assertEqual(task.location, "HQ")
        self.assertEqual(task.attendees, ["x@example.com"])
        self.assertEqual(task.firm_id, self.firm.id)
        self.assertEqual(task.record_id, self.record.id)
        self.assertTrue(task.metadata.get("backfilled"))

    def test_skips_activities_already_linked(self):
        existing_task = Task.objects.create(
            firm=self.firm, record=self.record, title="Already linked",
        )
        a = Activity.objects.create(
            record=self.record, type=ActivityType.MEETING_SCHEDULED,
            metadata={"start_at": (timezone.now() + dt.timedelta(days=1)).isoformat()},
            task=existing_task,
        )
        before = Task.objects.count()
        self._run_migration()
        a.refresh_from_db()
        self.assertEqual(a.task_id, existing_task.id)
        self.assertEqual(Task.objects.count(), before)

    def test_skips_activities_without_start_at(self):
        a = Activity.objects.create(
            record=self.record, type=ActivityType.MEETING_SCHEDULED, metadata={},
        )
        before = Task.objects.count()
        self._run_migration()
        a.refresh_from_db()
        self.assertIsNone(a.task_id)
        self.assertEqual(Task.objects.count(), before)

    def test_is_idempotent_when_run_twice(self):
        Activity.objects.create(
            record=self.record, type=ActivityType.MEETING_SCHEDULED,
            metadata={"start_at": (timezone.now() + dt.timedelta(days=1)).isoformat()},
        )
        self._run_migration()
        count_after_first = Task.objects.count()
        self._run_migration()
        self.assertEqual(Task.objects.count(), count_after_first)

    def test_does_not_touch_non_meeting_scheduled_activities(self):
        Activity.objects.create(
            record=self.record, type="comment", content_text="hi",
        )
        before = Task.objects.count()
        self._run_migration()
        self.assertEqual(Task.objects.count(), before)


# ---------------------------------------------------------------------------
# Calendar / Task unification — calendar endpoint
# ---------------------------------------------------------------------------

class CalendarTasksAPITest(CRMAPIFixtureMixin, TestCase):
    """``GET /api/v1/crm/calendar/tasks`` returns tasks whose calendar
    slot overlaps the requested window, scoped by assignee."""

    URL = "/api/v1/crm/calendar/tasks"

    def setUp(self):
        super().setUp()
        # Window we'll query against in most tests: 2026-05-01 → 2026-05-08
        self.win_start = "2026-05-01T00:00:00+00:00"
        self.win_end = "2026-05-08T00:00:00+00:00"

        def mk(due, end=None, **kw):
            defaults = dict(
                firm=self.firm, record=self.record, title=kw.pop("title", "T"),
                assigned_to=kw.pop("assigned_to", self.owner),
                due_date=due, due_date_end=end,
            )
            defaults.update(kw)
            return Task.objects.create(**defaults)

        # Inside window
        self.t_in = mk(
            dt.datetime(2026, 5, 3, 10, 0, tzinfo=dt.timezone.utc),
            dt.datetime(2026, 5, 3, 11, 0, tzinfo=dt.timezone.utc),
            title="In window meeting", kind="meeting", location="HQ",
            attendees=["a@b.cz"],
        )
        # Spans the window (due before, end inside)
        self.t_span = mk(
            dt.datetime(2026, 4, 30, 23, 0, tzinfo=dt.timezone.utc),
            dt.datetime(2026, 5, 1, 1, 0, tzinfo=dt.timezone.utc),
            title="Spans start",
        )
        # Before window
        self.t_before = mk(
            dt.datetime(2026, 4, 20, 12, 0, tzinfo=dt.timezone.utc),
            title="Before",
        )
        # After window
        self.t_after = mk(
            dt.datetime(2026, 5, 20, 12, 0, tzinfo=dt.timezone.utc),
            title="After",
        )
        # No due_date — never appears
        self.t_no_due = mk(None, title="No due")
        # Worker's task in window
        self.t_worker = mk(
            dt.datetime(2026, 5, 4, 9, 0, tzinfo=dt.timezone.utc),
            assigned_to=self.worker, title="Worker meeting", kind="call",
        )
        # Watching task — owner is watcher, assigned to worker
        self.t_watch = mk(
            dt.datetime(2026, 5, 5, 14, 0, tzinfo=dt.timezone.utc),
            assigned_to=self.worker, title="Watched",
        )
        self.t_watch.watchers.add(self.owner)

    # -- happy path ---------------------------------------------------------

    def test_default_scope_returns_only_my_tasks_in_range(self):
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end})
        self.assertEqual(resp.status_code, 200)
        ids = {row["id"] for row in resp.json()}
        self.assertIn(str(self.t_in.id), ids)
        self.assertIn(str(self.t_span.id), ids)
        self.assertNotIn(str(self.t_before.id), ids)
        self.assertNotIn(str(self.t_after.id), ids)
        self.assertNotIn(str(self.t_no_due.id), ids)
        self.assertNotIn(str(self.t_worker.id), ids)  # owned by worker

    def test_response_shape_includes_calendar_fields(self):
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end})
        rows = {r["id"]: r for r in resp.json()}
        row = rows[str(self.t_in.id)]
        self.assertEqual(row["title"], "In window meeting")
        self.assertEqual(row["kind"], "meeting")
        self.assertEqual(row["location"], "HQ")
        self.assertEqual(row["attendees"], ["a@b.cz"])
        self.assertEqual(row["record_id"], str(self.record.id))
        self.assertEqual(row["assigned_to_id"], str(self.owner.id))
        self.assertIn("start", row)
        self.assertIn("end", row)

    def test_results_ordered_by_due_date(self):
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end})
        starts = [r["start"] for r in resp.json()]
        self.assertEqual(starts, sorted(starts))

    # -- scope --------------------------------------------------------------

    def test_owner_admin_scope_all_returns_everything(self):
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end, "assigned_to_id": "all"})
        ids = {r["id"] for r in resp.json()}
        self.assertIn(str(self.t_in.id), ids)
        self.assertIn(str(self.t_worker.id), ids)
        self.assertIn(str(self.t_watch.id), ids)

    def test_specific_user_id_filters_to_that_user(self):
        resp = self._get(self.URL, {
            "start": self.win_start, "end": self.win_end,
            "assigned_to_id": str(self.worker.id),
        })
        ids = {r["id"] for r in resp.json()}
        self.assertEqual(ids, {str(self.t_worker.id), str(self.t_watch.id)})

    def test_watching_scope_returns_watched_tasks(self):
        resp = self._get(self.URL, {
            "start": self.win_start, "end": self.win_end,
            "assigned_to_id": "watching",
        })
        ids = {r["id"] for r in resp.json()}
        self.assertEqual(ids, {str(self.t_watch.id)})

    def test_worker_cannot_see_other_users_via_all(self):
        self.client.logout()
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end, "assigned_to_id": "all"})
        ids = {r["id"] for r in resp.json()}
        # Worker only sees their own assignments even with "all"
        self.assertEqual(ids, {str(self.t_worker.id), str(self.t_watch.id)})

    def test_worker_querying_other_user_silently_narrows_to_self(self):
        self.client.logout()
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._get(self.URL, {
            "start": self.win_start, "end": self.win_end,
            "assigned_to_id": str(self.owner.id),
        })
        ids = {r["id"] for r in resp.json()}
        # Worker is silently narrowed to their own assignments
        self.assertNotIn(str(self.t_in.id), ids)
        self.assertIn(str(self.t_worker.id), ids)

    # -- filters ------------------------------------------------------------

    def test_kind_filter(self):
        resp = self._get(self.URL, {
            "start": self.win_start, "end": self.win_end,
            "assigned_to_id": "all", "kind": "meeting",
        })
        ids = {r["id"] for r in resp.json()}
        self.assertEqual(ids, {str(self.t_in.id)})

    def test_completed_excluded_by_default(self):
        self.t_in.is_completed = True
        self.t_in.status = "done"
        self.t_in.save()
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end})
        ids = {r["id"] for r in resp.json()}
        self.assertNotIn(str(self.t_in.id), ids)

    def test_expired_excluded_by_default(self):
        self.t_in.status = "expired"
        self.t_in.save()
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end})
        ids = {r["id"] for r in resp.json()}
        self.assertNotIn(str(self.t_in.id), ids)

    def test_include_completed_true_returns_them(self):
        self.t_in.is_completed = True
        self.t_in.status = "done"
        self.t_in.save()
        resp = self._get(self.URL, {
            "start": self.win_start, "end": self.win_end, "include_completed": "true",
        })
        ids = {r["id"] for r in resp.json()}
        self.assertIn(str(self.t_in.id), ids)

    def test_archived_excluded_by_default(self):
        self.t_in.is_archived = True
        self.t_in.save()
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end})
        ids = {r["id"] for r in resp.json()}
        self.assertNotIn(str(self.t_in.id), ids)

    # -- validation ---------------------------------------------------------

    def test_missing_start_returns_422_or_400(self):
        # Ninja raises 422 for missing required query params; either is acceptable
        resp = self._get(self.URL, {"end": self.win_end})
        self.assertIn(resp.status_code, (400, 422))

    def test_invalid_iso_returns_400(self):
        resp = self._get(self.URL, {"start": "not-a-date", "end": self.win_end})
        self.assertEqual(resp.status_code, 400)

    def test_end_before_start_returns_400(self):
        resp = self._get(self.URL, {"start": self.win_end, "end": self.win_start})
        self.assertEqual(resp.status_code, 400)

    def test_window_too_large_returns_400(self):
        resp = self._get(self.URL, {
            "start": "2026-01-01T00:00:00Z", "end": "2027-12-31T23:59:59Z",
        })
        self.assertEqual(resp.status_code, 400)

    def test_z_suffix_iso_is_accepted(self):
        resp = self._get(self.URL, {
            "start": "2026-05-01T00:00:00Z", "end": "2026-05-08T00:00:00Z",
        })
        self.assertEqual(resp.status_code, 200)

    # -- isolation ----------------------------------------------------------

    def test_firm_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm Cal")
        other_user = User.objects.create_user(email="other@cal.com", password="pass")
        Membership.objects.create(user=other_user, firm=other_firm, role=InvitationRole.OWNER)
        Task.objects.create(
            firm=other_firm, title="Cross-firm",
            due_date=dt.datetime(2026, 5, 3, 10, 0, tzinfo=dt.timezone.utc),
            assigned_to=other_user,
        )
        resp = self._get(self.URL, {"start": self.win_start, "end": self.win_end, "assigned_to_id": "all"})
        titles = {r["title"] for r in resp.json()}
        self.assertNotIn("Cross-firm", titles)

    def test_unauthenticated_returns_401_or_403(self):
        self.client.logout()
        resp = self.client.get(self.URL, {"start": self.win_start, "end": self.win_end}, **self.firm_headers())
        self.assertIn(resp.status_code, (401, 403))


# ---------------------------------------------------------------------------
# Calendar / Task unification — outcome prompt (PR4)
# ---------------------------------------------------------------------------

class TaskOutcomePromptJobTest(CRMFixtureMixin, TestCase):
    """The auto-expire job sends a one-shot ``task.outcome_prompt`` notification
    once ``due_date_end`` has elapsed, before the grace period closes."""

    def _make(self, **overrides):
        defaults = dict(
            firm=self.firm,
            record=self.record,
            title="Calendar meeting",
            kind="meeting",
            auto_close_on_expiry=True,
            due_date=timezone.now() - dt.timedelta(hours=2),
            assigned_to=self.owner,
        )
        defaults.update(overrides)
        return Task.objects.create(**defaults)

    def test_prompt_sent_within_grace_window(self):
        from crm.models import Notification
        from crm.tasks import auto_expire_scheduled_tasks

        task = self._make()  # meeting, 24h grace, due 2h ago → in grace
        auto_expire_scheduled_tasks()

        task.refresh_from_db()
        self.assertIsNotNone(task.outcome_prompted_at)
        notes = Notification.objects.filter(user=self.owner, event="task.outcome_prompt")
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes.first().payload["task_id"], str(task.id))

    def test_prompt_sent_only_once(self):
        from crm.models import Notification
        from crm.tasks import auto_expire_scheduled_tasks

        task = self._make()
        auto_expire_scheduled_tasks()
        auto_expire_scheduled_tasks()
        auto_expire_scheduled_tasks()

        task.refresh_from_db()
        self.assertEqual(
            Notification.objects.filter(user=self.owner, event="task.outcome_prompt").count(),
            1,
        )
        self.assertIsNotNone(task.outcome_prompted_at)

    def test_prompt_includes_watchers(self):
        from crm.models import Notification
        from crm.tasks import auto_expire_scheduled_tasks

        task = self._make()
        task.watchers.add(self.worker)
        auto_expire_scheduled_tasks()

        recipients = set(
            Notification.objects.filter(event="task.outcome_prompt")
            .values_list("user_id", flat=True)
        )
        self.assertEqual(recipients, {self.owner.id, self.worker.id})

    def test_no_prompt_before_due_date(self):
        from crm.models import Notification
        from crm.tasks import auto_expire_scheduled_tasks

        # Future task — should not produce any prompt or expire.
        task = self._make(due_date=timezone.now() + dt.timedelta(hours=2))
        auto_expire_scheduled_tasks()

        task.refresh_from_db()
        self.assertIsNone(task.outcome_prompted_at)
        self.assertFalse(
            Notification.objects.filter(event="task.outcome_prompt").exists()
        )

    def test_generic_kind_skipped_no_prompt(self):
        """Generic tasks have zero grace → no prompt window, just direct expiry."""
        from crm.models import Notification
        from crm.tasks import auto_expire_scheduled_tasks

        self._make(kind="generic", due_date=timezone.now() - dt.timedelta(minutes=5))
        auto_expire_scheduled_tasks()

        self.assertFalse(
            Notification.objects.filter(event="task.outcome_prompt").exists()
        )

    def test_prompt_then_expire_when_grace_elapses(self):
        """A task prompted within grace is auto-expired once grace elapses."""
        from crm.models import TaskStatus
        from crm.tasks import auto_expire_scheduled_tasks

        # Kind=call → 2h grace. due 1h ago → in grace.
        task = self._make(kind="call", due_date=timezone.now() - dt.timedelta(hours=1))
        auto_expire_scheduled_tasks()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.TODO)
        self.assertIsNotNone(task.outcome_prompted_at)

        # Now move due_date back so grace has elapsed and re-run.
        task.due_date = timezone.now() - dt.timedelta(hours=5)
        task.save(update_fields=["due_date"])
        auto_expire_scheduled_tasks()
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.EXPIRED)


class TaskOutcomeEndpointTest(CRMAPIFixtureMixin, TestCase):
    """``POST /api/v1/crm/tasks/{id}/outcome`` — held / rescheduled / no_show."""

    def setUp(self):
        super().setUp()
        from crm.models import Task
        self.task = Task.objects.create(
            firm=self.firm,
            record=self.record,
            title="Calendar call",
            kind="call",
            auto_close_on_expiry=True,
            due_date=dt.datetime(2026, 4, 30, 10, 0, tzinfo=dt.timezone.utc),
            due_date_end=dt.datetime(2026, 4, 30, 10, 30, tzinfo=dt.timezone.utc),
            assigned_to=self.owner,
            outcome_prompted_at=dt.datetime(2026, 4, 30, 11, 0, tzinfo=dt.timezone.utc),
        )

    def _url(self):
        return f"/api/v1/crm/tasks/{self.task.id}/outcome"

    # -- held ---------------------------------------------------------------

    def test_held_marks_done_and_logs_call_activity(self):
        from crm.models import ActivityType, TaskStatus

        resp = self._post(self._url(), {"action": "held", "note": "Spoke with client, all good."})
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_completed)
        self.assertEqual(self.task.status, TaskStatus.DONE)
        self.assertEqual(self.task.completed_by, self.owner)

        acts = Activity.objects.filter(task=self.task, type=ActivityType.CALL)
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().content_text, "Spoke with client, all good.")
        self.assertEqual(acts.first().metadata.get("outcome"), "held")
        self.assertEqual(acts.first().record, self.record)

    def test_held_meeting_kind_logs_meeting_activity(self):
        from crm.models import ActivityType
        self.task.kind = "meeting"
        self.task.save(update_fields=["kind"])

        resp = self._post(self._url(), {"action": "held"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Activity.objects.filter(task=self.task, type=ActivityType.MEETING).exists()
        )

    def test_held_already_completed_returns_400(self):
        self.task.is_completed = True
        self.task.save(update_fields=["is_completed"])
        resp = self._post(self._url(), {"action": "held"})
        self.assertEqual(resp.status_code, 400)

    # -- rescheduled --------------------------------------------------------

    def test_rescheduled_updates_due_date_and_resets_prompt(self):
        from crm.models import ActivityType, TaskStatus

        new_due = "2026-05-15T14:00:00+00:00"
        resp = self._post(self._url(), {
            "action": "rescheduled",
            "new_due_date": new_due,
            "new_due_date_end": "2026-05-15T15:00:00+00:00",
            "note": "Client asked to move",
        })
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.due_date.isoformat(), "2026-05-15T14:00:00+00:00")
        self.assertEqual(self.task.due_date_end.isoformat(), "2026-05-15T15:00:00+00:00")
        self.assertIsNone(self.task.outcome_prompted_at)
        self.assertFalse(self.task.is_completed)
        self.assertEqual(self.task.status, TaskStatus.TODO)

        # Logs a DUE_DATE_CHANGE Activity with outcome=rescheduled metadata.
        acts = Activity.objects.filter(task=self.task, type=ActivityType.DUE_DATE_CHANGE)
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().metadata.get("outcome"), "rescheduled")
        self.assertEqual(acts.first().metadata.get("note"), "Client asked to move")

    def test_rescheduled_resurrects_expired_task(self):
        from crm.models import TaskStatus
        self.task.status = TaskStatus.EXPIRED
        self.task.save(update_fields=["status"])

        resp = self._post(self._url(), {
            "action": "rescheduled",
            "new_due_date": "2026-05-15T14:00:00+00:00",
        })
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.TODO)

    def test_rescheduled_requires_new_due_date(self):
        resp = self._post(self._url(), {"action": "rescheduled"})
        self.assertEqual(resp.status_code, 400)

    def test_rescheduled_validates_end_after_start(self):
        resp = self._post(self._url(), {
            "action": "rescheduled",
            "new_due_date": "2026-05-15T14:00:00+00:00",
            "new_due_date_end": "2026-05-15T13:00:00+00:00",
        })
        self.assertEqual(resp.status_code, 400)

    # -- no_show ------------------------------------------------------------

    def test_no_show_marks_expired_and_logs_activity(self):
        from crm.models import ActivityType, TaskStatus

        resp = self._post(self._url(), {"action": "no_show", "note": "Klient nedorazil"})
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.EXPIRED)
        self.assertFalse(self.task.is_completed)  # not "done"

        acts = Activity.objects.filter(task=self.task, type=ActivityType.TASK_EXPIRED)
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().metadata.get("outcome"), "no_show")
        self.assertEqual(acts.first().content_text, "Klient nedorazil")

    # -- validation & permissions -------------------------------------------

    def test_invalid_action_returns_400(self):
        resp = self._post(self._url(), {"action": "bogus"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_task_returns_404(self):
        import uuid
        resp = self._post(f"/api/v1/crm/tasks/{uuid.uuid4()}/outcome", {"action": "held"})
        self.assertEqual(resp.status_code, 404)

    def test_cross_firm_task_returns_404(self):
        other_firm = Firm.objects.create(name="Other Firm Outcome")
        from crm.models import Task
        other_task = Task.objects.create(
            firm=other_firm,
            title="X",
            kind="call",
            due_date=dt.datetime(2026, 4, 30, 10, 0, tzinfo=dt.timezone.utc),
        )
        resp = self._post(f"/api/v1/crm/tasks/{other_task.id}/outcome", {"action": "held"})
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_returns_401_or_403(self):
        self.client.logout()
        resp = self.client.post(
            self._url(),
            data=json.dumps({"action": "held"}),
            content_type="application/json",
            **self.firm_headers(),
        )
        self.assertIn(resp.status_code, (401, 403))


# ===========================================================================
# v2.3 — DASHBOARD WIDGET ENDPOINTS
# ===========================================================================

from crm.models import Category, Stage, Checkpoint  # noqa: E402


class DashboardAPITest(CRMAPIFixtureMixin, TestCase):
    """Tests for ``/api/v1/crm/stats`` filters and the new dashboard endpoints."""

    def setUp(self):
        super().setUp()
        # Pipeline taxonomy
        self.category = Category.objects.create(firm=self.firm, name="Sales")
        self.stage_new = Stage.objects.create(category=self.category, name="New", order=0)
        self.stage_won = Stage.objects.create(
            category=self.category, name="Won", order=1, is_terminal=True, is_won=True
        )
        self.other_category = Category.objects.create(firm=self.firm, name="Support")

        # Records: one in each category, one WON
        self.record.category = self.category
        self.record.current_stage = self.stage_new
        self.record.value = 1000
        self.record.currency = self.firm.default_currency
        self.record.save()

        self.record_won = PipelineRecord.objects.create(
            firm=self.firm,
            customer=self.customer,
            title="Won Deal",
            status=RecordStatus.WON,
            source=RecordSource.WEB,
            category=self.category,
            current_stage=self.stage_won,
            value=2500,
            currency=self.firm.default_currency,
            assigned_to=self.owner,
        )
        self.record_other = PipelineRecord.objects.create(
            firm=self.firm,
            customer=self.customer,
            title="Support Ticket",
            status=RecordStatus.NEW,
            source=RecordSource.WEB,
            category=self.other_category,
            value=500,
            currency=self.firm.default_currency,
        )

    # ---- /stats with filters --------------------------------------------

    def test_stats_returns_canonical_and_range_fields(self):
        resp = self._get("/api/v1/crm/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # New keys present
        for key in (
            "pipeline_value_canonical",
            "won_value_canonical",
            "canonical_currency",
            "avg_cycle_days",
            "created_in_range",
            "won_in_range",
            "lost_in_range",
            "range",
            "currency_breakdown",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["canonical_currency"], self.firm.default_currency)
        self.assertEqual(data["range"], "all")

    def test_stats_filters_by_category(self):
        resp = self._get("/api/v1/crm/stats", {"category_id": str(self.category.id)})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Only 2 records belong to Sales category (record + record_won)
        self.assertEqual(data["total_records"], 2)

    def test_stats_filters_by_owner_me(self):
        # record_won is assigned_to owner, others are not
        resp = self._get("/api/v1/crm/stats", {"owner_id": "me"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_records"], 1)

    def test_stats_filters_by_range(self):
        resp = self._get("/api/v1/crm/stats", {"range": "7d"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["range"], "7d")
        # All records were created just now → in range
        self.assertGreaterEqual(data["created_in_range"], 3)

    # ---- /dashboard/category-overview -----------------------------------

    def test_category_overview_lists_active_categories(self):
        resp = self._get("/api/v1/crm/dashboard/category-overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["canonical_currency"], self.firm.default_currency)
        names = [item["name"] for item in data["items"]]
        self.assertIn("Sales", names)
        self.assertIn("Support", names)
        sales = next(i for i in data["items"] if i["name"] == "Sales")
        self.assertEqual(sales["records_total"], 2)
        self.assertEqual(sales["records_won"], 1)
        self.assertEqual(len(sales["sparkline"]), 30)

    # ---- /dashboard/stage-funnel ----------------------------------------

    def test_stage_funnel_for_category(self):
        resp = self._get(
            "/api/v1/crm/dashboard/stage-funnel",
            {"category_id": str(self.category.id)},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["category_id"], str(self.category.id))
        self.assertEqual(len(data["stages"]), 2)
        self.assertEqual(data["stages"][0]["count"], 1)  # New
        self.assertEqual(data["stages"][1]["count"], 1)  # Won

    def test_stage_funnel_unknown_category_returns_404(self):
        resp = self._get(
            "/api/v1/crm/dashboard/stage-funnel",
            {"category_id": "00000000-0000-0000-0000-000000000000"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_stage_funnel_default_picks_first_active_category(self):
        resp = self._get("/api/v1/crm/dashboard/stage-funnel")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Either Sales or Support — both active. We just want a category id.
        self.assertIsNotNone(data["category_id"])

    # ---- /dashboard/trend ------------------------------------------------

    def test_trend_returns_points_for_default_range(self):
        resp = self._get("/api/v1/crm/dashboard/trend", {"metric": "created"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["metric"], "created")
        self.assertGreater(len(data["points"]), 0)
        # Sum of points over 30d should at least equal the records we created.
        total = sum(p["value"] for p in data["points"])
        self.assertGreaterEqual(total, 3)

    def test_trend_invalid_metric_falls_back_to_created(self):
        resp = self._get("/api/v1/crm/dashboard/trend", {"metric": "nonsense"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["metric"], "created")

    # ---- /dashboard/my-day ----------------------------------------------

    def test_my_day_groups_tasks_by_due_date(self):
        now = timezone.now()
        Task.objects.create(
            firm=self.firm,
            assigned_to=self.owner,
            record=self.record,
            title="Overdue task",
            due_date=now - dt.timedelta(days=2),
        )
        Task.objects.create(
            firm=self.firm,
            assigned_to=self.owner,
            record=self.record,
            title="Today task",
            due_date=now + dt.timedelta(hours=1),
        )
        Task.objects.create(
            firm=self.firm,
            assigned_to=self.owner,
            record=self.record,
            title="Next-week task",
            due_date=now + dt.timedelta(days=3),
        )
        resp = self._get("/api/v1/crm/dashboard/my-day")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["overdue"]), 1)
        self.assertEqual(len(data["today"]), 1)
        # this_week may also include checkpoints
        self.assertGreaterEqual(len(data["this_week"]), 1)

    def test_my_day_includes_checkpoints(self):
        Checkpoint.objects.create(
            record=self.record_won,
            name="Project kickoff",
            date=timezone.now().date() + dt.timedelta(days=2),
        )
        resp = self._get("/api/v1/crm/dashboard/my-day")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [item["title"] for item in data["this_week"]]
        self.assertIn("Project kickoff", names)

    # ---- /dashboard/stale-records ---------------------------------------

    def test_stale_records_uses_threshold(self):
        # Record older than threshold and never had any activity → stale
        old = PipelineRecord.objects.create(
            firm=self.firm,
            customer=self.customer,
            title="Old Record",
            status=RecordStatus.NEW,
            source=RecordSource.WEB,
            category=self.category,
        )
        PipelineRecord.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - dt.timedelta(days=30),
            created_at=timezone.now() - dt.timedelta(days=30),
        )
        resp = self._get("/api/v1/crm/dashboard/stale-records", {"days": 14})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["threshold_days"], 14)
        ids = {item["id"] for item in data["items"]}
        self.assertIn(str(old.id), ids)

    # ---- /dashboard/checkpoints -----------------------------------------

    def test_checkpoints_lists_upcoming(self):
        # Make record assigned to owner so it appears in default scope=mine
        self.record.assigned_to = self.owner
        self.record.save()
        cp = Checkpoint.objects.create(
            record=self.record,
            name="Next milestone",
            date=timezone.now().date() + dt.timedelta(days=3),
        )
        resp = self._get("/api/v1/crm/dashboard/checkpoints")
        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.json()["items"]}
        self.assertIn(str(cp.id), ids)

    # ---- /dashboard/team-leaderboard ------------------------------------

    def test_team_leaderboard_admin_only(self):
        # owner is OWNER → should pass
        resp = self._get("/api/v1/crm/dashboard/team-leaderboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["canonical_currency"], self.firm.default_currency)
        self.assertGreaterEqual(len(data["entries"]), 1)

    def test_team_leaderboard_forbidden_for_worker(self):
        self.client.logout()
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._get("/api/v1/crm/dashboard/team-leaderboard")
        self.assertEqual(resp.status_code, 403)


# ===========================================================================
# Phase 3 – CategoryGrant, RecordGrant, audit log signals, users_with_access()
# ===========================================================================

import uuid as _uuid

from crm.models import Category, CategoryGrant, PipelineRecord, RecordGrant


class CategoryGrantModelTest(TestCase):
    """Unit tests for CategoryGrant model."""

    def setUp(self):
        self.owner = User.objects.create_user(email="catgrant_owner@ex.com", password="pass")
        self.other = User.objects.create_user(email="catgrant_other@ex.com", password="pass")
        self.firm = Firm.objects.create(name="CatGrant Test Firm")
        self.membership = Membership.objects.create(
            user=self.owner, firm=self.firm, role=InvitationRole.OWNER
        )
        self.category = Category.objects.create(firm=self.firm, name="Sales")

    def test_create_user_grant(self):
        """A 'user' CategoryGrant can be created."""
        grant = CategoryGrant.objects.create(
            category=self.category,
            principal_type="user",
            principal_id=self.other.id,
            level="view",
            granted_by=self.membership,
        )
        self.assertEqual(grant.level, "view")
        self.assertEqual(grant.principal_type, "user")

    def test_create_team_grant(self):
        """A 'team' CategoryGrant can be created."""
        team_id = _uuid.uuid4()
        grant = CategoryGrant.objects.create(
            category=self.category,
            principal_type="team",
            principal_id=team_id,
            level="edit",
        )
        self.assertEqual(grant.principal_type, "team")
        self.assertEqual(str(grant.principal_id), str(team_id))

    def test_unique_principal_constraint(self):
        """Duplicate (category, principal_type, principal_id) is rejected."""
        from django.db import IntegrityError
        uid = _uuid.uuid4()
        CategoryGrant.objects.create(
            category=self.category, principal_type="user", principal_id=uid, level="view"
        )
        with self.assertRaises(Exception):
            CategoryGrant.objects.create(
                category=self.category, principal_type="user", principal_id=uid, level="edit"
            )

    def test_str_representation(self):
        """CategoryGrant __str__ includes level, principal info, and category."""
        grant = CategoryGrant.objects.create(
            category=self.category,
            principal_type="user",
            principal_id=self.other.id,
            level="manage",
        )
        s = str(grant)
        self.assertIn("manage", s)
        self.assertIn("user", s)

    def test_users_with_access_method(self):
        """Category.users_with_access() returns users with a user grant."""
        CategoryGrant.objects.create(
            category=self.category,
            principal_type="user",
            principal_id=self.other.id,
            level="view",
        )
        qs = self.category.users_with_access()
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.other.id, ids)
        self.assertNotIn(self.owner.id, ids)

    def test_users_with_access_excludes_team_grants(self):
        """Category.users_with_access() does not return teams."""
        CategoryGrant.objects.create(
            category=self.category,
            principal_type="team",
            principal_id=_uuid.uuid4(),
            level="view",
        )
        qs = self.category.users_with_access()
        self.assertEqual(qs.count(), 0)

    def test_cascade_on_category_delete(self):
        """Deleting a Category cascades to its grants."""
        CategoryGrant.objects.create(
            category=self.category,
            principal_type="user",
            principal_id=self.other.id,
            level="view",
        )
        self.category.delete()
        self.assertEqual(CategoryGrant.objects.count(), 0)


class RecordGrantModelTest(TestCase):
    """Unit tests for RecordGrant model."""

    def setUp(self):
        self.owner = User.objects.create_user(email="recgrant_owner@ex.com", password="pass")
        self.other = User.objects.create_user(email="recgrant_other@ex.com", password="pass")
        self.firm = Firm.objects.create(name="RecGrant Test Firm")
        self.membership = Membership.objects.create(
            user=self.owner, firm=self.firm, role=InvitationRole.OWNER
        )
        self.record = PipelineRecord.objects.create(
            firm=self.firm, title="Test Record", created_by=self.owner
        )

    def test_create_user_grant(self):
        """A 'user' RecordGrant can be created."""
        grant = RecordGrant.objects.create(
            record=self.record,
            principal_type="user",
            principal_id=self.other.id,
            level="view",
            granted_by=self.membership,
        )
        self.assertEqual(grant.level, "view")

    def test_create_with_expiry(self):
        """RecordGrant can have an expires_at timestamp."""
        from django.utils import timezone
        expires = timezone.now() + dt.timedelta(days=30)
        grant = RecordGrant.objects.create(
            record=self.record,
            principal_type="user",
            principal_id=self.other.id,
            level="view",
            expires_at=expires,
        )
        self.assertIsNotNone(grant.expires_at)

    def test_unique_principal_constraint(self):
        """Duplicate (record, principal_type, principal_id) is rejected."""
        uid = _uuid.uuid4()
        RecordGrant.objects.create(
            record=self.record, principal_type="user", principal_id=uid, level="view"
        )
        with self.assertRaises(Exception):
            RecordGrant.objects.create(
                record=self.record, principal_type="user", principal_id=uid, level="edit"
            )

    def test_str_representation(self):
        """RecordGrant __str__ includes level and principal type."""
        grant = RecordGrant.objects.create(
            record=self.record,
            principal_type="user",
            principal_id=self.other.id,
            level="edit",
        )
        s = str(grant)
        self.assertIn("edit", s)
        self.assertIn("user", s)

    def test_users_with_access_method(self):
        """PipelineRecord.users_with_access() returns users with a user grant."""
        RecordGrant.objects.create(
            record=self.record,
            principal_type="user",
            principal_id=self.other.id,
            level="view",
        )
        qs = self.record.users_with_access()
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.other.id, ids)
        self.assertNotIn(self.owner.id, ids)

    def test_users_with_access_excludes_team_grants(self):
        """PipelineRecord.users_with_access() does not return teams."""
        RecordGrant.objects.create(
            record=self.record,
            principal_type="team",
            principal_id=_uuid.uuid4(),
            level="view",
        )
        qs = self.record.users_with_access()
        self.assertEqual(qs.count(), 0)

    def test_cascade_on_record_delete(self):
        """Deleting a PipelineRecord cascades to its grants."""
        RecordGrant.objects.create(
            record=self.record,
            principal_type="user",
            principal_id=self.other.id,
            level="view",
        )
        record_id = self.record.pk
        self.record.delete()
        self.assertEqual(RecordGrant.objects.filter(record_id=record_id).count(), 0)


class GrantAuditSignalTest(TestCase):
    """Post-save / post-delete signals on grants create PermissionAuditLog entries."""

    def setUp(self):
        self.owner = User.objects.create_user(email="grtsig_owner@ex.com", password="pass")
        self.firm = Firm.objects.create(name="Grant Signal Firm")
        self.category = Category.objects.create(firm=self.firm, name="Test Category")
        self.record = PipelineRecord.objects.create(
            firm=self.firm, title="Signal Record", created_by=self.owner
        )

    def test_category_grant_create_logs_audit(self):
        """Creating a CategoryGrant logs 'category_grant.created' in audit."""
        from firms.models import PermissionAuditLog
        initial = PermissionAuditLog.objects.filter(action="category_grant.created").count()
        CategoryGrant.objects.create(
            category=self.category,
            principal_type="user",
            principal_id=self.owner.id,
            level="view",
        )
        new_count = PermissionAuditLog.objects.filter(action="category_grant.created").count()
        self.assertEqual(new_count, initial + 1)

    def test_category_grant_delete_logs_audit(self):
        """Deleting a CategoryGrant logs 'category_grant.deleted' in audit."""
        from firms.models import PermissionAuditLog
        grant = CategoryGrant.objects.create(
            category=self.category,
            principal_type="user",
            principal_id=self.owner.id,
            level="view",
        )
        initial = PermissionAuditLog.objects.filter(action="category_grant.deleted").count()
        grant.delete()
        new_count = PermissionAuditLog.objects.filter(action="category_grant.deleted").count()
        self.assertEqual(new_count, initial + 1)

    def test_record_grant_create_logs_audit(self):
        """Creating a RecordGrant logs 'record_grant.created' in audit."""
        from firms.models import PermissionAuditLog
        initial = PermissionAuditLog.objects.filter(action="record_grant.created").count()
        RecordGrant.objects.create(
            record=self.record,
            principal_type="user",
            principal_id=self.owner.id,
            level="view",
        )
        new_count = PermissionAuditLog.objects.filter(action="record_grant.created").count()
        self.assertEqual(new_count, initial + 1)

    def test_record_grant_delete_logs_audit(self):
        """Deleting a RecordGrant logs 'record_grant.deleted' in audit."""
        from firms.models import PermissionAuditLog
        grant = RecordGrant.objects.create(
            record=self.record,
            principal_type="user",
            principal_id=self.owner.id,
            level="view",
        )
        initial = PermissionAuditLog.objects.filter(action="record_grant.deleted").count()
        grant.delete()
        new_count = PermissionAuditLog.objects.filter(action="record_grant.deleted").count()
        self.assertEqual(new_count, initial + 1)


# ===========================================================================
# Phase 4 – Query scoping tests (crm.permissions)
# ===========================================================================

class FilterRecordsQsTest(TestCase):
    """Tests for filter_records_qs with PERMISSIONS_V2_ENABLED=True."""

    def setUp(self):
        from django.test import RequestFactory
        self.factory = RequestFactory()
        self.firm = Firm.objects.create(name="Scope Firm", subscription_tier="pro")
        self.owner = User.objects.create_user(email="scope_owner@example.com", password="pass")
        self.worker_a = User.objects.create_user(email="scope_workerA@example.com", password="pass")
        self.worker_b = User.objects.create_user(email="scope_workerB@example.com", password="pass")
        self.owner_m = Membership.objects.create(
            user=self.owner, firm=self.firm, role=InvitationRole.OWNER, default_scope="all"
        )
        self.worker_a_m = Membership.objects.create(
            user=self.worker_a, firm=self.firm, role=InvitationRole.MEMBER, default_scope="own"
        )
        self.worker_b_m = Membership.objects.create(
            user=self.worker_b, firm=self.firm, role=InvitationRole.MEMBER, default_scope="own"
        )
        # Create records
        self.record_a = PipelineRecord.objects.create(
            firm=self.firm, title="Record A", status=RecordStatus.NEW,
            created_by=self.worker_a, assigned_to=self.worker_a,
        )
        self.record_b = PipelineRecord.objects.create(
            firm=self.firm, title="Record B", status=RecordStatus.NEW,
            created_by=self.worker_b, assigned_to=self.worker_b,
        )
        self.record_unowned = PipelineRecord.objects.create(
            firm=self.firm, title="Unowned Record", status=RecordStatus.NEW,
            created_by=None, assigned_to=None,
        )

    def _make_request(self, user, membership):
        from django.test import RequestFactory
        req = RequestFactory().get("/")
        req.user = user
        req.firm = self.firm
        req.membership = membership
        return req

    def test_flag_off_returns_all(self):
        """Without a membership, filter returns empty queryset."""
        from crm.permissions import filter_records_qs
        from django.test import RequestFactory
        req = RequestFactory().get("/")
        req.user = self.worker_a
        req.firm = self.firm
        req.membership = None
        qs = filter_records_qs(PipelineRecord.objects.filter(firm=self.firm), req)
        self.assertEqual(qs.count(), 0)

    def test_owner_sees_all_records(self):
        """Owner sees every record."""
        from crm.permissions import filter_records_qs
        req = self._make_request(self.owner, self.owner_m)
        qs = filter_records_qs(PipelineRecord.objects.filter(firm=self.firm), req)
        self.assertIn(self.record_a, qs)
        self.assertIn(self.record_b, qs)
        self.assertIn(self.record_unowned, qs)

    def test_worker_own_scope_sees_only_own(self):
        """Worker with scope=own sees only records assigned to or created by them."""
        from crm.permissions import filter_records_qs
        req = self._make_request(self.worker_a, self.worker_a_m)
        qs = filter_records_qs(PipelineRecord.objects.filter(firm=self.firm), req)
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.record_a.id, ids)
        self.assertNotIn(self.record_b.id, ids)
        self.assertNotIn(self.record_unowned.id, ids)

    def test_worker_all_scope_sees_all(self):
        """Worker with scope=all sees every record."""
        from crm.permissions import filter_records_qs
        self.worker_a_m.default_scope = "all"
        self.worker_a_m.save()
        req = self._make_request(self.worker_a, self.worker_a_m)
        qs = filter_records_qs(PipelineRecord.objects.filter(firm=self.firm), req)
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.record_b.id, ids)
        self.assertIn(self.record_unowned.id, ids)

    def test_record_grant_gives_access(self):
        """A RecordGrant allows a worker to see a record outside their scope."""
        from crm.models import RecordGrant
        from crm.permissions import filter_records_qs
        # worker_a has scope=own, but gets a direct grant to record_b
        RecordGrant.objects.create(
            record=self.record_b,
            principal_type="user",
            principal_id=self.worker_a.id,
            level="view",
        )
        req = self._make_request(self.worker_a, self.worker_a_m)
        qs = filter_records_qs(PipelineRecord.objects.filter(firm=self.firm), req)
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.record_a.id, ids)
        self.assertIn(self.record_b.id, ids)

    def test_no_membership_returns_none(self):
        """Without membership, filter returns empty queryset."""
        from crm.permissions import filter_records_qs
        from django.test import RequestFactory
        req = RequestFactory().get("/")
        req.user = self.worker_a
        req.firm = self.firm
        req.membership = None
        qs = filter_records_qs(PipelineRecord.objects.filter(firm=self.firm), req)
        self.assertEqual(qs.count(), 0)


class ResolveEffectivePermissionsTest(TestCase):
    """Tests for resolve_effective_permissions."""

    def setUp(self):
        self.firm = Firm.objects.create(name="Eff Perm Firm")
        self.user = User.objects.create_user(email="effperm@example.com", password="pass")
        self.membership = Membership.objects.create(
            user=self.user, firm=self.firm, role=InvitationRole.MEMBER
        )

    def test_fallback_to_legacy_when_no_db_roles(self):
        """Without DB roles, falls back to LEGACY_ROLE_PERMISSIONS."""
        from crm.permissions import resolve_effective_permissions
        perms = resolve_effective_permissions(self.membership)
        self.assertIn("record.view", perms)
        self.assertIn("record.create", perms)
        self.assertNotIn("billing.manage", perms)

    def test_uses_db_roles_when_assigned(self):
        """With DB roles, uses their permission set."""
        from crm.permissions import resolve_effective_permissions
        from firms.models import PermissionRecord, Role, RolePermission
        role = Role.objects.create(firm=self.firm, code="custom", name="Custom Role")
        perm = PermissionRecord.objects.get_or_create(
            code="record.view", defaults={"group": "Records", "description": "View records"}
        )[0]
        RolePermission.objects.create(role=role, permission=perm)
        self.membership.roles.add(role)
        perms = resolve_effective_permissions(self.membership)
        self.assertIn("record.view", perms)


# ---------------------------------------------------------------------------
# Phase 5 – Streamline visibility tests
# ---------------------------------------------------------------------------

class StreamlineVisibilityTests(TestCase):
    """
    Phase 5: verify that Activity.visibility='restricted' is correctly
    filtered when PERMISSIONS_V2_ENABLED=True.

    Scenario:
    - firm with owner, worker_a (scope=own), worker_b (scope=team)
    - record owned by worker_a
    - public activity + restricted activity on that record by worker_a
    - worker_b has scope=team → should see both activities
    - worker_c has scope=own → should only see the restricted activity if
      they are the author; otherwise only public
    """

    def setUp(self):
        from firms.permissions import Scope
        self.firm = Firm.objects.create(name="Visibility Firm", subscription_tier="pro")
        self.owner = User.objects.create_user(email="vis_owner@example.com", password="pass")
        self.worker_a = User.objects.create_user(email="vis_worker_a@example.com", password="pass")
        self.worker_b = User.objects.create_user(email="vis_worker_b@example.com", password="pass")
        self.worker_c = User.objects.create_user(email="vis_worker_c@example.com", password="pass")

        self.owner_m = Membership.objects.create(user=self.owner, firm=self.firm, role=InvitationRole.OWNER)
        self.worker_a_m = Membership.objects.create(
            user=self.worker_a, firm=self.firm, role=InvitationRole.MEMBER, default_scope=Scope.OWN
        )
        self.worker_b_m = Membership.objects.create(
            user=self.worker_b, firm=self.firm, role=InvitationRole.MEMBER, default_scope=Scope.TEAM
        )
        self.worker_c_m = Membership.objects.create(
            user=self.worker_c, firm=self.firm, role=InvitationRole.MEMBER, default_scope=Scope.OWN
        )

        self.record = PipelineRecord.objects.create(
            firm=self.firm, title="Test Record",
            created_by=self.worker_a, assigned_to=self.worker_a,
        )
        self.public_activity = Activity.objects.create(
            record=self.record,
            user=self.worker_a,
            type=ActivityType.COMMENT,
            content_text="Public note",
            visibility="public",
        )
        self.restricted_activity = Activity.objects.create(
            record=self.record,
            user=self.worker_a,
            type=ActivityType.COMMENT,
            content_text="Team-only note",
            visibility="restricted",
        )

    def _make_request(self, user, membership):
        from django.test import RequestFactory
        req = RequestFactory().get("/")
        req.user = user
        req.firm = self.firm
        req.membership = membership
        return req

    def test_activity_visibility_field_default_public(self):
        """New activities default to visibility='public'."""
        a = Activity.objects.create(
            record=self.record,
            user=self.worker_a,
            type=ActivityType.COMMENT,
            content_text="Default",
        )
        self.assertEqual(a.visibility, "public")

    def test_owner_sees_all_activities(self):
        """Owner always sees all activities regardless of visibility."""
        from crm.permissions import filter_activities_qs
        req = self._make_request(self.owner, self.owner_m)
        qs = filter_activities_qs(
            Activity.objects.filter(record=self.record), req
        )
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.public_activity.id, ids)
        self.assertIn(self.restricted_activity.id, ids)

    def test_worker_own_scope_sees_only_public_and_own_restricted(self):
        """Worker with scope=own sees public activities; restricted only if they authored it."""
        from crm.permissions import filter_activities_qs
        req = self._make_request(self.worker_c, self.worker_c_m)
        # worker_c cannot see the record at all since scope=own, record belongs to worker_a
        # so no activities should be returned
        qs = filter_activities_qs(
            Activity.objects.filter(record=self.record), req
        )
        ids = list(qs.values_list("id", flat=True))
        self.assertNotIn(self.public_activity.id, ids)
        self.assertNotIn(self.restricted_activity.id, ids)

    def test_worker_own_scope_sees_own_restricted(self):
        """worker_a (scope=own, author) sees both activities on their own record."""
        from crm.permissions import filter_activities_qs
        req = self._make_request(self.worker_a, self.worker_a_m)
        qs = filter_activities_qs(
            Activity.objects.filter(record=self.record), req
        )
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.public_activity.id, ids)
        # worker_a authored the restricted activity → should see it
        self.assertIn(self.restricted_activity.id, ids)

    def test_worker_all_scope_sees_all(self):
        """Worker with scope=all sees all activities including restricted."""
        from crm.permissions import filter_activities_qs
        from firms.permissions import Scope
        # Give worker_b scope=all so they can see all records and all activities
        self.worker_b_m.default_scope = Scope.ALL
        self.worker_b_m.save()
        req = self._make_request(self.worker_b, self.worker_b_m)
        qs = filter_activities_qs(
            Activity.objects.filter(record=self.record), req
        )
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.public_activity.id, ids)
        self.assertIn(self.restricted_activity.id, ids)

    def test_no_membership_returns_empty(self):
        """Without membership, filter returns empty queryset."""
        from crm.permissions import filter_activities_qs
        from django.test import RequestFactory
        req = RequestFactory().get("/")
        req.user = self.worker_c
        req.firm = self.firm
        req.membership = None
        qs = filter_activities_qs(
            Activity.objects.filter(record=self.record), req
        )
        self.assertEqual(qs.count(), 0)


class ConditionRulesTest(CRMFixtureMixin, TestCase):
    def test_context_builder_includes_standard_record_fields(self):
        from crm.condition_rules import RecordConditionContextBuilder

        self.record.value = Decimal("123.45")
        self.record.notes = "Important note"
        self.record.extra_data = {"installation_date": "2026-05-01", "requires_photo": True}
        self.record.save(update_fields=["value", "notes", "extra_data"])
        Activity.objects.create(
            record=self.record,
            user=self.owner,
            type=ActivityType.FILE_UPLOAD,
            metadata={"tool_type": "file_upload"},
        )
        ctx = RecordConditionContextBuilder().build(self.record)

        self.assertEqual(ctx["id"], str(self.record.id))
        self.assertEqual(ctx["firm_id"], str(self.firm.id))
        self.assertEqual(ctx["title"], self.record.title)
        self.assertEqual(ctx["status"], self.record.status)
        self.assertEqual(ctx["source"], self.record.source)
        self.assertEqual(ctx["value"], Decimal("123.45"))
        self.assertEqual(ctx["notes"], "Important note")
        self.assertEqual(ctx["customer_id"], str(self.customer.id))
        self.assertEqual(ctx["category_fields"]["installation_date"], "2026-05-01")
        self.assertTrue(ctx["category_fields"]["requires_photo"])
        self.assertGreaterEqual(len(ctx["activities"]), 1)
        file_upload_activity = next(
            (a for a in ctx["activities"] if a["type"] == ActivityType.FILE_UPLOAD),
            None,
        )
        self.assertIsNotNone(file_upload_activity)
        self.assertEqual(file_upload_activity["entity_type"], "record")

    def test_condition_tree_supports_and_or_not_and_nested_groups(self):
        from crm.tasks import evaluate_condition_tree

        tree = {
            "type": "group",
            "operator": "and",
            "children": [
                {"field": "status", "operator": "eq", "value": "new"},
                {
                    "type": "group",
                    "operator": "or",
                    "children": [
                        {"field": "source", "operator": "eq", "value": "api"},
                        {
                            "field": "value",
                            "operator": "lt",
                            "value": "100",
                            "negated": True,
                        },
                    ],
                },
            ],
        }
        context = {"status": "new", "source": "web", "value": "120.50"}
        self.assertTrue(evaluate_condition_tree(tree, context))

    def test_missing_field_fails_closed(self):
        from crm.tasks import evaluate_condition_tree

        tree = {"field": "missing.path", "operator": "eq", "value": "x"}
        self.assertFalse(evaluate_condition_tree(tree, {"status": "new"}))

    def test_condition_tree_fails_closed_for_self_referencing_group(self):
        from crm.tasks import evaluate_condition_tree

        root = {"op": "and", "children": []}
        root["children"].append(root)
        self.assertFalse(evaluate_condition_tree(root, {"status": "new"}))

    def test_condition_tree_fails_closed_for_indirect_cycle_between_groups(self):
        from crm.tasks import evaluate_condition_tree

        first = {"op": "and", "children": []}
        second = {"op": "or", "children": []}
        first["children"].append(second)
        second["children"].append(first)
        self.assertFalse(evaluate_condition_tree(first, {"status": "new"}))

    def test_condition_tree_allows_reused_subtree_without_cycle(self):
        from crm.tasks import evaluate_condition_tree

        shared = {"field": "status", "operator": "eq", "value": "new"}
        tree = {"op": "and", "children": [shared, shared]}
        self.assertTrue(evaluate_condition_tree(tree, {"status": "new"}))

    def test_numeric_comparison_handles_decimal_like_values(self):
        from crm.tasks import evaluate_condition_tree

        context = {"value": "10.50"}
        self.assertTrue(
            evaluate_condition_tree(
                {"field": "value", "operator": "gt", "value": "10.4"},
                context,
            )
        )
        self.assertFalse(
            evaluate_condition_tree(
                {"field": "value", "operator": "lte", "value": "10.49"},
                context,
            )
        )

    def test_category_field_source_type_is_supported(self):
        from crm.tasks import evaluate_condition_tree

        context = {"category_fields": {"installation_date": "2026-05-01"}}
        tree = {
            "source_type": "category_field",
            "category_field_key": "installation_date",
            "operator": "eq",
            "value": "2026-05-01",
        }
        self.assertTrue(evaluate_condition_tree(tree, context))

    def test_activity_source_supports_tool_type_and_entity_type(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "activities": [
                {
                    "type": "file_upload",
                    "entity_type": "record",
                    "created_at": timezone.now().isoformat(),
                },
                {
                    "type": "comment",
                    "entity_type": "task",
                    "created_at": timezone.now().isoformat(),
                },
            ]
        }
        tree = {
            "source_type": "activity",
            "operator": "exists",
            "activity_type": "file_upload",
            "entity_type": "record",
        }
        self.assertTrue(evaluate_condition_tree(tree, context))

    def test_streamline_tool_source_supports_time_window(self):
        from crm.tasks import evaluate_condition_tree

        old_time = (timezone.now() - dt.timedelta(days=10)).isoformat()
        fresh_time = (timezone.now() - dt.timedelta(hours=2)).isoformat()
        context = {
            "activities": [
                {"type": "file_upload", "entity_type": "record", "created_at": old_time},
                {"type": "file_upload", "entity_type": "record", "created_at": fresh_time},
            ]
        }

        tree_recent = {
            "source_type": "streamline_tool",
            "operator": "exists",
            "value": "file_upload",
            "time_window": {"last_hours": 24},
        }
        tree_old = {
            "source_type": "streamline_tool",
            "operator": "exists",
            "value": "file_upload",
            "time_window": {"last_hours": 1},
        }
        tree_streamline_activity_days = {
            "source_type": "streamline_activity",
            "operator": "exists",
            "activity_type": "file_upload",
            "time_window": {"last_days": 1},
        }

        self.assertTrue(evaluate_condition_tree(tree_recent, context))
        self.assertFalse(evaluate_condition_tree(tree_old, context))
        self.assertTrue(evaluate_condition_tree(tree_streamline_activity_days, context))

    def test_streamline_tool_source_supports_explicit_tool_type(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "activities": [
                {
                    "type": "comment",
                    "tool_type": "whatsapp_out",
                    "entity_type": "record",
                    "created_at": timezone.now().isoformat(),
                }
            ]
        }
        tool_tree = {
            "source_type": "streamline_tool",
            "operator": "exists",
            "value": "whatsapp_out",
        }
        activity_type_tree = {
            "source_type": "streamline_tool",
            "operator": "exists",
            "value": "comment",
        }

        self.assertTrue(evaluate_condition_tree(tool_tree, context))
        self.assertFalse(evaluate_condition_tree(activity_type_tree, context))

    def test_field_change_source_supports_changed_operators(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "changed_field": "status",
            "changed_field_source": "field",
            "old_value": "new",
            "new_value": "qualified",
        }
        changed_tree = {
            "source_type": "field_change",
            "field": "status",
            "operator": "changed",
        }
        changed_from_tree = {
            "source_type": "field_change",
            "field": "status",
            "operator": "changed_from",
            "value": "new",
        }
        changed_to_tree = {
            "source_type": "field_change",
            "field": "status",
            "operator": "changed_to",
            "value": "qualified",
        }

        self.assertTrue(evaluate_condition_tree(changed_tree, context))
        self.assertTrue(evaluate_condition_tree(changed_from_tree, context))
        self.assertTrue(evaluate_condition_tree(changed_to_tree, context))

    def test_field_change_source_fails_for_non_matching_field(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "changed_field": "status",
            "changed_field_source": "field",
            "old_value": "new",
            "new_value": "qualified",
        }
        tree = {
            "source_type": "field_change",
            "field": "value",
            "operator": "changed",
        }
        self.assertFalse(evaluate_condition_tree(tree, context))

    def test_category_field_change_source_supports_changed_from(self):
        from crm.tasks import evaluate_condition_tree

        # The evaluator supports both flat change keys and nested `change` payloads.
        context = {
            "change": {
                "field_key": "installation_date",
                "source_type": "category_field",
                "old_value": "2026-01-01",
                "new_value": "2026-05-01",
            }
        }
        tree = {
            "source_type": "category_field_change",
            "category_field_key": "installation_date",
            "operator": "changed_from",
            "value": "2026-01-01",
        }
        self.assertTrue(evaluate_condition_tree(tree, context))

    def test_category_field_change_source_reads_category_field_key_from_change_context(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "change": {
                "category_field_key": "installation_date",
                "source_type": "category_field",
                "old_value": "2026-01-01",
                "new_value": "2026-05-01",
            }
        }
        tree = {
            "source_type": "category_field_change",
            "category_field_key": "installation_date",
            "operator": "changed_to",
            "value": "2026-05-01",
        }
        self.assertTrue(evaluate_condition_tree(tree, context))

    def test_category_field_change_fails_when_source_type_mismatches(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "field_changes": {
                "installation_date": {
                    "source_type": "field",
                    "old_value": "2026-01-01",
                    "new_value": "2026-05-01",
                }
            }
        }
        tree = {
            "source_type": "category_field_change",
            "category_field_key": "installation_date",
            "operator": "changed",
        }
        self.assertFalse(evaluate_condition_tree(tree, context))

    def test_field_change_changed_requires_actual_difference(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "changed_field": "status",
            "changed_field_source": "field",
            "old_value": "qualified",
            "new_value": "qualified",
        }
        tree = {
            "source_type": "field_change",
            "field": "status",
            "operator": "changed",
        }
        self.assertFalse(evaluate_condition_tree(tree, context))

    def test_field_change_treats_none_and_string_none_as_different(self):
        from crm.tasks import evaluate_condition_tree

        context = {
            "changed_field": "status",
            "changed_field_source": "field",
            "old_value": None,
            "new_value": "qualified",
        }
        tree = {
            "source_type": "field_change",
            "field": "status",
            "operator": "changed_from",
            "value": "None",
        }
        self.assertFalse(evaluate_condition_tree(tree, context))

    def test_related_entity_source_supports_exists_and_missing(self):
        from crm.tasks import evaluate_condition_tree

        exists_tree = {
            "source_type": "related_entity",
            "entity_type": "customer",
            "operator": "exists",
        }
        missing_tree = {
            "source_type": "related_entity",
            "entity_type": "customer",
            "operator": "missing",
        }
        self.assertTrue(evaluate_condition_tree(exists_tree, {"customer_id": str(self.customer.id)}))
        self.assertFalse(evaluate_condition_tree(exists_tree, {"customer_id": None}))
        self.assertFalse(evaluate_condition_tree(missing_tree, {"customer_id": str(self.customer.id)}))
        self.assertTrue(evaluate_condition_tree(missing_tree, {"customer_id": None}))

    def test_related_entity_source_supports_known_entity_types(self):
        from crm.tasks import evaluate_condition_tree

        supported = {
            "customer": "customer_id",
            "company": "company_id",
            "contact_person": "contact_person_id",
            "assigned_to": "assigned_to_id",
            "category": "category_id",
            "current_stage": "current_stage_id",
            "stage": "current_stage_id",
            "parent": "parent_id",
        }
        for entity_type, field_key in supported.items():
            tree = {
                "source_type": "related_entity",
                "entity_type": entity_type,
                "operator": "exists",
            }
            self.assertTrue(
                evaluate_condition_tree(tree, {field_key: "entity-id"}),
                msg=f"source_type related_entity should support {entity_type}",
            )

    def test_related_entity_source_fails_closed_for_invalid_entity_type(self):
        from crm.tasks import evaluate_condition_tree

        tree = {
            "source_type": "related_entity",
            "entity_type": "unknown_entity",
            "operator": "exists",
        }
        self.assertFalse(evaluate_condition_tree(tree, {"customer_id": str(self.customer.id)}))

    def test_evaluate_condition_rule_outputs_returns_effect_payloads_sorted_by_priority(self):
        from crm.condition_rules import evaluate_condition_rule_outputs

        rules = [
            {
                "id": "rule-high",
                "name": "High priority",
                "is_active": True,
                "priority": 10,
                "created_at": "2026-05-10T10:00:00+00:00",
                "condition_tree": {"field": "status", "operator": "eq", "value": "new"},
                "effect": "warning",
                "severity": "warning",
                "effect_config": {"message": "high"},
            },
            {
                "id": "rule-low",
                "name": "Low priority",
                "is_active": True,
                "priority": 50,
                "created_at": "2026-05-10T09:00:00+00:00",
                "condition_tree": {"field": "status", "operator": "eq", "value": "new"},
                "effect": "block",
                "severity": "error",
                "effect_config": {"message": "low"},
            },
            {
                "id": "rule-inactive",
                "name": "Inactive",
                "is_active": False,
                "priority": 1,
                "created_at": "2026-05-10T08:00:00+00:00",
                "condition_tree": {"field": "status", "operator": "eq", "value": "new"},
                "effect": "recommendation",
                "severity": "info",
                "effect_config": {"message": "inactive"},
            },
        ]

        outputs = evaluate_condition_rule_outputs(rules, {"status": "new"})
        self.assertEqual([item["rule_id"] for item in outputs], ["rule-high", "rule-low"])
        self.assertEqual(outputs[0]["effect"], "warning")
        self.assertEqual(outputs[0]["severity"], "warning")
        self.assertEqual(outputs[0]["effect_config"], {"message": "high"})

    def test_evaluate_condition_rule_outputs_is_deterministic_with_same_priority(self):
        from crm.condition_rules import evaluate_condition_rule_outputs

        rules = [
            {
                "id": "rule-b",
                "name": "Rule B",
                "is_active": True,
                "priority": 10,
                "created_at": "2026-05-10T10:00:00+00:00",
                "condition_tree": {"field": "status", "operator": "eq", "value": "new"},
                "effect": "warning",
                "severity": "warning",
                "effect_config": {},
            },
            {
                "id": "rule-a",
                "name": "Rule A",
                "is_active": True,
                "priority": 10,
                "created_at": "2026-05-10T09:00:00+00:00",
                "condition_tree": {"field": "status", "operator": "eq", "value": "new"},
                "effect": "block",
                "severity": "error",
                "effect_config": {},
            },
        ]

        outputs = evaluate_condition_rule_outputs(rules, {"status": "new"})
        self.assertEqual([item["rule_id"] for item in outputs], ["rule-a", "rule-b"])


class ConditionRulesApiEndpointsTest(CRMAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(firm=self.firm, name="Installations", slug="installations")
        self.stage_a = Stage.objects.create(category=self.category, name="A", order=1)
        self.stage_b = Stage.objects.create(category=self.category, name="B", order=2)
        self.record.category = self.category
        self.record.current_stage = self.stage_a
        self.record.save(update_fields=["category", "current_stage"])

    def test_condition_rule_crud_and_soft_deactivate(self):
        create_payload = {
            "name": "Block stage transition",
            "description": "Must have value",
            "scope_type": ConditionScopeType.STAGE_TRANSITION,
            "category_id": str(self.category.id),
            "source_stage_id": str(self.stage_a.id),
            "target_stage_id": str(self.stage_b.id),
            "trigger_type": ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
            "condition_tree": {"field": "value", "operator": "gt", "value": 0},
            "effect": ConditionEffectType.BLOCK,
            "severity": ConditionSeverity.ERROR,
            "effect_config": {"message": "Missing value"},
            "priority": 10,
        }
        resp = self._post("/api/v1/crm/condition-rules", create_payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        rule_id = resp.json()["id"]

        list_resp = self._get("/api/v1/crm/condition-rules")
        self.assertEqual(list_resp.status_code, 200)
        self.assertTrue(any(item["id"] == rule_id for item in list_resp.json()))

        detail_resp = self._get(f"/api/v1/crm/condition-rules/{rule_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["name"], "Block stage transition")

        patch_resp = self._patch(
            f"/api/v1/crm/condition-rules/{rule_id}",
            {"name": "Updated name", "priority": 5},
        )
        self.assertEqual(patch_resp.status_code, 200, patch_resp.content)
        self.assertEqual(patch_resp.json()["name"], "Updated name")
        self.assertEqual(patch_resp.json()["priority"], 5)

        delete_resp = self._delete(f"/api/v1/crm/condition-rules/{rule_id}")
        self.assertEqual(delete_resp.status_code, 204)
        self.assertFalse(ConditionRule.objects.get(id=rule_id).is_active)
        actions = list(
            PermissionAuditLog.objects.filter(
                firm=self.firm,
                target_type="condition_rule",
                target_id=rule_id,
            ).values_list("action", flat=True)
        )
        self.assertIn("condition_rule.created", actions)
        self.assertIn("condition_rule.updated", actions)
        self.assertIn("condition_rule.deactivated", actions)

    def test_condition_rule_management_requires_category_manage_permission(self):
        self.client.logout()
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._post(
            "/api/v1/crm/condition-rules",
            {
                "name": "Worker cannot create",
                "trigger_type": ConditionTriggerType.RECORD_UPDATED,
                "condition_tree": {"field": "status", "operator": "eq", "value": RecordStatus.NEW},
            },
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._get("/api/v1/crm/condition-rules").status_code, 403)
        self.assertEqual(
            self._get(
                f"/api/v1/crm/categories/{self.category.id}/stages/{self.stage_a.id}/scenarios"
            ).status_code,
            403,
        )
        self.assertEqual(self._get("/api/v1/crm/rule-evaluation-logs").status_code, 403)

    def test_stage_scenario_endpoints_and_active_requirements_endpoint(self):
        scenario_resp = self._post(
            f"/api/v1/crm/categories/{self.category.id}/stages/{self.stage_a.id}/scenarios",
            {
                "name": "Scenario A",
                "activation_condition": {"field": "status", "operator": "eq", "value": RecordStatus.NEW},
                "completion_condition": {},
                "recommended_next_stage_id": str(self.stage_b.id),
                "priority": 1,
            },
        )
        self.assertEqual(scenario_resp.status_code, 201, scenario_resp.content)
        scenario_id = scenario_resp.json()["id"]
        patch_scenario_resp = self._patch(
            f"/api/v1/crm/categories/{self.category.id}/stages/{self.stage_a.id}/scenarios/{scenario_id}",
            {"priority": 3, "is_active": True},
        )
        self.assertEqual(patch_scenario_resp.status_code, 200, patch_scenario_resp.content)
        self.assertEqual(patch_scenario_resp.json()["priority"], 3)

        requirement_create_resp = self._post(
            f"/api/v1/crm/scenarios/{scenario_id}/requirements",
            {
                "name": "Need upload",
                "requirement_type": "activity",
                "condition": {
                    "source_type": "activity",
                    "activity_type": "task",
                    "operator": "exists",
                },
                "blocking": True,
                "sort_order": 0,
            },
        )
        self.assertEqual(requirement_create_resp.status_code, 201, requirement_create_resp.content)
        requirement_id = requirement_create_resp.json()["id"]

        requirement_patch_resp = self._patch(
            f"/api/v1/crm/scenarios/{scenario_id}/requirements/{requirement_id}",
            {"blocking": False},
        )
        self.assertEqual(requirement_patch_resp.status_code, 200, requirement_patch_resp.content)
        self.assertFalse(requirement_patch_resp.json()["blocking"])

        list_resp = self._get(
            f"/api/v1/crm/categories/{self.category.id}/stages/{self.stage_a.id}/scenarios"
        )
        self.assertEqual(list_resp.status_code, 200)
        self.assertTrue(any(item["id"] == scenario_id for item in list_resp.json()))

        req_resp = self._get(f"/api/v1/crm/scenarios/{scenario_id}/requirements")
        self.assertEqual(req_resp.status_code, 200)
        self.assertEqual(req_resp.json()[0]["id"], requirement_id)

        active_req_resp = self._get(
            f"/api/v1/crm/records/{self.record.id}/active-stage-requirements"
        )
        self.assertEqual(active_req_resp.status_code, 200, active_req_resp.content)
        payload = active_req_resp.json()
        self.assertEqual(payload["active_stage_scenario_id"], scenario_id)
        self.assertEqual(payload["active_stage_scenario_name"], "Scenario A")
        self.assertEqual(payload["recommended_next_stage_id"], str(self.stage_b.id))
        self.assertEqual(payload["recommended_next_stage_name"], self.stage_b.name)
        self.assertEqual(payload["active_stage_requirements"][0]["id"], requirement_id)
        self.assertIsNone(payload["active_stage_requirements"][0]["relevant_field_key"])
        self.assertEqual(payload["active_stage_requirements"][0]["relevant_activity_type"], "task")
        self.assertIsNone(payload["active_stage_requirements"][0]["relevant_tool_type"])
        self.assertFalse(payload["active_stage_requirements"][0]["blocking"])

        requirement_delete_resp = self._delete(
            f"/api/v1/crm/scenarios/{scenario_id}/requirements/{requirement_id}"
        )
        self.assertEqual(requirement_delete_resp.status_code, 204, requirement_delete_resp.content)

        scenario_delete_resp = self._delete(
            f"/api/v1/crm/categories/{self.category.id}/stages/{self.stage_a.id}/scenarios/{scenario_id}"
        )
        self.assertEqual(scenario_delete_resp.status_code, 204, scenario_delete_resp.content)

    def test_condition_rule_test_evaluation_and_log_listing(self):
        rule = ConditionRule.objects.create(
            firm=self.firm,
            name="Warn when new",
            scope_type=ConditionScopeType.FIRM,
            trigger_type=ConditionTriggerType.MANUAL_EVALUATION_REQUESTED,
            condition_tree={"field": "status", "operator": "eq", "value": RecordStatus.NEW},
            effect=ConditionEffectType.WARNING,
            severity=ConditionSeverity.WARNING,
            effect_config={"message": "still new"},
            created_by=self.owner,
        )
        eval_resp = self._post(
            "/api/v1/crm/condition-rules/test-evaluation/run",
            {"record_id": str(self.record.id), "rule_id": str(rule.id)},
        )
        self.assertEqual(eval_resp.status_code, 200, eval_resp.content)
        self.assertTrue(eval_resp.json()["matched"])
        self.assertEqual(eval_resp.json()["warnings"][0]["rule_id"], str(rule.id))

        RuleEvaluationLog.objects.create(
            firm=self.firm,
            record=self.record,
            rule=rule,
            trigger_type=ConditionTriggerType.MANUAL_EVALUATION_REQUESTED,
            input_context={"record_id": str(self.record.id)},
            result=RuleEvaluationResult.WARNING,
            messages=["still new"],
            recommendations=[],
            evaluated_by=self.owner,
        )
        logs_resp = self._get(
            "/api/v1/crm/rule-evaluation-logs",
            {"rule_id": str(rule.id), "result": RuleEvaluationResult.WARNING},
        )
        self.assertEqual(logs_resp.status_code, 200, logs_resp.content)
        self.assertTrue(any(item["rule_id"] == str(rule.id) for item in logs_resp.json()))
