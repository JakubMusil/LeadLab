from django.test import TestCase
from django.utils import timezone
import datetime as dt

from crm.models import Activity, ActivityType, Customer, Lead, LeadSource, LeadStatus, Task
from firms.models import Firm, Membership, MembershipRole
from users.models import User


class CRMFixtureMixin:
    """Mixin that sets up a firm with an owner and a worker."""

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@crm.com", password="pass")
        self.worker = User.objects.create_user(email="worker@crm.com", password="pass")
        self.firm = Firm.objects.create(name="CRM Firm", subscription_tier="pro")
        Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)

        self.customer = Customer.objects.create(
            firm=self.firm,
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )
        self.lead = Lead.objects.create(
            firm=self.firm,
            customer=self.customer,
            title="Demo Deal",
            status=LeadStatus.NEW,
            source=LeadSource.WEB,
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


class LeadModelTest(CRMFixtureMixin, TestCase):
    def test_lead_str(self):
        self.assertIn("Demo Deal", str(self.lead))

    def test_lead_default_status(self):
        lead = Lead.objects.create(firm=self.firm, title="Quick Lead")
        self.assertEqual(lead.status, LeadStatus.NEW)

    def test_lead_nullable_customer(self):
        lead = Lead.objects.create(firm=self.firm, title="Quick Entry")
        self.assertIsNone(lead.customer)

    def test_lead_choices(self):
        valid_statuses = [s.value for s in LeadStatus]
        self.assertIn(self.lead.status, valid_statuses)

    def test_lead_firm_isolation(self):
        other_firm = Firm.objects.create(name="Isolate Firm")
        Lead.objects.create(firm=other_firm, title="Other Lead")
        self.assertEqual(Lead.objects.filter(firm=self.firm).count(), 1)


class ActivityModelTest(CRMFixtureMixin, TestCase):
    def test_create_comment_activity(self):
        activity = Activity.objects.create(
            lead=self.lead,
            user=self.owner,
            type=ActivityType.COMMENT,
            content_text="First contact made.",
        )
        self.assertEqual(activity.type, ActivityType.COMMENT)
        self.assertEqual(activity.lead, self.lead)

    def test_create_status_change_activity(self):
        activity = Activity.objects.create(
            lead=self.lead,
            user=self.owner,
            type=ActivityType.STATUS_CHANGE,
            metadata={"old_status": "new", "new_status": "contacted"},
        )
        self.assertEqual(activity.metadata["old_status"], "new")
        self.assertEqual(activity.metadata["new_status"], "contacted")

    def test_create_email_out_activity(self):
        activity = Activity.objects.create(
            lead=self.lead,
            user=self.worker,
            type=ActivityType.EMAIL_OUT,
            content_text="Hi Jane, following up...",
            metadata={"subject": "Follow-up", "to": "jane@example.com"},
        )
        self.assertEqual(activity.metadata["subject"], "Follow-up")

    def test_activities_ordered_newest_first(self):
        a1 = Activity.objects.create(lead=self.lead, type=ActivityType.COMMENT, content_text="A1")
        a2 = Activity.objects.create(lead=self.lead, type=ActivityType.CALL, content_text="A2")
        activities = list(Activity.objects.filter(lead=self.lead))
        self.assertEqual(activities[0].pk, a2.pk)  # newest first

    def test_activity_str(self):
        activity = Activity.objects.create(
            lead=self.lead, type=ActivityType.COMMENT, content_text="test"
        )
        self.assertIn("Comment", str(activity))

    def test_activity_lead_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm 2")
        other_lead = Lead.objects.create(firm=other_firm, title="Other Lead")
        Activity.objects.create(lead=other_lead, type=ActivityType.COMMENT, content_text="x")
        self.assertEqual(Activity.objects.filter(lead=self.lead).count(), 0)


class TaskModelTest(CRMFixtureMixin, TestCase):
    def test_create_task(self):
        task = Task.objects.create(
            firm=self.firm,
            lead=self.lead,
            assigned_to=self.worker,
            title="Send proposal",
        )
        self.assertFalse(task.is_completed)
        self.assertIsNone(task.completed_at)

    def test_complete_task(self):
        task = Task.objects.create(firm=self.firm, lead=self.lead, title="Call back")
        task.is_completed = True
        task.completed_at = timezone.now()
        task.save()
        task.refresh_from_db()
        self.assertTrue(task.is_completed)
        self.assertIsNotNone(task.completed_at)

    def test_task_str(self):
        task = Task.objects.create(firm=self.firm, lead=self.lead, title="Follow up")
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
            lead=self.lead,
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
            "sub_task_added", "task_created", "task_archived",
            "approval_requested", "approval_resolved", "time_logged",
            "checklist_item_checked", "voice_memo",
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
            Activity.objects.filter(lead=self.lead, is_internal=True).count(), 1,
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

    def test_sub_task_added_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.SUB_TASK_ADDED,
            metadata={"subtask_id": "abc", "subtask_title": "Write tests"},
        )
        out = get_tool("sub_task_added").render_payload(a)
        self.assertEqual(out["subtask_title"], "Write tests")

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

    def test_checklist_item_checked_render(self):
        from crm.streamline.registry import get_tool
        a = self._build_activity(
            ActivityType.CHECKLIST_ITEM_CHECKED,
            metadata={"item_text": "Buy milk", "is_checked": True},
        )
        out = get_tool("checklist_item_checked").render_payload(a)
        self.assertTrue(out["is_checked"])

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
            self.lead,
            {"metadata": {
                "old_assignee_id": str(self.owner.id),
                "new_assignee_id": str(self.worker.id),
            }},
            {"firm": self.firm, "user": self.owner, "entity_title": self.lead.title},
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
            self.lead,
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
            lead=self.lead,
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
            lead=self.lead,
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
            lead=self.lead,
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
            self.lead,
            {"metadata": {"mentioned_user_id": str(self.worker.id)}},
            {"firm": self.firm, "user": self.owner, "entity_title": self.lead.title},
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
            self.lead,
            {"metadata": {"mentioned_user_id": str(self.owner.id)}},
            {"firm": self.firm, "user": self.owner, "entity_title": ""},
        )
        self.assertEqual(
            Notification.objects.filter(event="activity.mention").count(), 0
        )


