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
# Lead Attachments API tests
# ---------------------------------------------------------------------------

import io
import uuid as uuid_module

from django.core.files.uploadedfile import SimpleUploadedFile

from crm.models import LeadAttachment


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
        LeadAttachment.objects.create(
            firm=other_firm,
            lead=other_lead,
            original_filename="secret.pdf",
            content_type="application/pdf",
            size_bytes=100,
        )
        resp = self._get(f"/api/v1/crm/opportunities/{self.lead.id}/attachments")
        self.assertEqual(resp.json(), [])

    def test_list_attachments_pagination(self):
        for i in range(5):
            LeadAttachment.objects.create(
                firm=self.firm,
                lead=self.lead,
                original_filename=f"file{i}.txt",
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
        for attachment in LeadAttachment.objects.filter(lead=self.lead):
            attachment.file.delete(save=False)
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
        self.assertEqual(LeadAttachment.objects.filter(lead=self.lead).count(), 1)

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
        # Create an attachment record without a physical file for delete tests.
        self.attachment = LeadAttachment.objects.create(
            firm=self.firm,
            lead=self.lead,
            original_filename="deleteme.txt",
            content_type="text/plain",
            size_bytes=5,
        )

    def test_delete_attachment_admin_succeeds(self):
        resp = self._delete(
            f"/api/v1/crm/opportunities/{self.lead.id}/attachments/{self.attachment.id}"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(LeadAttachment.objects.filter(id=self.attachment.id).exists())

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
