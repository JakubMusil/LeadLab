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
        self.firm = Firm.objects.create(name="CRM Firm")
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