class ActivityTaskLinkTest(CRMFixtureMixin, TestCase):
    """Phase 0 — Activity can now be linked to a Task entity."""

    def test_activity_can_be_linked_to_task(self):
        task = Task.objects.create(firm=self.firm, lead=self.lead, title="T")
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
            lead=self.lead, user=self.owner, type=ActivityType.COMMENT, content_text="x"
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
    """Sets up two users, a firm with owner + worker, a customer and a lead."""

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@crm-api.com", password="pass")
        self.worker = User.objects.create_user(email="worker@crm-api.com", password="pass")
        self.firm = Firm.objects.create(name="CRM API Firm", subscription_tier="pro")
        self.owner_membership = Membership.objects.create(
            user=self.owner, firm=self.firm, role=MembershipRole.OWNER
        )
        self.worker_membership = Membership.objects.create(
            user=self.worker, firm=self.firm, role=MembershipRole.WORKER
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
        self.lead = Lead.objects.create(
            firm=self.firm,
            customer=self.customer,
            title="Test Lead",
            status=LeadStatus.NEW,
            source=LeadSource.WEB,
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


# -- Leads -------------------------------------------------------------------

class LeadListAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/opportunities"

    def test_list_leads_returns_firm_leads(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_filter_by_status(self):
        Lead.objects.create(firm=self.firm, title="Won Lead", status=LeadStatus.WON)
        resp = self._get(self.URL, {"status": "won"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "won")

    def test_filter_by_source(self):
        Lead.objects.create(firm=self.firm, title="Referral Lead", source=LeadSource.REFERRAL)
        resp = self._get(self.URL, {"source": "referral"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source"], "referral")

    def test_filter_by_tag(self):
        # self.lead has customer with tag "vip"
        Lead.objects.create(firm=self.firm, title="Untagged Lead")
        resp = self._get(self.URL, {"tag": "vip"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(self.lead.id))

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
            Lead.objects.create(firm=self.firm, title=f"Lead {i}")
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm")
        Lead.objects.create(firm=other_firm, title="Foreign Lead")
        resp = self._get(self.URL)
        self.assertEqual(len(resp.json()), 1)


class LeadCreateAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/opportunities"

    def test_create_lead_returns_201(self):
        resp = self._post(self.URL, {"title": "New Lead"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["title"], "New Lead")

    def test_create_lead_with_customer(self):
        resp = self._post(self.URL, {
            "title": "Lead With Customer",
            "customer_id": str(self.customer.id),
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["customer_id"], str(self.customer.id))

    def test_create_lead_invalid_customer_returns_400(self):
        import uuid
        resp = self._post(self.URL, {"title": "Bad", "customer_id": str(uuid.uuid4())})
        self.assertEqual(resp.status_code, 400)

    def test_create_lead_worker_allowed(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._post(self.URL, {"title": "Worker Lead"})
        self.assertEqual(resp.status_code, 201)


class LeadGetAPITest(CRMAPIFixtureMixin, TestCase):
    def test_get_lead(self):
        resp = self._get(f"/api/v1/crm/opportunities/{self.lead.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Test Lead")

    def test_get_nonexistent_lead_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/opportunities/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)


class LeadUpdateAPITest(CRMAPIFixtureMixin, TestCase):
    def test_patch_lead_title(self):
        resp = self._patch(f"/api/v1/crm/opportunities/{self.lead.id}", {"title": "Updated"})
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.title, "Updated")

    def test_patch_status_creates_activity(self):
        resp = self._patch(f"/api/v1/crm/opportunities/{self.lead.id}", {"status": "contacted"})
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, LeadStatus.CONTACTED)
        self.assertTrue(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.STATUS_CHANGE
            ).exists()
        )

    def test_patch_nonexistent_lead_returns_404(self):
        import uuid
        resp = self._patch(f"/api/v1/crm/opportunities/{uuid.uuid4()}", {"title": "X"})
        self.assertEqual(resp.status_code, 404)


class LeadDeleteAPITest(CRMAPIFixtureMixin, TestCase):
    def test_delete_lead_admin_succeeds(self):
        resp = self._delete(f"/api/v1/crm/opportunities/{self.lead.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Lead.objects.filter(id=self.lead.id).exists())

    def test_delete_lead_worker_returns_403(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(f"/api/v1/crm/opportunities/{self.lead.id}")
        self.assertEqual(resp.status_code, 403)


# -- Activities --------------------------------------------------------------

class ActivityListAPITest(CRMAPIFixtureMixin, TestCase):
    def test_list_activities_empty(self):
        resp = self._get(f"/api/v1/crm/opportunities/{self.lead.id}/activities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_activities_after_comment(self):
        Activity.objects.create(
            lead=self.lead, user=self.owner, type=ActivityType.COMMENT, content_text="Hello"
        )
        resp = self._get(f"/api/v1/crm/opportunities/{self.lead.id}/activities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_list_activities_pagination(self):
        for i in range(5):
            Activity.objects.create(
                lead=self.lead, type=ActivityType.COMMENT, content_text=f"msg {i}"
            )
        resp = self._get(
            f"/api/v1/crm/opportunities/{self.lead.id}/activities",
            {"page": 1, "page_size": 3},
        )
        self.assertEqual(len(resp.json()), 3)

    def test_list_activities_nonexistent_lead_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/opportunities/{uuid.uuid4()}/activities")
        self.assertEqual(resp.status_code, 404)


class ActivityCreateAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/activities"

    def test_create_comment_activity(self):
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
            "type": "comment",
            "content_text": "First contact",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["type"], "comment")

    def test_create_activity_invalid_lead_returns_400(self):
        import uuid
        resp = self._post(self.URL, {
            "lead_id": str(uuid.uuid4()),
            "type": "comment",
            "content_text": "Orphan",
        })
        self.assertEqual(resp.status_code, 400)

    def test_create_activity_invalid_type_returns_400(self):
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
            "type": "invalid_type",
        })
        self.assertEqual(resp.status_code, 400)

    def test_status_change_activity_updates_lead(self):
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
            "type": "status_change",
            "metadata": {"new_status": "contacted"},
        })
        self.assertEqual(resp.status_code, 201)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "contacted")

    # ------------------------------------------------------------------
    # F-3 — payload validation against tool JSON Schema
    # ------------------------------------------------------------------

    def test_payload_missing_required_field_returns_400(self):
        """status_change requires metadata.new_status — empty metadata fails."""
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
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
            "lead_id": str(self.lead.id),
            "type": "status_change",
            "metadata": {"new_status": "not_a_real_status"},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("new_status", resp.json()["detail"])

    def test_payload_negative_minimum_returns_400(self):
        """call.duration_minutes has minimum: 0 — negative value fails."""
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
            "type": "call",
            "content_text": "Quick chat",
            "metadata": {"duration_minutes": -5},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("duration_minutes", resp.json()["detail"])

    def test_payload_unknown_metadata_keys_allowed(self):
        """Unknown metadata properties should pass (additionalProperties: true)."""
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
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
        Task.objects.create(firm=self.firm, lead=self.lead, title="Do something")
        resp = self._get(self.URL)
        self.assertEqual(len(resp.json()), 1)

    def test_filter_by_completed(self):
        Task.objects.create(firm=self.firm, lead=self.lead, title="Done", is_completed=True)
        Task.objects.create(firm=self.firm, lead=self.lead, title="Pending")
        resp = self._get(self.URL, {"completed": "true"})
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["is_completed"])

    def test_pagination(self):
        for i in range(5):
            Task.objects.create(firm=self.firm, lead=self.lead, title=f"Task {i}")
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)


class TaskCreateAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/tasks"

    def test_create_task_returns_201(self):
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
            "title": "Send proposal",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.json()["is_completed"])

    def test_create_task_logs_task_assigned_activity(self):
        self._post(self.URL, {"lead_id": str(self.lead.id), "title": "Task A"})
        self.assertTrue(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.TASK_ASSIGNED
            ).exists()
        )

    def test_create_task_invalid_lead_returns_400(self):
        import uuid
        resp = self._post(self.URL, {"lead_id": str(uuid.uuid4()), "title": "Orphan"})
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # Task.realization + Task.management FKs (18th iteration)
    # ------------------------------------------------------------------

    def test_create_task_with_realization_link(self):
        from crm.models import Realization
        realization = Realization.objects.create(
            firm=self.firm, title="Realization A", customer=self.customer,
        )
        resp = self._post(self.URL, {
            "realization_id": str(realization.id),
            "title": "Task on realization",
        })
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["realization_id"], str(realization.id))
        self.assertEqual(body["realization_title"], "Realization A")
        self.assertIsNone(body["lead_id"])
        # DB round-trip: task is reachable via realization.tasks
        self.assertEqual(realization.tasks.count(), 1)

    def test_create_task_with_management_link(self):
        from crm.models import Management
        management = Management.objects.create(
            firm=self.firm, title="Mgmt A", customer=self.customer,
        )
        resp = self._post(self.URL, {
            "management_id": str(management.id),
            "title": "Task on management",
        })
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["management_id"], str(management.id))
        self.assertEqual(body["management_title"], "Mgmt A")
        self.assertEqual(management.tasks.count(), 1)

    def test_create_task_invalid_realization_returns_400(self):
        import uuid
        resp = self._post(self.URL, {
            "realization_id": str(uuid.uuid4()),
            "title": "Orphan",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Realization", resp.json()["detail"])

    def test_create_task_invalid_management_returns_400(self):
        import uuid
        resp = self._post(self.URL, {
            "management_id": str(uuid.uuid4()),
            "title": "Orphan",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Management", resp.json()["detail"])

    def test_create_task_realization_from_other_firm_returns_400(self):
        """Tenant isolation: cannot link a Task to a Realization in another Firm."""
        from crm.models import Realization
        other_firm = Firm.objects.create(name="Other", subscription_tier="pro")
        other_realization = Realization.objects.create(
            firm=other_firm, title="Other R",
        )
        resp = self._post(self.URL, {
            "realization_id": str(other_realization.id),
            "title": "X",
        })
        self.assertEqual(resp.status_code, 400)

    def test_task_out_realization_management_default_none(self):
        """A task without realization/management still serializes the new keys as None."""
        Task.objects.create(firm=self.firm, lead=self.lead, title="Plain")
        data = self._get(self.URL).json()
        self.assertEqual(len(data), 1)
        self.assertIsNone(data[0]["realization_id"])
        self.assertIsNone(data[0]["realization_title"])
        self.assertIsNone(data[0]["management_id"])
        self.assertIsNone(data[0]["management_title"])


class TaskCompleteAPITest(CRMAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.task = Task.objects.create(
            firm=self.firm, lead=self.lead, title="Call client"
        )

    def test_complete_task_returns_200(self):
        resp = self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_completed"])

    def test_complete_task_logs_activity(self):
        self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        self.assertTrue(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.TASK_COMPLETED
            ).exists()
        )

    def test_complete_already_completed_task_is_idempotent(self):
        self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        resp = self._post(f"/api/v1/crm/tasks/{self.task.id}/complete", {})
        self.assertEqual(resp.status_code, 200)
        # Only one TASK_COMPLETED activity should exist
        count = Activity.objects.filter(
            lead=self.lead, type=ActivityType.TASK_COMPLETED
        ).count()
        self.assertEqual(count, 1)

    def test_complete_nonexistent_task_returns_404(self):
        import uuid
        resp = self._post(f"/api/v1/crm/tasks/{uuid.uuid4()}/complete", {})
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Tier limit enforcement for lead creation
# ---------------------------------------------------------------------------


class TierLimitLeadCreateAPITest(TestCase):
    """create_lead enforces the Free-tier 50-lead limit."""

    URL = "/api/v1/crm/opportunities"

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@lead_tier.com", password="pass")
        # Free-tier firm with only 1 member to avoid hitting the member limit.
        self.firm = Firm.objects.create(name="Free Lead Firm", subscription_tier="free")
        Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.client.login(username="owner@lead_tier.com", password="pass")

    def _firm_headers(self):
        return {"HTTP_X_FIRM_ID": str(self.firm.id)}

    def test_create_lead_blocked_when_50_leads_exist(self):
        # Pre-fill 50 leads directly in the DB.
        Lead.objects.bulk_create([
            Lead(firm=self.firm, title=f"Lead {i}") for i in range(50)
        ])
        resp = self.client.post(
            self.URL,
            data=json.dumps({"title": "Over limit"}),
            content_type="application/json",
            **self._firm_headers(),
        )
        self.assertEqual(resp.status_code, 402)
        self.assertIn("50 leads", resp.json()["detail"])

    def test_create_lead_allowed_at_49_leads(self):
        Lead.objects.bulk_create([
            Lead(firm=self.firm, title=f"Lead {i}") for i in range(49)
        ])
        resp = self.client.post(
            self.URL,
            data=json.dumps({"title": "Just within limit"}),
            content_type="application/json",
            **self._firm_headers(),
        )
        self.assertEqual(resp.status_code, 201)


# ---------------------------------------------------------------------------
# Lead Attachments API tests (now backed by Document)
# ---------------------------------------------------------------------------

import io
import uuid as uuid_module

from django.core.files.uploadedfile import SimpleUploadedFile

from crm.models import Document


class AttachmentAPIFixtureMixin(CRMAPIFixtureMixin):
    """Extends CRMAPIFixtureMixin with a pre-built SimpleUploadedFile helper."""

    def _make_file(self, name="test.txt", content=b"hello world", content_type="text/plain"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def _upload(self, lead_id, name="test.txt", content=b"hello world"):
        f = self._make_file(name=name, content=content)
        return self.client.post(
            f"/api/v1/crm/opportunities/{lead_id}/attachments",
            data={"file": f},
            **self.firm_headers(),
        )


class AttachmentListAPITest(AttachmentAPIFixtureMixin, TestCase):
    def test_list_attachments_empty(self):
        resp = self._get(f"/api/v1/crm/opportunities/{self.lead.id}/attachments")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_attachments_nonexistent_lead_returns_404(self):
        resp = self._get(f"/api/v1/crm/opportunities/{uuid_module.uuid4()}/attachments")
        self.assertEqual(resp.status_code, 404)

    def test_list_attachments_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Other Firm Attach")
        other_lead = Lead.objects.create(firm=other_firm, title="Other Lead")
        # Upload directly to DB for other firm's lead — should not appear in our list.
        Document.objects.create(
            firm=other_firm,
            lead=other_lead,
            name="secret.pdf",
            content_type="application/pdf",
            size_bytes=100,
        )
        resp = self._get(f"/api/v1/crm/opportunities/{self.lead.id}/attachments")
        self.assertEqual(resp.json(), [])

    def test_list_attachments_pagination(self):
        for i in range(5):
            Document.objects.create(
                firm=self.firm,
                lead=self.lead,
                name=f"file{i}.txt",
                content_type="text/plain",
                size_bytes=i,
            )
        resp = self._get(
            f"/api/v1/crm/opportunities/{self.lead.id}/attachments",
            {"page": 1, "page_size": 3},
        )
        self.assertEqual(len(resp.json()), 3)


class AttachmentUploadAPITest(AttachmentAPIFixtureMixin, TestCase):
    def tearDown(self):
        # Clean up any files written to MEDIA_ROOT during tests.
        for doc in Document.objects.filter(lead=self.lead):
            doc.file.delete(save=False)
        super().tearDown()

    def test_upload_returns_201(self):
        resp = self._upload(self.lead.id)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["original_filename"], "test.txt")
        self.assertEqual(data["lead_id"], str(self.lead.id))
        self.assertIn("url", data)

    def test_upload_creates_db_record(self):
        self._upload(self.lead.id)
        self.assertEqual(Document.objects.filter(lead=self.lead).count(), 1)

    def test_upload_logs_file_upload_activity(self):
        self._upload(self.lead.id)
        self.assertTrue(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.FILE_UPLOAD
            ).exists()
        )

    def test_upload_activity_metadata_contains_filename(self):
        self._upload(self.lead.id, name="report.pdf", content=b"PDF")
        activity = Activity.objects.get(lead=self.lead, type=ActivityType.FILE_UPLOAD)
        self.assertEqual(activity.metadata["filename"], "report.pdf")

    def test_upload_worker_allowed(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._upload(self.lead.id)
        self.assertEqual(resp.status_code, 201)

    def test_upload_nonexistent_lead_returns_404(self):
        resp = self._upload(uuid_module.uuid4())
        self.assertEqual(resp.status_code, 404)

    def test_upload_requires_authentication(self):
        self.client.logout()
        resp = self._upload(self.lead.id)
        self.assertIn(resp.status_code, [401, 403])

    def test_upload_file_too_large_returns_400(self):
        large_content = b"x" * (20 * 1024 * 1024 + 1)
        resp = self._upload(self.lead.id, content=large_content)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("20 MB", resp.json()["detail"])


class AttachmentDeleteAPITest(AttachmentAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Create a Document record without a physical file for delete tests.
        self.attachment = Document.objects.create(
            firm=self.firm,
            lead=self.lead,
            name="deleteme.txt",
            content_type="text/plain",
            size_bytes=5,
        )

    def test_delete_attachment_admin_succeeds(self):
        resp = self._delete(
            f"/api/v1/crm/opportunities/{self.lead.id}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Document.objects.filter(id=self.attachment.id).exists())

    def test_delete_attachment_worker_returns_403(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(
            f"/api/v1/crm/opportunities/{self.lead.id}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_nonexistent_attachment_returns_404(self):
        resp = self._delete(
            f"/api/v1/crm/opportunities/{self.lead.id}/attachments/{uuid_module.uuid4()}"
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_attachment_wrong_lead_returns_404(self):
        other_lead = Lead.objects.create(firm=self.firm, title="Other Lead")
        resp = self._delete(
            f"/api/v1/crm/opportunities/{other_lead.id}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_attachment_nonexistent_lead_returns_404(self):
        resp = self._delete(
            f"/api/v1/crm/opportunities/{uuid_module.uuid4()}/attachments/{self.attachment.id}"
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
        lead_id=None,
        content=b"FAKEAUDIO",
        content_type="audio/webm",
        filename="memo.webm",
    ):
        f = SimpleUploadedFile(filename, content, content_type=content_type)
        url = "/api/v1/crm/voice-memos/upload"
        if lead_id:
            url = f"{url}?lead_id={lead_id}"
        return self.client.post(url, data={"file": f}, **self.firm_headers())

    def test_upload_voice_memo_returns_metadata_without_creating_activity(self):
        before = Activity.objects.filter(type=ActivityType.VOICE_MEMO).count()
        resp = self._upload_voice(lead_id=str(self.lead.id))
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
        self.assertIsNone(doc.lead_id)

    def test_upload_voice_memo_rejects_non_audio(self):
        resp = self._upload_voice(content_type="text/plain", filename="memo.txt")
        self.assertEqual(resp.status_code, 400)

    def test_upload_voice_memo_invalid_lead_returns_404(self):
        resp = self._upload_voice(lead_id=str(uuid_module.uuid4()))
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# File Upload composer API tests (Fáze 7.2)
# ---------------------------------------------------------------------------


class FileUploadComposerAPITest(AttachmentAPIFixtureMixin, TestCase):
    """Smoke tests for ``POST /api/v1/crm/file-uploads/upload``."""

    URL = "/api/v1/crm/file-uploads/upload"

    def _upload_files(self, *files, lead_id=None):
        payload = [("files", f) for f in files]
        url = self.URL
        if lead_id:
            url = f"{url}?lead_id={lead_id}"
        return self.client.post(url, dict(payload), **self.firm_headers())

    def test_multi_file_upload_returns_one_entry_per_file_no_activity(self):
        before = Activity.objects.filter(type=ActivityType.FILE_UPLOAD).count()
        f1 = SimpleUploadedFile("a.pdf", b"PDF1", content_type="application/pdf")
        f2 = SimpleUploadedFile("b.png", b"PNGDATA", content_type="image/png")
        resp = self.client.post(
            f"{self.URL}?lead_id={self.lead.id}",
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

    def test_upload_invalid_lead_returns_404(self):
        f = SimpleUploadedFile("a.txt", b"hi", content_type="text/plain")
        resp = self.client.post(
            f"{self.URL}?lead_id={uuid_module.uuid4()}",
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
        self.assertIsNone(doc.lead_id)


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
        lead = Lead.objects.create(firm=firm, title="FUT lead")
        activity = Activity.objects.create(
            lead=lead,
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
        self.lead = Lead.objects.create(firm=self.firm, title="Fetch lead")

    def _make_activity(self, **metadata):
        return Activity.objects.create(
            lead=self.lead,
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
            firm=self.firm, lead=self.lead, title="Doc test task"
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
        other_lead = Lead.objects.create(firm=other_firm, title="Other Lead")
        other_task = Task.objects.create(firm=other_firm, lead=other_lead, title="Other")
        Document.objects.create(
            firm=other_firm, task=other_task, name="hidden.pdf",
            content_type="application/pdf", size_bytes=10,
        )
        # Hitting our firm with their task ID must 404 (cross-tenant).
        resp = self._get(f"/api/v1/crm/tasks/{other_task.id}/documents")
        self.assertEqual(resp.status_code, 404)

    def test_list_returns_only_task_documents(self):
        # One doc on our task, one on the lead — only the task one must appear.
        Document.objects.create(
            firm=self.firm, task=self.task, name="mine.txt",
            content_type="text/plain", size_bytes=4,
        )
        Document.objects.create(
            firm=self.firm, lead=self.lead, name="leadonly.txt",
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
        from crm.models import LeadStatus
        expected = {s.value for s in LeadStatus}
        self.assertEqual(returned_statuses, expected)

    def test_counts_reflect_leads(self):
        # setUp creates one NEW lead; add a WON lead with a value
        Lead.objects.create(firm=self.firm, title="Won Deal", status=LeadStatus.WON, value="5000.00")
        resp = self._get(self.URL)
        data = resp.json()
        rows_by_status = {row["status"]: row for row in data["statuses"]}
        self.assertEqual(rows_by_status["new"]["count"], 1)
        self.assertEqual(rows_by_status["won"]["count"], 1)
        self.assertEqual(rows_by_status["lost"]["count"], 0)

    def test_total_value_sums_all_statuses(self):
        Lead.objects.create(firm=self.firm, title="L1", status=LeadStatus.NEW, value="1000.00")
        Lead.objects.create(firm=self.firm, title="L2", status=LeadStatus.WON, value="2000.00")
        resp = self._get(self.URL)
        data = resp.json()
        self.assertAlmostEqual(data["total_value"], 3000.0, places=2)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Report Other Firm")
        Lead.objects.create(firm=other_firm, title="Foreign Lead", status=LeadStatus.WON)
        resp = self._get(self.URL)
        data = resp.json()
        rows_by_status = {row["status"]: row for row in data["statuses"]}
        # Our firm only has one NEW lead from setUp
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
        # Create a second lead so we can verify cross-lead aggregation
        self.lead2 = Lead.objects.create(firm=self.firm, title="Second Lead")
        self.a1 = Activity.objects.create(
            lead=self.lead, user=self.owner, type=ActivityType.COMMENT, content_text="First"
        )
        self.a2 = Activity.objects.create(
            lead=self.lead2, user=self.worker, type=ActivityType.CALL, content_text="Call"
        )

    def test_returns_200(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_returns_activities_across_all_leads(self):
        resp = self._get(self.URL)
        data = resp.json()
        self.assertEqual(len(data), 2)

    def test_includes_lead_title(self):
        resp = self._get(self.URL)
        titles = {item["lead_title"] for item in resp.json()}
        self.assertIn("Test Lead", titles)
        self.assertIn("Second Lead", titles)

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
            Activity.objects.create(lead=self.lead, type=ActivityType.COMMENT, content_text=f"m{i}")
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Feed Other Firm")
        other_lead = Lead.objects.create(firm=other_firm, title="Spy Lead")
        Activity.objects.create(lead=other_lead, type=ActivityType.COMMENT, content_text="spy")
        resp = self._get(self.URL)
        lead_ids = {item["lead_id"] for item in resp.json()}
        self.assertNotIn(str(other_lead.id), lead_ids)

    def test_requires_authentication(self):
        self.client.logout()
        resp = self._get(self.URL)
        self.assertIn(resp.status_code, [401, 403])


class OverdueTasksAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/reports/tasks/overdue"

    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.overdue_task = Task.objects.create(
            firm=self.firm,
            lead=self.lead,
            title="Overdue",
            due_date=now - dt.timedelta(days=2),
        )
        self.future_task = Task.objects.create(
            firm=self.firm,
            lead=self.lead,
            title="Future",
            due_date=now + dt.timedelta(days=2),
        )
        self.completed_overdue = Task.objects.create(
            firm=self.firm,
            lead=self.lead,
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

    def test_includes_lead_title(self):
        resp = self._get(self.URL)
        self.assertEqual(resp.json()[0]["lead_title"], "Test Lead")

    def test_no_due_date_tasks_excluded(self):
        Task.objects.create(firm=self.firm, lead=self.lead, title="No Due Date")
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
                lead=self.lead,
                title=f"Old task {i}",
                due_date=now - dt.timedelta(days=i + 3),
            )
        resp = self._get(self.URL, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)

    def test_tenant_isolation(self):
        other_firm = Firm.objects.create(name="Overdue Other Firm")
        other_lead = Lead.objects.create(firm=other_firm, title="Other Lead")
        Task.objects.create(
            firm=other_firm,
            lead=other_lead,
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

    def test_export_leads_csv(self):
        resp = self.client.get("/api/v1/integrations/export/leads.csv")
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
            "lead_id": str(self.lead.id),
        }
        resp = self.client.post(
            "/api/v1/erp/time-entries",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["duration_minutes"], 90)
        self.assertEqual(data["lead_id"], str(self.lead.id))

    def test_list_time_entries(self):
        TimeEntry.objects.create(
            firm=self.firm,
            user=self.owner,
            duration_minutes=30,
            lead=self.lead,
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
        from firms.models import Firm, Membership, MembershipRole
        other_firm = Firm.objects.create(name="Other ERP Firm", subscription_tier="pro")
        other_user = __import__("users.models", fromlist=["User"]).User.objects.create_user(
            email="erp_other@test.com", password="pass"
        )
        Membership.objects.create(user=other_user, firm=other_firm, role=MembershipRole.OWNER)
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
            "lead_id": str(self.lead.id),
        }
        resp = self.client.post(
            "/api/v1/erp/revenues",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "Project payment")
        self.assertEqual(data["lead_id"], str(self.lead.id))

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
# 19th iteration: TASK_ASSIGNED auto-log on realization/management +
# entity-scoped task list endpoints
# ---------------------------------------------------------------------------


class TaskActivityLogAcrossEntitiesAPITest(CRMAPIFixtureMixin, TestCase):
    """`create_task` should log a TASK_ASSIGNED Activity onto every entity
    the task is linked to (lead, realization, management) — not just lead."""

    URL = "/api/v1/crm/tasks"

    def test_task_creation_logs_activity_on_realization(self):
        from crm.models import Realization
        realization = Realization.objects.create(
            firm=self.firm, title="R1", customer=self.customer,
        )
        resp = self._post(self.URL, {
            "realization_id": str(realization.id),
            "title": "Plan kickoff",
        })
        self.assertEqual(resp.status_code, 201)
        # Activity logged onto realization
        self.assertTrue(
            Activity.objects.filter(
                realization=realization, type=ActivityType.TASK_ASSIGNED
            ).exists()
        )
        # No leakage onto lead
        self.assertFalse(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.TASK_ASSIGNED
            ).exists()
        )

    def test_task_creation_logs_activity_on_management(self):
        from crm.models import Management
        management = Management.objects.create(
            firm=self.firm, title="M1", customer=self.customer,
        )
        resp = self._post(self.URL, {
            "management_id": str(management.id),
            "title": "Renew SLA",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            Activity.objects.filter(
                management=management, type=ActivityType.TASK_ASSIGNED
            ).exists()
        )

    def test_task_creation_logs_activity_on_both_lead_and_realization(self):
        """When a task links to multiple entities, each gets its own log entry."""
        from crm.models import Realization
        realization = Realization.objects.create(
            firm=self.firm, title="R-multi", customer=self.customer,
        )
        resp = self._post(self.URL, {
            "lead_id": str(self.lead.id),
            "realization_id": str(realization.id),
            "title": "Multi-link task",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.TASK_ASSIGNED
            ).count(),
            1,
        )
        self.assertEqual(
            Activity.objects.filter(
                realization=realization, type=ActivityType.TASK_ASSIGNED
            ).count(),
            1,
        )


class RealizationTasksListAPITest(CRMAPIFixtureMixin, TestCase):
    """GET /api/v1/crm/realizations/{id}/tasks — entity-scoped task list."""

    def setUp(self):
        super().setUp()
        from crm.models import Realization
        self.realization = Realization.objects.create(
            firm=self.firm, title="R-listing", customer=self.customer,
        )
        self.url = f"/api/v1/crm/realizations/{self.realization.id}/tasks"

    def test_returns_200_empty_when_no_tasks(self):
        resp = self._get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_returns_only_tasks_for_this_realization(self):
        from crm.models import Realization
        other_realization = Realization.objects.create(
            firm=self.firm, title="R-other", customer=self.customer,
        )
        Task.objects.create(
            firm=self.firm, realization=self.realization, title="On this R",
        )
        Task.objects.create(
            firm=self.firm, realization=other_realization, title="On other R",
        )
        Task.objects.create(firm=self.firm, lead=self.lead, title="Lead-only")
        resp = self._get(self.url)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["title"], "On this R")
        self.assertEqual(body[0]["realization_id"], str(self.realization.id))

    def test_returns_404_for_unknown_realization(self):
        import uuid
        resp = self._get(f"/api/v1/crm/realizations/{uuid.uuid4()}/tasks")
        self.assertEqual(resp.status_code, 404)

    def test_tenant_isolation_returns_404_for_other_firm_realization(self):
        from crm.models import Realization
        other_firm = Firm.objects.create(name="Other-19", subscription_tier="pro")
        other_r = Realization.objects.create(firm=other_firm, title="Forbidden")
        resp = self._get(f"/api/v1/crm/realizations/{other_r.id}/tasks")
        self.assertEqual(resp.status_code, 404)

    def test_pagination_respects_page_size(self):
        for i in range(5):
            Task.objects.create(
                firm=self.firm, realization=self.realization, title=f"T{i}",
            )
        resp = self._get(self.url, {"page": 1, "page_size": 3})
        self.assertEqual(len(resp.json()), 3)


class ManagementTasksListAPITest(CRMAPIFixtureMixin, TestCase):
    """GET /api/v1/crm/management/{id}/tasks — entity-scoped task list."""

    def setUp(self):
        super().setUp()
        from crm.models import Management
        self.management = Management.objects.create(
            firm=self.firm, title="M-listing", customer=self.customer,
        )
        self.url = f"/api/v1/crm/management/{self.management.id}/tasks"

    def test_returns_only_tasks_for_this_management(self):
        from crm.models import Management
        other = Management.objects.create(
            firm=self.firm, title="M-other", customer=self.customer,
        )
        Task.objects.create(
            firm=self.firm, management=self.management, title="On this M",
        )
        Task.objects.create(firm=self.firm, management=other, title="On other M")
        resp = self._get(self.url)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["title"], "On this M")
        self.assertEqual(body[0]["management_id"], str(self.management.id))

    def test_returns_404_for_unknown_management(self):
        import uuid
        resp = self._get(f"/api/v1/crm/management/{uuid.uuid4()}/tasks")
        self.assertEqual(resp.status_code, 404)

    def test_tenant_isolation_returns_404_for_other_firm_management(self):
        from crm.models import Management
        other_firm = Firm.objects.create(name="Other-19m", subscription_tier="pro")
        other_m = Management.objects.create(firm=other_firm, title="Forbidden")
        resp = self._get(f"/api/v1/crm/management/{other_m.id}/tasks")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# 20th iteration: TASK_COMPLETED symmetric auto-log on realization/management
# ---------------------------------------------------------------------------


class TaskCompleteActivityLogAcrossEntitiesAPITest(CRMAPIFixtureMixin, TestCase):
    """`complete_task` should log a TASK_COMPLETED Activity onto every
    entity the task is linked to (lead, realization, management) — mirror
    of the 19th-iteration refactor in `create_task`."""

    def test_complete_task_logs_activity_on_realization(self):
        from crm.models import Realization
        realization = Realization.objects.create(
            firm=self.firm, title="R-complete", customer=self.customer,
        )
        task = Task.objects.create(
            firm=self.firm, realization=realization, title="Do thing",
        )
        resp = self._post(f"/api/v1/crm/tasks/{task.id}/complete", {})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Activity.objects.filter(
                realization=realization, type=ActivityType.TASK_COMPLETED
            ).exists()
        )
        # No leakage onto lead
        self.assertFalse(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.TASK_COMPLETED
            ).exists()
        )

    def test_complete_task_logs_activity_on_management(self):
        from crm.models import Management
        management = Management.objects.create(
            firm=self.firm, title="M-complete", customer=self.customer,
        )
        task = Task.objects.create(
            firm=self.firm, management=management, title="Renew",
        )
        resp = self._post(f"/api/v1/crm/tasks/{task.id}/complete", {})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Activity.objects.filter(
                management=management, type=ActivityType.TASK_COMPLETED
            ).exists()
        )

    def test_complete_task_logs_activity_on_both_lead_and_realization(self):
        """Multi-link task → exactly one Activity per linked entity."""
        from crm.models import Realization
        realization = Realization.objects.create(
            firm=self.firm, title="R-multi-complete", customer=self.customer,
        )
        task = Task.objects.create(
            firm=self.firm, lead=self.lead, realization=realization,
            title="Multi-link complete",
        )
        resp = self._post(f"/api/v1/crm/tasks/{task.id}/complete", {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Activity.objects.filter(
                lead=self.lead, type=ActivityType.TASK_COMPLETED
            ).count(),
            1,
        )
        self.assertEqual(
            Activity.objects.filter(
                realization=realization, type=ActivityType.TASK_COMPLETED
            ).count(),
            1,
        )

    def test_complete_already_completed_realization_task_is_idempotent(self):
        """Re-completing a realization-linked task does not double-log."""
        from crm.models import Realization
        realization = Realization.objects.create(
            firm=self.firm, title="R-idem", customer=self.customer,
        )
        task = Task.objects.create(
            firm=self.firm, realization=realization, title="Idem task",
        )
        self._post(f"/api/v1/crm/tasks/{task.id}/complete", {})
        self._post(f"/api/v1/crm/tasks/{task.id}/complete", {})
        self.assertEqual(
            Activity.objects.filter(
                realization=realization, type=ActivityType.TASK_COMPLETED
            ).count(),
            1,
        )


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
            lead=self.lead,
            user=self.owner,
            type=activity_type,
            metadata=metadata,
        )
        tool.process_action(
            activity,
            self.lead,
            {"metadata": metadata},
            {"firm": self.firm, "user": self.owner, "entity_title": self.lead.title},
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
        self.assertEqual(task.lead_id, self.lead.id)
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
            lead=self.lead,
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
            lead=self.lead,
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
        # An Activity of type TASK_EXPIRED is logged on the same lead.
        self.assertTrue(
            Activity.objects.filter(
                lead=self.lead, task=task, type=ActivityType.TASK_EXPIRED
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
            lead=self.lead,
            user=self.owner,
            type=activity_type,
            metadata=metadata,
        )
        tool.process_action(
            activity, self.lead, {"metadata": metadata},
            {"firm": self.firm, "user": self.owner, "entity_title": self.lead.title},
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
            lead=self.lead,
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
            defaults={"role": MembershipRole.OWNER},
        )

    def test_activity_out_serializer_exposes_task_id(self):
        from crm.api import _activity_out
        task = Task.objects.create(firm=self.firm, lead=self.lead, title="Parent task")
        activity = Activity.objects.create(
            lead=self.lead, user=self.owner, type="comment",
            content_text="hello", task=task,
        )
        out = _activity_out(activity, self.owner)
        self.assertEqual(out["task_id"], str(task.id))

    def test_activity_out_task_id_is_none_when_unlinked(self):
        from crm.api import _activity_out
        activity = Activity.objects.create(
            lead=self.lead, user=self.owner, type="comment", content_text="hi",
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
        self.lead = Lead.objects.create(
            firm=self.firm, customer=self.customer, title="Mig Lead",
            status=LeadStatus.NEW, source=LeadSource.WEB,
        )

    def _run_migration(self):
        # Re-apply the data-migration function directly against the live
        # apps registry — emulates what Django would do during migrate.
        from django.apps import apps
        from importlib import import_module
        mod = import_module("crm.migrations.0043_backfill_meeting_scheduled_tasks")
        mod.backfill_meeting_scheduled_tasks(apps, None)

    def test_creates_task_for_legacy_meeting_scheduled_activity(self):
        start = (timezone.now() + dt.timedelta(days=1)).isoformat()
        a = Activity.objects.create(
            lead=self.lead, type=ActivityType.MEETING_SCHEDULED,
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
        self.assertEqual(task.lead_id, self.lead.id)
        self.assertTrue(task.metadata.get("backfilled"))

    def test_skips_activities_already_linked(self):
        existing_task = Task.objects.create(
            firm=self.firm, lead=self.lead, title="Already linked",
        )
        a = Activity.objects.create(
            lead=self.lead, type=ActivityType.MEETING_SCHEDULED,
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
            lead=self.lead, type=ActivityType.MEETING_SCHEDULED, metadata={},
        )
        before = Task.objects.count()
        self._run_migration()
        a.refresh_from_db()
        self.assertIsNone(a.task_id)
        self.assertEqual(Task.objects.count(), before)

    def test_is_idempotent_when_run_twice(self):
        Activity.objects.create(
            lead=self.lead, type=ActivityType.MEETING_SCHEDULED,
            metadata={"start_at": (timezone.now() + dt.timedelta(days=1)).isoformat()},
        )
        self._run_migration()
        count_after_first = Task.objects.count()
        self._run_migration()
        self.assertEqual(Task.objects.count(), count_after_first)

    def test_does_not_touch_non_meeting_scheduled_activities(self):
        Activity.objects.create(
            lead=self.lead, type="comment", content_text="hi",
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
                firm=self.firm, lead=self.lead, title=kw.pop("title", "T"),
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
        self.assertEqual(row["lead_id"], str(self.lead.id))
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
        Membership.objects.create(user=other_user, firm=other_firm, role=MembershipRole.OWNER)
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
            lead=self.lead,
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
            lead=self.lead,
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
        self.assertEqual(acts.first().lead, self.lead)

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
