"""
Management command: load_demo_data

Creates a self-contained demo workspace with realistic sample data so that
evaluators and developers can explore LeadLab without having to enter data
manually.

Usage:
    python manage.py load_demo_data [--email <owner-email>] [--password <password>]

If the email already exists the command attaches the demo workspace to that
account instead of creating a new user. Running the command a second time for
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
    ContactType,
    Lead,
    LeadSource,
    LeadStatus,
    Project,
    Task,
    TaskPriority,
    TaskStatus,
)
from firms.models import Firm, Membership, MembershipRole

User = get_user_model()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

CUSTOMERS_COMPANIES = [
    {
        "company_name": "Tesla Motors Europe",
        "email": "partners@tesla.com",
        "phone": "+420 800 123 456",
        "ico": "11223344",
        "dic": "CZ11223344",
        "address_street": "Průmyslová 1",
        "address_city": "Praha",
        "address_zip": "10000",
        "address_country": "Czech Republic",
        "website": "https://www.tesla.com",
        "type": ContactType.COMPANY,
        "tags": ["enterprise", "automotive", "vip"],
    },
    {
        "company_name": "Avast Software",
        "email": "enterprise@avast.com",
        "phone": "+420 800 987 654",
        "ico": "44332211",
        "dic": "CZ44332211",
        "address_street": "Pikrtova 1737/1A",
        "address_city": "Praha",
        "address_zip": "14000",
        "address_country": "Czech Republic",
        "website": "https://www.avast.com",
        "type": ContactType.COMPANY,
        "tags": ["enterprise", "software"],
    },
    {
        "company_name": "Seznam.cz, a.s.",
        "email": "obchod@seznam.cz",
        "phone": "+420 234 694 111",
        "ico": "26168685",
        "dic": "CZ26168685",
        "address_street": "Radlická 3294/10",
        "address_city": "Praha 5",
        "address_zip": "15000",
        "address_country": "Czech Republic",
        "website": "https://www.seznam.cz",
        "type": ContactType.COMPANY,
        "tags": ["tech", "smb", "marketing"],
    },
]

CUSTOMERS_PERSONS = [
    {
        "first_name": "Elon",
        "last_name": "Musk",
        "email": "elon@tesla.com",
        "phone": "+420 777 123 456",
        "company_index": 0,
        "type": ContactType.PERSON,
        "tags": ["vip", "decision-maker"],
    },
    {
        "first_name": "Ondřej",
        "last_name": "Vlček",
        "email": "ondrej.vlcek@avast.com",
        "phone": "+420 777 987 654",
        "company_index": 1,
        "type": ContactType.PERSON,
        "tags": ["decision-maker"],
    },
    {
        "first_name": "Ivo",
        "last_name": "Lukačovič",
        "email": "ivo@seznam.cz",
        "phone": "+420 777 111 222",
        "company_index": 2,
        "type": ContactType.PERSON,
        "tags": ["founder"],
    },
]

LEADS = [
    {
        "title": "Zavádění CRM - Tesla Motors Europe",
        "description": "Zhodnocení LeadLab pro mezinárodní nasazení s 200 uživateli.",
        "status": LeadStatus.NEGOTIATION,
        "source": LeadSource.REFERRAL,
        "value": Decimal("48000.00"),
        "currency": "EUR",
        "company_index": 0,
        "contact_person_index": 0,
    },
    {
        "title": "Konzultace k redesignu webu - Avast",
        "description": "Návrh nové struktury firemních stránek a propojení na CRM systém.",
        "status": LeadStatus.PROPOSAL,
        "source": LeadSource.WEB,
        "value": Decimal("12500.00"),
        "currency": "CZK",
        "company_index": 1,
        "contact_person_index": 1,
    },
    {
        "title": "Roční licence a podpora - Seznam.cz",
        "description": "Obnova balíčku pro profesionální marketingové týmy.",
        "status": LeadStatus.WON,
        "source": LeadSource.EMAIL,
        "value": Decimal("3600.00"),
        "currency": "EUR",
        "company_index": 2,
        "contact_person_index": 2,
    },
]

ACTIVITIES_BY_LEAD = {
    0: [
        ("Úvodní hovor s Elonem Musk o požadavcích na LeadLab.", ActivityType.CALL),
        ("Zasláno produktové demo a předběžná cenová nabídka.", ActivityType.EMAIL_OUT),
        ("Elon potvrdil zájem o testování prémiového tarifu.", ActivityType.EMAIL_IN),
    ],
    1: [
        ("Zahájen discovery proces k redesignu.", ActivityType.CALL),
        ("Odeslány příklady dřívějších projektů.", ActivityType.EMAIL_OUT),
    ],
    2: [
        ("Zasláno upozornění na obnovení ročního tarifu.", ActivityType.EMAIL_OUT),
        ("Zákazník potvrdil zaplacení faktury.", ActivityType.EMAIL_IN),
    ],
}

TASKS = [
    ("Odeslat doplňující nabídku pro Teslu", 0, 3, TaskPriority.HIGH, TaskStatus.TODO),
    ("Připravit demo prezentaci pro Avast", 1, 7, TaskPriority.MEDIUM, TaskStatus.IN_PROGRESS),
    ("Připravit licenční smlouvu pro Seznam.cz", 2, 2, TaskPriority.HIGH, TaskStatus.TODO),
]

PROJECTS = [
    "Q3 Obchodní Plán",
    "Klíčoví Zákazníci",
    "Předplatné a Retence",
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
            self.stdout.write(self.style.SUCCESS(f"Created user: {email} (password: {password})"))
        else:
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

        # ---- companies ----
        companies = []
        for data in CUSTOMERS_COMPANIES:
            company, created = Customer.objects.get_or_create(
                firm=firm,
                email=data["email"],
                defaults={
                    "company_name": data["company_name"],
                    "phone": data["phone"],
                    "ico": data["ico"],
                    "dic": data["dic"],
                    "address_street": data["address_street"],
                    "address_city": data["address_city"],
                    "address_zip": data["address_zip"],
                    "address_country": data["address_country"],
                    "website": data["website"],
                    "type": data["type"],
                    "tags": data["tags"],
                },
            )
            companies.append(company)
            if created:
                self.stdout.write(f" + Company: {company.company_name}")

        # ---- persons ----
        persons = []
        for data in CUSTOMERS_PERSONS:
            linked_company = companies[data["company_index"]]
            person, created = Customer.objects.get_or_create(
                firm=firm,
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data["phone"],
                    "company": linked_company,
                    "company_name": linked_company.company_name,
                    "type": data["type"],
                    "tags": data["tags"],
                },
            )
            persons.append(person)
            if created:
                self.stdout.write(f" + Person: {person.first_name} {person.last_name}")

        # ---- leads ----
        leads = []
        for i, data in enumerate(LEADS):
            company = companies[data["company_index"]]
            contact_person = persons[data["contact_person_index"]]
            lead, created = Lead.objects.get_or_create(
                firm=firm,
                title=data["title"],
                defaults={
                    "description": data["description"],
                    "status": data["status"],
                    "source": data["source"],
                    "value": data["value"],
                    "currency": data["currency"],
                    "company": company,
                    "contact_person": contact_person,
                    "assigned_to": user,
                },
            )
            leads.append(lead)
            if created:
                self.stdout.write(f" + Lead: {lead.title}")

        # ---- activities ----
        for lead_index, activity_list in ACTIVITIES_BY_LEAD.items():
            if lead_index >= len(leads):
                continue
            target_lead = leads[lead_index]
            if Activity.objects.filter(lead=target_lead).exists():
                continue
            for body, atype in activity_list:
                Activity.objects.create(
                    lead=target_lead,
                    user=user,
                    type=atype,
                    content_text=body,
                )
            self.stdout.write(f" + {len(activity_list)} activities on '{target_lead.title}'")

        # ---- projects ----
        for project_name in PROJECTS:
            project, created = Project.objects.get_or_create(firm=firm, name=project_name)
            if created:
                self.stdout.write(f" + Project: {project_name}")

        # ---- tasks ----
        now = timezone.now()
        for title, lead_index, days_offset, priority, status in TASKS:
            if lead_index >= len(leads):
                continue
            target_lead = leads[lead_index]
            task, created = Task.objects.get_or_create(
                firm=firm,
                title=title,
                lead=target_lead,
                defaults={
                    "assigned_to": user,
                    "due_date": now + timedelta(days=days_offset),
                    "priority": priority,
                    "status": status,
                    "is_completed": status == TaskStatus.DONE,
                },
            )
            if created:
                self.stdout.write(f" + Task: {title}")

        self.stdout.write(self.style.SUCCESS("\nDemo data loaded successfully!"))
