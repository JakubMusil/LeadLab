"""
Management command: load_demo_data

Creates a self-contained demo workspace with realistic sample data so that
evaluators and developers can explore LeadLab without having to enter data
manually.

Usage:
    python manage.py load_demo_data [--email <owner-email>] [--password <password>]

If the email already exists the command attaches the demo workspace to that
account instead of creating a new user.  Running the command a second time for
the same owner email is safe — it will skip objects that already exist.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.models import (
    Activity,
    ActivityType,
    Customer,
    Lead,
    LeadSource,
    LeadStatus,
    Task,
)
from firms.models import Firm, Membership, MembershipRole

User = get_user_model()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

CUSTOMERS = [
    {
        "first_name": "Alice",
        "last_name": "Johnson",
        "email": "alice.johnson@example.com",
        "phone": "+1 555-0101",
        "company_name": "Bright Future LLC",
        "tags": ["enterprise", "vip"],
    },
    {
        "first_name": "Bob",
        "last_name": "Smith",
        "email": "bob.smith@example.com",
        "phone": "+1 555-0102",
        "company_name": "Smith & Partners",
        "tags": ["smb"],
    },
    {
        "first_name": "Carol",
        "last_name": "Williams",
        "email": "carol.williams@example.com",
        "phone": "+1 555-0103",
        "company_name": "Williams Group",
        "tags": ["prospect"],
    },
    {
        "first_name": "David",
        "last_name": "Brown",
        "email": "david.brown@example.com",
        "phone": "+1 555-0104",
        "company_name": "Brown Industries",
        "tags": ["enterprise"],
    },
    {
        "first_name": "Emma",
        "last_name": "Davis",
        "email": "emma.davis@example.com",
        "phone": "+1 555-0105",
        "company_name": "Davis Digital",
        "tags": ["startup", "prospect"],
    },
]

LEADS = [
    {
        "title": "Enterprise CRM rollout — Bright Future",
        "description": "Evaluate LeadLab for a 200-seat deployment across three offices.",
        "status": LeadStatus.NEGOTIATION,
        "source": LeadSource.REFERRAL,
        "value": Decimal("48000.00"),
        "currency": "USD",
        "customer_index": 0,
    },
    {
        "title": "Website redesign consultation",
        "description": "Consulting engagement to modernise their public site and integrate CRM.",
        "status": LeadStatus.PROPOSAL,
        "source": LeadSource.WEB,
        "value": Decimal("12500.00"),
        "currency": "USD",
        "customer_index": 1,
    },
    {
        "title": "Annual software license renewal",
        "description": "Renewal of the Pro plan for the next 12 months.",
        "status": LeadStatus.WON,
        "source": LeadSource.EMAIL,
        "value": Decimal("3600.00"),
        "currency": "USD",
        "customer_index": 2,
    },
    {
        "title": "Inbound — Brown Industries cold outreach",
        "description": "Responded to LinkedIn campaign; interested in sales automation features.",
        "status": LeadStatus.CONTACTED,
        "source": LeadSource.SOCIAL,
        "value": Decimal("9000.00"),
        "currency": "USD",
        "customer_index": 3,
    },
    {
        "title": "Startup onboarding package — Davis Digital",
        "description": "Small team looking for an affordable CRM to replace spreadsheets.",
        "status": LeadStatus.NEW,
        "source": LeadSource.WEB,
        "value": Decimal("1200.00"),
        "currency": "USD",
        "customer_index": 4,
    },
    {
        "title": "Lost — competitor selected",
        "description": "Prospect chose a competitor after a 3-week evaluation.",
        "status": LeadStatus.LOST,
        "source": LeadSource.COLD_CALL,
        "value": Decimal("7500.00"),
        "currency": "USD",
        "customer_index": 1,
    },
]

ACTIVITIES = [
    ("Introduced LeadLab via introductory call — positive reception.", ActivityType.CALL),
    ("Sent product overview deck and pricing sheet.", ActivityType.EMAIL_OUT),
    ("Follow-up email: confirmed interest in Pro plan.", ActivityType.EMAIL_IN),
    ("Demo session scheduled for next Tuesday.", ActivityType.MEETING),
    ("Proposal draft sent for review.", ActivityType.EMAIL_OUT),
    ("Received signed contract — deal closed!", ActivityType.COMMENT),
]

TASKS = [
    ("Send follow-up email", 3),
    ("Prepare demo environment", 7),
    ("Schedule stakeholder call", 5),
    ("Review proposal feedback", 2),
    ("Update CRM with call notes", 1),
]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Populate the database with a demo workspace, contacts, leads, "
        "activities, and tasks for evaluation and development purposes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="demo@leadlab.io",
            help="Email address for the demo workspace owner (default: demo@leadlab.io).",
        )
        parser.add_argument(
            "--password",
            default="Demo1234!",
            help="Password for a newly created demo user (default: Demo1234!).",
        )
        parser.add_argument(
            "--firm-name",
            default="LeadLab Demo",
            help="Name for the demo workspace (default: 'LeadLab Demo').",
        )
        parser.add_argument(
            "--superadmin",
            action="store_true",
            default=False,
            help="Grant the demo user superadmin (is_staff + is_superuser) privileges.",
        )

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        firm_name = options["firm_name"]
        superadmin = options["superadmin"]

        # ---- owner user ----
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": "Demo",
                "last_name": "User",
                "is_active": True,
                "is_staff": superadmin,
                "is_superuser": superadmin,
            },
        )
        if user_created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created user: {email}  (password: {password})"))
        else:
            # Always sync password and superadmin flags on existing user
            user.set_password(password)
            user.is_staff = superadmin
            user.is_superuser = superadmin
            user.save()
            self.stdout.write(f"Using existing user: {email}")

        # ---- firm ----
        firm, firm_created = Firm.objects.get_or_create(name=firm_name)
        if firm_created:
            self.stdout.write(self.style.SUCCESS(f"Created firm: {firm_name}"))
        else:
            self.stdout.write(f"Using existing firm: {firm_name}")

        Membership.objects.get_or_create(
            user=user,
            firm=firm,
            defaults={"role": MembershipRole.OWNER},
        )

        # ---- customers ----
        customers = []
        for data in CUSTOMERS:
            customer, created = Customer.objects.get_or_create(
                firm=firm,
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data["phone"],
                    "company_name": data["company_name"],
                    "tags": data["tags"],
                },
            )
            customers.append(customer)
            if created:
                self.stdout.write(f"  + Customer: {customer.first_name} {customer.last_name}")

        # ---- leads ----
        leads = []
        base_date = timezone.now() - timedelta(days=60)
        for i, data in enumerate(LEADS):
            customer = customers[data["customer_index"]]
            lead, created = Lead.objects.get_or_create(
                firm=firm,
                title=data["title"],
                defaults={
                    "description": data["description"],
                    "status": data["status"],
                    "source": data["source"],
                    "value": data["value"],
                    "currency": data["currency"],
                    "customer": customer,
                    "assigned_to": user,
                },
            )
            leads.append(lead)
            if created:
                self.stdout.write(f"  + Lead: {lead.title[:60]}")

        # ---- activities ----
        if leads:
            primary_lead = leads[0]
            existing_count = Activity.objects.filter(lead=primary_lead).count()
            if existing_count == 0:
                for j, (body, atype) in enumerate(ACTIVITIES):
                    Activity.objects.create(
                        lead=primary_lead,
                        user=user,
                        type=atype,
                        content_text=body,
                    )
                self.stdout.write(f"  + {len(ACTIVITIES)} activities on '{primary_lead.title[:40]}'")

        # ---- tasks ----
        if leads:
            primary_lead = leads[0]
            existing_tasks = Task.objects.filter(lead=primary_lead).count()
            if existing_tasks == 0:
                now = timezone.now()
                for title, days_offset in TASKS:
                    Task.objects.create(
                        firm=firm,
                        lead=primary_lead,
                        assigned_to=user,
                        title=title,
                        due_date=now + timedelta(days=days_offset),
                    )
                self.stdout.write(f"  + {len(TASKS)} tasks on '{primary_lead.title[:40]}'")

        self.stdout.write(self.style.SUCCESS("\nDemo data loaded successfully!"))
        self.stdout.write(
            f"\nLogin at /app/ with:\n"
            f"  Email:    {email}\n"
            f"  Password: {password}\n"
        )
