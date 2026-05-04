"""
Management command: load_demo_data

Creates a self-contained demo workspace with realistic Czech sample data so that
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
from django.db import transaction
from django.utils import timezone

from crm.models import (
    Activity,
    ActivityType,
    Category,
    CategoryField,
    Customer,
    ContactType,
    PipelineRecord,
    RecordSource,
    RecordStatus,
    Project,
    Stage,
    Task,
    TaskPriority,
    TaskStatus,
)
from firms.models import Firm, Membership, MembershipRole

User = get_user_model()


# ---------------------------------------------------------------------------
# Pipeline categories (Příležitosti / Realizace / Správa)
# ---------------------------------------------------------------------------

PIPELINE_CATEGORIES = [
    {
        "name": "Příležitosti",
        "slug": "prileziosti",
        "icon": "funnel",
        "color": "#3B82F6",
        "order": 0,
        "stages": [
            {"name": "Nový", "label": "Nový", "color": "#94A3B8", "order": 0},
            {"name": "Osloven", "label": "Osloven", "color": "#60A5FA", "order": 1},
            {"name": "Nabídka", "label": "Nabídka", "color": "#FBBF24", "order": 2},
            {"name": "Vyjednávání", "label": "Vyjednávání", "color": "#F97316", "order": 3},
            {"name": "Vyhráno", "label": "Vyhráno", "color": "#22C55E", "order": 4, "is_terminal": True, "is_won": True},
            {"name": "Prohráno", "label": "Prohráno", "color": "#EF4444", "order": 5, "is_terminal": True},
        ],
        "fields": [
            {"field_key": "value_currency", "is_visible": True, "is_required": False, "order": 0},
            {"field_key": "expires_at", "is_visible": True, "is_required": False, "order": 1},
            {"field_key": "source", "is_visible": True, "is_required": False, "order": 2},
        ],
    },
    {
        "name": "Realizace",
        "slug": "realizace",
        "icon": "wrench-screwdriver",
        "color": "#10B981",
        "order": 1,
        "stages": [
            {"name": "Zahájení", "label": "Zahájení", "color": "#94A3B8", "order": 0},
            {"name": "Zpracování", "label": "Zpracování", "color": "#34D399", "order": 1},
            {"name": "Předání", "label": "Předání", "color": "#FBBF24", "order": 2},
            {"name": "Dokončeno", "label": "Dokončeno", "color": "#22C55E", "order": 3, "is_terminal": True, "is_won": True},
            {"name": "Zrušeno", "label": "Zrušeno", "color": "#EF4444", "order": 4, "is_terminal": True},
        ],
        "fields": [
            {"field_key": "date_range", "is_visible": True, "is_required": False, "order": 0},
            {"field_key": "notes", "is_visible": True, "is_required": False, "order": 1},
            {"field_key": "origin_record", "is_visible": True, "is_required": False, "order": 2},
        ],
    },
    {
        "name": "Správa",
        "slug": "sprava",
        "icon": "shield-check",
        "color": "#8B5CF6",
        "order": 2,
        "stages": [
            {"name": "Aktivní", "label": "Aktivní", "color": "#94A3B8", "order": 0},
            {"name": "Monitorování", "label": "Monitorování", "color": "#A78BFA", "order": 1},
            {"name": "Uzavřeno", "label": "Uzavřeno", "color": "#22C55E", "order": 2, "is_terminal": True, "is_won": True},
        ],
        "fields": [
            {"field_key": "notes", "is_visible": True, "is_required": False, "order": 0},
            {"field_key": "expires_at", "is_visible": True, "is_required": False, "order": 1},
        ],
    },
]


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

CUSTOMERS_COMPANIES = [
    {
        "company_name": "Rohlík.cz s.r.o.",
        "email": "obchod@rohlik.cz",
        "phone": "+420 800 600 700",
        "ico": "03950914",
        "dic": "CZ03950914",
        "address_street": "Jankovcova 1037/49",
        "address_city": "Praha 7",
        "address_zip": "17000",
        "address_country": "Česká republika",
        "website": "https://www.rohlik.cz",
        "type": ContactType.COMPANY,
        "tags": ["e-commerce", "enterprise", "vip"],
    },
    {
        "company_name": "Komerční banka, a.s.",
        "email": "partneri@kb.cz",
        "phone": "+420 800 111 055",
        "ico": "45317054",
        "dic": "CZ45317054",
        "address_street": "Na Příkopě 33/969",
        "address_city": "Praha 1",
        "address_zip": "11407",
        "address_country": "Česká republika",
        "website": "https://www.kb.cz",
        "type": ContactType.COMPANY,
        "tags": ["finance", "enterprise", "banka"],
    },
    {
        "company_name": "Alza.cz a.s.",
        "email": "b2b@alza.cz",
        "phone": "+420 225 340 111",
        "ico": "27082440",
        "dic": "CZ27082440",
        "address_street": "Jankovcova 1522/53",
        "address_city": "Praha 7",
        "address_zip": "17000",
        "address_country": "Česká republika",
        "website": "https://www.alza.cz",
        "type": ContactType.COMPANY,
        "tags": ["e-commerce", "enterprise", "tech"],
    },
    {
        "company_name": "Škoda Auto a.s.",
        "email": "fleetsales@skoda-auto.cz",
        "phone": "+420 326 811 111",
        "ico": "00177041",
        "dic": "CZ00177041",
        "address_street": "tř. Václava Klementa 869",
        "address_city": "Mladá Boleslav",
        "address_zip": "29301",
        "address_country": "Česká republika",
        "website": "https://www.skoda-auto.cz",
        "type": ContactType.COMPANY,
        "tags": ["automotive", "enterprise", "vip"],
    },
    {
        "company_name": "Mall Group a.s.",
        "email": "marketplace@mallgroup.com",
        "phone": "+420 234 212 111",
        "ico": "02165547",
        "dic": "CZ02165547",
        "address_street": "Vyskočilova 1481/4",
        "address_city": "Praha 4",
        "address_zip": "14000",
        "address_country": "Česká republika",
        "website": "https://www.mall.cz",
        "type": ContactType.COMPANY,
        "tags": ["e-commerce", "marketplace"],
    },
    {
        "company_name": "O2 Czech Republic a.s.",
        "email": "business@o2.cz",
        "phone": "+420 800 020 202",
        "ico": "60193336",
        "dic": "CZ60193336",
        "address_street": "Za Brumlovkou 266/2",
        "address_city": "Praha 4",
        "address_zip": "14022",
        "address_country": "Česká republika",
        "website": "https://www.o2.cz",
        "type": ContactType.COMPANY,
        "tags": ["telekomunikace", "enterprise"],
    },
    {
        "company_name": "Datart International a.s.",
        "email": "obchod@datart.cz",
        "phone": "+420 841 111 225",
        "ico": "61501838",
        "dic": "CZ61501838",
        "address_street": "Sokolovská 192/79",
        "address_city": "Praha 8",
        "address_zip": "18600",
        "address_country": "Česká republika",
        "website": "https://www.datart.cz",
        "type": ContactType.COMPANY,
        "tags": ["retail", "elektronika"],
    },
    {
        "company_name": "Česká spořitelna, a.s.",
        "email": "korporatni@csas.cz",
        "phone": "+420 800 207 207",
        "ico": "45244782",
        "dic": "CZ45244782",
        "address_street": "Olbrachtova 1929/62",
        "address_city": "Praha 4",
        "address_zip": "14000",
        "address_country": "Česká republika",
        "website": "https://www.csas.cz",
        "type": ContactType.COMPANY,
        "tags": ["finance", "banka", "enterprise"],
    },
]

CUSTOMERS_PERSONS = [
    {
        "first_name": "Tomáš",
        "last_name": "Čupr",
        "email": "tomas.cupr@rohlik.cz",
        "phone": "+420 777 600 700",
        "company_index": 0,
        "type": ContactType.PERSON,
        "tags": ["founder", "decision-maker", "vip"],
    },
    {
        "first_name": "Jan",
        "last_name": "Juchelka",
        "email": "jan.juchelka@kb.cz",
        "phone": "+420 777 111 055",
        "company_index": 1,
        "type": ContactType.PERSON,
        "tags": ["decision-maker", "CEO"],
    },
    {
        "first_name": "Ondřej",
        "last_name": "Fryc",
        "email": "ondrej.fryc@alza.cz",
        "phone": "+420 777 340 111",
        "company_index": 2,
        "type": ContactType.PERSON,
        "tags": ["founder", "decision-maker"],
    },
    {
        "first_name": "Klaus",
        "last_name": "Zellmer",
        "email": "k.zellmer@skoda-auto.cz",
        "phone": "+420 777 811 111",
        "company_index": 3,
        "type": ContactType.PERSON,
        "tags": ["CEO", "decision-maker", "vip"],
    },
    {
        "first_name": "Daniel",
        "last_name": "Křetínský",
        "email": "d.kretinsky@mallgroup.com",
        "phone": "+420 777 212 111",
        "company_index": 4,
        "type": ContactType.PERSON,
        "tags": ["investor", "decision-maker"],
    },
    {
        "first_name": "Markéta",
        "last_name": "Šichtařová",
        "email": "marketa.sichtarova@o2.cz",
        "phone": "+420 777 020 202",
        "company_index": 5,
        "type": ContactType.PERSON,
        "tags": ["obchod", "kontakt"],
    },
    {
        "first_name": "Petr",
        "last_name": "Novák",
        "email": "petr.novak@datart.cz",
        "phone": "+420 777 111 225",
        "company_index": 6,
        "type": ContactType.PERSON,
        "tags": ["obchod"],
    },
    {
        "first_name": "Jiří",
        "last_name": "Škorvaga",
        "email": "jiri.skorvaga@csas.cz",
        "phone": "+420 777 207 207",
        "company_index": 7,
        "type": ContactType.PERSON,
        "tags": ["IT", "decision-maker"],
    },
]

# Each lead: title, status, source, value, currency, company_index, contact_person_index,
#            category_slug, stage_order, notes
LEADS = [
    {
        "title": "Implementace CRM systému – Rohlík.cz",
        "status": RecordStatus.NEGOTIATION,
        "source": RecordSource.REFERRAL,
        "value": Decimal("185000.00"),
        "currency": "CZK",
        "company_index": 0,
        "contact_person_index": 0,
        "category_slug": "prileziosti",
        "stage_order": 3,
        "notes": "Zákazník vyžaduje napojení na interní ERP systém. Klíčový deal Q3.",
    },
    {
        "title": "Digitální transformace pobočkové sítě – KB",
        "status": RecordStatus.PROPOSAL,
        "source": RecordSource.COLD_CALL,
        "value": Decimal("420000.00"),
        "currency": "CZK",
        "company_index": 1,
        "contact_person_index": 1,
        "category_slug": "prileziosti",
        "stage_order": 2,
        "notes": "Pilotní pobočka Praha Smíchov. RFP termín 15.8.",
    },
    {
        "title": "Redesign B2B portálu – Alza.cz",
        "status": RecordStatus.WON,
        "source": RecordSource.WEB,
        "value": Decimal("95000.00"),
        "currency": "CZK",
        "company_index": 2,
        "contact_person_index": 2,
        "category_slug": "prileziosti",
        "stage_order": 4,
        "notes": "Smlouva podepsána. Zahájení 1.7.",
    },
    {
        "title": "Analytika prodeje flotily – Škoda Auto",
        "status": RecordStatus.NEW,
        "source": RecordSource.REFERRAL,
        "value": Decimal("62000.00"),
        "currency": "EUR",
        "company_index": 3,
        "contact_person_index": 3,
        "category_slug": "prileziosti",
        "stage_order": 0,
        "notes": "Prvotní kontakt přes partnera Deloitte.",
    },
    {
        "title": "Integrace marketplace API – Mall Group",
        "status": RecordStatus.CONTACTED,
        "source": RecordSource.EMAIL,
        "value": Decimal("38000.00"),
        "currency": "CZK",
        "company_index": 4,
        "contact_person_index": 4,
        "category_slug": "prileziosti",
        "stage_order": 1,
        "notes": "Zájem o real-time synchronizaci katalogů.",
    },
    {
        "title": "Migrace infrastruktury do cloudu – O2",
        "status": RecordStatus.PROPOSAL,
        "source": RecordSource.SOCIAL,
        "value": Decimal("750000.00"),
        "currency": "CZK",
        "company_index": 5,
        "contact_person_index": 5,
        "category_slug": "prileziosti",
        "stage_order": 2,
        "notes": "Azure vs. AWS porovnání probíhá. Rozhodnutí do konce kvartálu.",
    },
    {
        "title": "Záruční servis a podpora – Datart",
        "status": RecordStatus.WON,
        "source": RecordSource.REFERRAL,
        "value": Decimal("28000.00"),
        "currency": "CZK",
        "company_index": 6,
        "contact_person_index": 6,
        "category_slug": "sprava",
        "stage_order": 0,
        "notes": "Roční SLA smlouva obnovena. Platná do 31.12.",
    },
    {
        "title": "Bezpečnostní audit IS – Česká spořitelna",
        "status": RecordStatus.NEGOTIATION,
        "source": RecordSource.COLD_CALL,
        "value": Decimal("120000.00"),
        "currency": "CZK",
        "company_index": 7,
        "contact_person_index": 7,
        "category_slug": "prileziosti",
        "stage_order": 3,
        "notes": "Penetrační testy + compliance report. GDPR požadavek.",
    },
    {
        "title": "Realizace e-shopu – Rohlík.cz (fáze 2)",
        "status": RecordStatus.NEW,
        "source": RecordSource.REFERRAL,
        "value": Decimal("210000.00"),
        "currency": "CZK",
        "company_index": 0,
        "contact_person_index": 0,
        "category_slug": "realizace",
        "stage_order": 1,
        "notes": "Navázání na fázi 1 – nová mobilní aplikace pro řidiče.",
    },
    {
        "title": "Podpora a monitoring – KB produkce",
        "status": RecordStatus.WON,
        "source": RecordSource.EMAIL,
        "value": Decimal("36000.00"),
        "currency": "CZK",
        "company_index": 1,
        "contact_person_index": 1,
        "category_slug": "sprava",
        "stage_order": 1,
        "notes": "24/7 monitoring, SLA 99,9 %. Obnovení na rok.",
    },
]

ACTIVITIES_BY_LEAD: dict[int, list[tuple[str, ActivityType]]] = {
    0: [
        ("Úvodní schůzka s Tomášem Čuprem – představení LeadLab platformy. Zájem o enterprise tarif.", ActivityType.MEETING),
        ("Zasláno demo prostředí a přístupové údaje pro testování.", ActivityType.EMAIL_OUT),
        ("Tomáš Čupr odpověděl – chce napojení na SAP modul. Domluvena technická schůzka.", ActivityType.EMAIL_IN),
        ("Technická schůzka s IT týmem – diskuze API integrace a datové struktury.", ActivityType.CALL),
        ("Odeslána detailní cenová nabídka a harmonogram implementace.", ActivityType.EMAIL_OUT),
    ],
    1: [
        ("Studený telefonát – zájem o digitalizaci poboček. Poslán info materiál.", ActivityType.CALL),
        ("Odeslán whitepaper o digitální transformaci v bankovnictví.", ActivityType.EMAIL_OUT),
        ("Jan Juchelka potvrdil účast na produktovém webináři.", ActivityType.EMAIL_IN),
        ("Webinář proběhl – 8 účastníků z KB. Zájem o pilotní nasazení.", ActivityType.MEETING),
        ("Zaslána nabídka pilotního projektu na pobočku Praha Smíchov.", ActivityType.EMAIL_OUT),
    ],
    2: [
        ("Poptávka přišla přes web. Zákazník chce kompletní redesign B2B portálu.", ActivityType.EMAIL_IN),
        ("Úvodní hovor – upřesnění rozsahu, timeline a rozpočtu.", ActivityType.CALL),
        ("Odeslány ukázky předchozích projektů a case studies.", ActivityType.EMAIL_OUT),
        ("Ondřej Fryc podepsal smlouvu. Zahájení projektu 1.7.", ActivityType.EMAIL_IN),
    ],
    3: [
        ("Prvotní kontakt přes partnera Deloitte. Nastíněno řešení pro flotilové CRM.", ActivityType.CALL),
        ("Zasláno úvodní představení produktu v angličtině.", ActivityType.EMAIL_OUT),
    ],
    4: [
        ("E-mail od Daniela Křetínského – zájem o marketplace API integraci.", ActivityType.EMAIL_IN),
        ("Odeslána technická dokumentace API endpointů.", ActivityType.EMAIL_OUT),
    ],
    5: [
        ("LinkedIn zpráva – O2 hledá partnera pro cloudovou migraci.", ActivityType.EMAIL_IN),
        ("Technická prezentace Azure řešení – záznam schůzky.", ActivityType.MEETING),
        ("Markéta Šichtařová zaslala interní schválení pro zaslání nabídky.", ActivityType.EMAIL_IN),
        ("Odeslána komplexní nabídka včetně SLA a migračního plánu.", ActivityType.EMAIL_OUT),
    ],
    6: [
        ("Zákazník žádá o obnovení SLA smlouvy. Podmínky bez změny.", ActivityType.EMAIL_IN),
        ("Odesláno potvrzení obnovení a faktura na roční poplatek.", ActivityType.EMAIL_OUT),
        ("Petr Novák potvrdil zaplacení faktury. Smlouva aktivní.", ActivityType.EMAIL_IN),
    ],
    7: [
        ("Zákazník kontaktoval naše obchodní oddělení s požadavkem na audit.", ActivityType.CALL),
        ("Odeslán dotazník pro pre-audit analýzu.", ActivityType.EMAIL_OUT),
        ("Vyplněný dotazník přijat. Zahájení zpracování nabídky.", ActivityType.EMAIL_IN),
        ("Schůzka s IT bezpečnostním týmem – upřesnění rozsahu penetračních testů.", ActivityType.MEETING),
        ("Odeslána nabídka – pentest + compliance report + GDPR poradenství.", ActivityType.EMAIL_OUT),
    ],
    8: [
        ("Interní kick-off s Tomášem Čuprem pro fázi 2 mobilní aplikace.", ActivityType.MEETING),
        ("Zaslán projektový plán a wireframy.", ActivityType.EMAIL_OUT),
    ],
    9: [
        ("Smlouva o podpoře podepsána. Nastavena monitorovací pravidla.", ActivityType.EMAIL_IN),
        ("Testovací alert proběhl úspěšně. SLA systém funkční.", ActivityType.CALL),
    ],
}

# (title, lead_index, days_offset, priority, status)
TASKS = [
    ("Připravit technický návrh SAP integrace pro Rohlík", 0, 5, TaskPriority.HIGH, TaskStatus.TODO),
    ("Odeslat revidovanou nabídku po technické schůzce – Rohlík", 0, 3, TaskPriority.HIGH, TaskStatus.IN_PROGRESS),
    ("Domluvit pilotní demonstraci na pobočce KB Smíchov", 1, 7, TaskPriority.MEDIUM, TaskStatus.TODO),
    ("Zpracovat výsledky webináře a follow-up e-maily – KB", 1, 2, TaskPriority.LOW, TaskStatus.TODO),
    ("Připravit projektový plán fáze 2 – Rohlík mobilní app", 8, 10, TaskPriority.HIGH, TaskStatus.TODO),
    ("Nastavit monitoring prostředí – KB produkce", 9, 1, TaskPriority.MEDIUM, TaskStatus.IN_PROGRESS),
    ("Připravit pentest report – Česká spořitelna", 7, 14, TaskPriority.HIGH, TaskStatus.TODO),
    ("Odeslat finální smlouvu a harmonogram – Alza.cz", 2, 1, TaskPriority.LOW, TaskStatus.DONE),
    ("Sjednat schůzku s technickým týmem – Škoda Auto", 3, 6, TaskPriority.MEDIUM, TaskStatus.TODO),
    ("Zpracovat odpovědi z dotazníku pre-auditu – ČS", 7, 3, TaskPriority.HIGH, TaskStatus.IN_PROGRESS),
    ("Aktualizovat CRM záznamy po webináři – KB", 1, 1, TaskPriority.LOW, TaskStatus.TODO),
    ("Připravit API dokumentaci pro Mall Group", 4, 4, TaskPriority.MEDIUM, TaskStatus.TODO),
]

PROJECTS = [
    "Q3 2026 – Obchodní Plán",
    "Klíčoví Zákazníci Enterprise",
    "Předplatné a Retence",
    "Cloudové Migrace",
    "Bezpečnostní Audity",
    "E-commerce Projekty",
]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Populate the database with a demo workspace, contacts, leads, "
        "pipeline categories, activities, and tasks for evaluation and "
        "development purposes."
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

        with transaction.atomic():
            self._load(email, password, firm_name, superadmin)

    def _load(self, email: str, password: str, firm_name: str, superadmin: bool) -> None:
        # ---- owner user ----
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": "Demo",
                "last_name": "Superadmin" if superadmin else "User",
                "is_active": True,
                "is_staff": superadmin,
                "is_superuser": superadmin,
            },
        )
        if user_created:
            user.set_password(password)
            user.save()
            role_label = "superadmin" if superadmin else "user"
            self.stdout.write(self.style.SUCCESS(
                f"Vytvořen uživatel ({role_label}): {email}  heslo: {password}"
            ))
        else:
            user.set_password(password)
            user.is_staff = superadmin
            user.is_superuser = superadmin
            user.save()
            self.stdout.write(f"Existující uživatel upraven: {email}")

        # ---- firm ----
        firm, firm_created = Firm.objects.get_or_create(name=firm_name)
        if firm_created:
            self.stdout.write(self.style.SUCCESS(f"Vytvořena firma: {firm_name}"))
        else:
            self.stdout.write(f"Použita existující firma: {firm_name}")

        Membership.objects.get_or_create(
            user=user,
            firm=firm,
            defaults={"role": MembershipRole.OWNER},
        )

        # ---- pipeline categories ----
        categories_by_slug: dict[str, Category] = {}
        stages_by_slug: dict[str, dict[int, Stage]] = {}
        for cat_def in PIPELINE_CATEGORIES:
            stage_defs = cat_def["stages"]
            field_defs = cat_def["fields"]
            slug = cat_def["slug"]

            category, cat_created = Category.objects.get_or_create(
                firm=firm,
                slug=slug,
                defaults={
                    "name": cat_def["name"],
                    "icon": cat_def["icon"],
                    "color": cat_def["color"],
                    "order": cat_def["order"],
                },
            )
            categories_by_slug[slug] = category
            stages_by_slug[slug] = {}
            if cat_created:
                self.stdout.write(f" + Kategorie: {cat_def['name']}")

            for stage_def in stage_defs:
                stage, _ = Stage.objects.get_or_create(
                    category=category,
                    order=stage_def["order"],
                    defaults={
                        "name": stage_def["name"],
                        "label": stage_def.get("label", stage_def["name"]),
                        "color": stage_def.get("color", ""),
                        "is_terminal": stage_def.get("is_terminal", False),
                        "is_won": stage_def.get("is_won", False),
                    },
                )
                stages_by_slug[slug][stage_def["order"]] = stage

            for field_def in field_defs:
                CategoryField.objects.get_or_create(
                    category=category,
                    field_key=field_def["field_key"],
                    defaults={
                        "is_visible": field_def.get("is_visible", True),
                        "is_required": field_def.get("is_required", False),
                        "order": field_def.get("order", 0),
                    },
                )

        # ---- companies ----
        companies: list[Customer] = []
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
                self.stdout.write(f" + Firma: {company.company_name}")

        # ---- persons ----
        persons: list[Customer] = []
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
                self.stdout.write(f" + Kontakt: {person.first_name} {person.last_name}")

        # ---- leads ----
        leads: list[PipelineRecord] = []
        for data in LEADS:
            company = companies[data["company_index"]]
            contact_person = persons[data["contact_person_index"]]
            cat_slug = data.get("category_slug", "prileziosti")
            stage_order = data.get("stage_order", 0)
            category = categories_by_slug.get(cat_slug)
            stage = stages_by_slug.get(cat_slug, {}).get(stage_order)

            lead, created = PipelineRecord.objects.get_or_create(
                firm=firm,
                title=data["title"],
                defaults={
                    "status": data["status"],
                    "source": data["source"],
                    "value": data["value"],
                    "currency": data["currency"],
                    "company": company,
                    "contact_person": contact_person,
                    "assigned_to": user,
                    "category": category,
                    "current_stage": stage,
                    "notes": data.get("notes", ""),
                },
            )
            leads.append(lead)
            if created:
                self.stdout.write(f" + Záznam: {lead.title}")

        # ---- activities ----
        for lead_index, activity_list in ACTIVITIES_BY_LEAD.items():
            if lead_index >= len(leads):
                continue
            target_lead = leads[lead_index]
            if Activity.objects.filter(record=target_lead).exists():
                continue
            for body, atype in activity_list:
                Activity.objects.create(
                    record=target_lead,
                    user=user,
                    type=atype,
                    content_text=body,
                )
            self.stdout.write(
                f" + {len(activity_list)} aktivit na '{target_lead.title}'"
            )

        # ---- projects ----
        for project_name in PROJECTS:
            project, created = Project.objects.get_or_create(firm=firm, name=project_name)
            if created:
                self.stdout.write(f" + Projekt: {project_name}")

        # ---- tasks ----
        now = timezone.now()
        for title, lead_index, days_offset, priority, status in TASKS:
            if lead_index >= len(leads):
                continue
            target_lead = leads[lead_index]
            task, created = Task.objects.get_or_create(
                firm=firm,
                title=title,
                record=target_lead,
                defaults={
                    "assigned_to": user,
                    "due_date": now + timedelta(days=days_offset),
                    "priority": priority,
                    "status": status,
                    "is_completed": status == TaskStatus.DONE,
                },
            )
            if created:
                self.stdout.write(f" + Úkol: {title}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDemonstační data úspěšně načtena!"
            f"\n  Firmy (kontakty): {len(companies)}"
            f"\n  Osoby (kontakty): {len(persons)}"
            f"\n  Pipeline záznamy: {len(leads)}"
            f"\n  Přihlašovací e-mail: {email}"
            f"\n  Heslo: {password}"
        ))
