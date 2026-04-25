from django.test import TestCase
from django.utils import timezone

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
    URL = "/api/v1/crm/customers"

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
    URL = "/api/v1/crm/customers"

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
        resp = self._get(f"/api/v1/crm/customers/{self.customer.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email"], "jane@example.com")

    def test_get_nonexistent_customer_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/customers/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)

    def test_get_other_firm_customer_returns_404(self):
        other_firm = Firm.objects.create(name="Other")
        other_cust = Customer.objects.create(firm=other_firm, first_name="Eve")
        resp = self._get(f"/api/v1/crm/customers/{other_cust.id}")
        self.assertEqual(resp.status_code, 404)


class CustomerUpdateAPITest(CRMAPIFixtureMixin, TestCase):
    def test_update_customer(self):
        resp = self._put(
            f"/api/v1/crm/customers/{self.customer.id}",
            {"first_name": "Janet", "last_name": "Doe", "email": "janet@example.com",
             "phone": "", "company_name": "", "tags": [], "metadata": {}},
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Janet")

    def test_update_nonexistent_customer_returns_404(self):
        import uuid
        resp = self._put(
            f"/api/v1/crm/customers/{uuid.uuid4()}",
            {"first_name": "X", "last_name": "", "email": "", "phone": "",
             "company_name": "", "tags": [], "metadata": {}},
        )
        self.assertEqual(resp.status_code, 404)


class CustomerDeleteAPITest(CRMAPIFixtureMixin, TestCase):
    def test_delete_customer_admin_succeeds(self):
        resp = self._delete(f"/api/v1/crm/customers/{self.customer.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Customer.objects.filter(id=self.customer.id).exists())

    def test_delete_customer_worker_returns_403(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(f"/api/v1/crm/customers/{self.customer.id}")
        self.assertEqual(resp.status_code, 403)


# -- Leads -------------------------------------------------------------------

class LeadListAPITest(CRMAPIFixtureMixin, TestCase):
    URL = "/api/v1/crm/leads"

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
    URL = "/api/v1/crm/leads"

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
        resp = self._get(f"/api/v1/crm/leads/{self.lead.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Test Lead")

    def test_get_nonexistent_lead_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/leads/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)


class LeadUpdateAPITest(CRMAPIFixtureMixin, TestCase):
    def test_patch_lead_title(self):
        resp = self._patch(f"/api/v1/crm/leads/{self.lead.id}", {"title": "Updated"})
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.title, "Updated")

    def test_patch_status_creates_activity(self):
        resp = self._patch(f"/api/v1/crm/leads/{self.lead.id}", {"status": "contacted"})
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
        resp = self._patch(f"/api/v1/crm/leads/{uuid.uuid4()}", {"title": "X"})
        self.assertEqual(resp.status_code, 404)


class LeadDeleteAPITest(CRMAPIFixtureMixin, TestCase):
    def test_delete_lead_admin_succeeds(self):
        resp = self._delete(f"/api/v1/crm/leads/{self.lead.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Lead.objects.filter(id=self.lead.id).exists())

    def test_delete_lead_worker_returns_403(self):
        self.client.login(username="worker@crm-api.com", password="pass")
        resp = self._delete(f"/api/v1/crm/leads/{self.lead.id}")
        self.assertEqual(resp.status_code, 403)


# -- Activities --------------------------------------------------------------

class ActivityListAPITest(CRMAPIFixtureMixin, TestCase):
    def test_list_activities_empty(self):
        resp = self._get(f"/api/v1/crm/leads/{self.lead.id}/activities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_activities_after_comment(self):
        Activity.objects.create(
            lead=self.lead, user=self.owner, type=ActivityType.COMMENT, content_text="Hello"
        )
        resp = self._get(f"/api/v1/crm/leads/{self.lead.id}/activities")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_list_activities_pagination(self):
        for i in range(5):
            Activity.objects.create(
                lead=self.lead, type=ActivityType.COMMENT, content_text=f"msg {i}"
            )
        resp = self._get(
            f"/api/v1/crm/leads/{self.lead.id}/activities",
            {"page": 1, "page_size": 3},
        )
        self.assertEqual(len(resp.json()), 3)

    def test_list_activities_nonexistent_lead_returns_404(self):
        import uuid
        resp = self._get(f"/api/v1/crm/leads/{uuid.uuid4()}/activities")
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

import json as _json


class TierLimitLeadCreateAPITest(TestCase):
    """create_lead enforces the Free-tier 50-lead limit."""

    URL = "/api/v1/crm/leads"

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
            data=_json.dumps({"title": "Over limit"}),
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
            data=_json.dumps({"title": "Just within limit"}),
            content_type="application/json",
            **self._firm_headers(),
        )
        self.assertEqual(resp.status_code, 201)
