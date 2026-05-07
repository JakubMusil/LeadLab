"""
Management command: load_demo_data

Creates a self-contained demo workspace with realistic Czech sample data so that
evaluators and developers can explore LeadLab without having to enter data
manually.

The fixture covers a wide range of features so the application can be tested
meaningfully out of the box:

* multiple team members (Owner / Admin / Members)
* ~25 companies (CZ, SK, PL, DE) and ~35 person contacts (incl. standalone)
* 50+ pipeline records spread across all categories, stages, sources,
  currencies (CZK, EUR, USD) and historical/future created_at dates
* a rich activity timeline (email, call, meeting, sms, whatsapp, file,
  link, payment, ai summary, …) distributed over weeks and months
* tasks of various kinds (generic, call, meeting, event, email-followup),
  priorities and statuses, with watchers and Streamline TODO/sub-task lists
* proposals (draft / sent / viewed / accepted / rejected / expired) with
  multiple line items, plus reusable proposal templates and a firm-wide
  catalog of pre-defined items
* ERP demo data: revenue items, expense items, time entries (billable +
  non-billable)
* per-record milestones (Checkpoints), saved views, record scoring rules
  and inbox notifications

Usage:
    python manage.py load_demo_data [--email <owner-email>] [--password <password>]

If the email already exists the command attaches the demo workspace to that
account instead of creating a new user. Running the command a second time for
the same owner email is safe — it will skip objects that already exist.
"""

from __future__ import annotations

import random
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
    Checkpoint,
    Customer,
    ContactType,
    ExpenseItem,
    ExpenseItemRecurrence,
    FirmProposalItem,
    Notification,
    PipelineRecord,
    Proposal,
    ProposalItem,
    ProposalStatus,
    ProposalTemplate,
    ProposalTemplateItem,
    RecordScoringRule,
    RecordSource,
    RecordStatus,
    RevenueItem,
    Project,
    SavedView,
    Stage,
    StreamlineItem,
    StreamlineItemKind,
    Task,
    TaskKind,
    TaskPriority,
    TaskStatus,
    TimeEntry,
)
from firms.models import Firm, Membership, InvitationRole

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

# Each record: title, status, source, value, currency, company_index, contact_person_index,
#              category_slug, stage_order, notes
RECORDS = [
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

ACTIVITIES_BY_RECORD: dict[int, list[tuple[str, ActivityType]]] = {
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

# (title, record_index, days_offset, priority, status)
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

# Extended tasks: (title, record_index, days_offset, priority, status, kind,
#                  is_pinned, is_archived, estimated_minutes)
EXTENDED_TASKS = [
    # Calendar-bound calls / meetings
    ("Kvalifikační hovor – ČEZ AI projekt", 10, 2, TaskPriority.HIGH, TaskStatus.TODO, TaskKind.CALL, True, False, 30),
    ("Schůzka s decision makerem – Avast", 12, 4, TaskPriority.HIGH, TaskStatus.TODO, TaskKind.MEETING, False, False, 60),
    ("Demo Heureka – nové skóre", 18, 7, TaskPriority.HIGH, TaskStatus.TODO, TaskKind.MEETING, True, False, 90),
    ("On-site instalace WMS – den 1", 20, -3, TaskPriority.CRITICAL, TaskStatus.DONE, TaskKind.EVENT, False, True, 480),
    ("Quarterly review – KB SLA", 44, 30, TaskPriority.MEDIUM, TaskStatus.TODO, TaskKind.MEETING, False, False, 60),
    # Email follow-ups
    ("Follow-up nabídka – ČSOB", 22, 1, TaskPriority.MEDIUM, TaskStatus.TODO, TaskKind.EMAIL_FOLLOWUP, False, False, 15),
    ("Follow-up – Slovak Telekom rozhodnutí", 23, 2, TaskPriority.MEDIUM, TaskStatus.TODO, TaskKind.EMAIL_FOLLOWUP, False, False, 15),
    ("Follow-up – ÚNMZ tendr", 27, 5, TaskPriority.LOW, TaskStatus.TODO, TaskKind.EMAIL_FOLLOWUP, False, False, 10),
    # Generic to-dos
    ("Vypracovat ROI kalkulaci pro ČEZ", 10, 3, TaskPriority.HIGH, TaskStatus.IN_PROGRESS, TaskKind.GENERIC, False, False, 240),
    ("Konsolidace zpětné vazby – Notino", 30, 6, TaskPriority.MEDIUM, TaskStatus.TODO, TaskKind.GENERIC, False, False, 120),
    ("Příprava case study – Productboard win", 32, -2, TaskPriority.LOW, TaskStatus.DONE, TaskKind.GENERIC, False, False, 180),
    ("Aktualizace katalogu cenových položek", None, 5, TaskPriority.LOW, TaskStatus.TODO, TaskKind.GENERIC, False, False, 90),
    ("Měsíční pipeline review", None, 7, TaskPriority.MEDIUM, TaskStatus.TODO, TaskKind.MEETING, True, False, 90),
    # Blocked + cancelled examples
    ("Příprava SOW – PACS FN Brno", 28, 14, TaskPriority.HIGH, TaskStatus.BLOCKED, TaskKind.GENERIC, False, False, 480),
    ("Návrh marketingu Heureka (zrušeno)", 19, -10, TaskPriority.LOW, TaskStatus.CANCELLED, TaskKind.GENERIC, False, True, 60),
    # Older completed
    ("Závěrečné předání projektu – Alza B2B", 2, -3, TaskPriority.HIGH, TaskStatus.DONE, TaskKind.GENERIC, False, False, 240),
    ("Akceptační schůzka – Kofola WMS milestone 1", 20, -25, TaskPriority.HIGH, TaskStatus.DONE, TaskKind.MEETING, False, True, 120),
]

# Streamline TODOs / sub-tasks per (extended) task index.
# Index refers to position in EXTENDED_TASKS (0-based).
STREAMLINE_ITEMS_DATA: dict[int, list[tuple[StreamlineItemKind, str, bool]]] = {
    0: [
        (StreamlineItemKind.TODO, "Připravit kvalifikační otázky", True),
        (StreamlineItemKind.TODO, "Ověřit dostupný rozpočet Q4", False),
        (StreamlineItemKind.TODO, "Naplánovat technickou schůzku", False),
    ],
    1: [
        (StreamlineItemKind.SUBTASK, "Připravit prezentaci (10 slidů)", True),
        (StreamlineItemKind.SUBTASK, "Sestavit demo data pro Avast", False),
        (StreamlineItemKind.TODO, "Odeslat agendu s předstihem", False),
    ],
    2: [
        (StreamlineItemKind.SUBTASK, "Příprava live demo prostředí", False),
        (StreamlineItemKind.SUBTASK, "Sběr otázek z minulé schůzky", True),
    ],
    8: [
        (StreamlineItemKind.TODO, "Zpracovat assumptions", True),
        (StreamlineItemKind.TODO, "Spočítat NPV", False),
        (StreamlineItemKind.TODO, "Připravit citlivostní analýzu", False),
        (StreamlineItemKind.TODO, "Zaslat draft k internímu review", False),
    ],
    13: [
        (StreamlineItemKind.SUBTASK, "Vyžádat detailní zadání tendru", True),
        (StreamlineItemKind.SUBTASK, "Konsolidovat technické požadavky", False),
        (StreamlineItemKind.SUBTASK, "Sestavit cenový rozpočet", False),
    ],
}

# Notifications for the demo user (event, payload, days_ago, is_read)
NOTIFICATIONS_DATA = [
    ("record.created", {"title": "AI doporučovací systém – ČEZ"}, 1, False),
    ("activity.created", {"type": "email_in", "preview": "Klient potvrdil příjem dokumentace…"}, 1, False),
    ("task.assigned", {"title": "Kvalifikační hovor – ČEZ AI projekt"}, 2, True),
    ("proposal.viewed", {"proposal": "Pilot KB Smíchov – nabídka", "viewer": "Jan Juchelka"}, 3, True),
    ("record.status_changed", {"title": "Implementace WMS – Kofola Krnov", "from": "negotiation", "to": "won"}, 4, True),
    ("task.completed", {"title": "Závěrečné předání projektu – Alza B2B"}, 5, True),
    ("payment.received", {"amount": "47500.00", "currency": "CZK", "record": "Redesign B2B portálu – Alza.cz"}, 6, True),
    ("invitation.sent", {"email": "anna.kovarova@leadlab.io"}, 14, True),
]

PROJECTS = [
    "Q3 2026 – Obchodní Plán",
    "Klíčoví Zákazníci Enterprise",
    "Předplatné a Retence",
    "Cloudové Migrace",
    "Bezpečnostní Audity",
    "E-commerce Projekty",
    "Veřejný Sektor",
    "Mezinárodní Expanze",
    "Strategické Partnerství",
]


# ---------------------------------------------------------------------------
# Extended fixtures (Phase 2 – wide coverage of features)
# ---------------------------------------------------------------------------

# Additional team members so workspaces have multiple users for permission /
# assignment / team scenarios.  Each tuple: (email, first, last, role).
TEAM_MEMBERS = [
    ("anna.kovarova@leadlab.io", "Anna", "Kovářová", InvitationRole.ADMIN),
    ("petr.svoboda@leadlab.io", "Petr", "Svoboda", InvitationRole.MEMBER),
    ("lucie.dvorakova@leadlab.io", "Lucie", "Dvořáková", InvitationRole.MEMBER),
    ("martin.horak@leadlab.io", "Martin", "Horák", InvitationRole.MEMBER),
    ("eva.prochazkova@leadlab.io", "Eva", "Procházková", InvitationRole.MEMBER),
]

# Additional companies (continuing index 8+) covering more industries and
# countries to make filtering / search / locale handling testable.
MORE_COMPANIES = [
    {
        "company_name": "ČEZ, a.s.",
        "email": "obchod@cez.cz",
        "phone": "+420 211 042 111",
        "ico": "45274649",
        "dic": "CZ45274649",
        "address_street": "Duhová 1444/2",
        "address_city": "Praha 4",
        "address_zip": "14000",
        "address_country": "Česká republika",
        "website": "https://www.cez.cz",
        "type": ContactType.COMPANY,
        "tags": ["energetika", "enterprise", "vip"],
    },
    {
        "company_name": "Avast Software s.r.o.",
        "email": "partners@avast.com",
        "phone": "+420 274 005 666",
        "ico": "02176475",
        "dic": "CZ02176475",
        "address_street": "Pikrtova 1737/1A",
        "address_city": "Praha 4",
        "address_zip": "14000",
        "address_country": "Česká republika",
        "website": "https://www.avast.com",
        "type": ContactType.COMPANY,
        "tags": ["software", "kybernetická-bezpečnost", "tech"],
    },
    {
        "company_name": "Seznam.cz, a.s.",
        "email": "obchod@firma.seznam.cz",
        "phone": "+420 234 694 333",
        "ico": "26168685",
        "dic": "CZ26168685",
        "address_street": "Radlická 3294/10",
        "address_city": "Praha 5",
        "address_zip": "15000",
        "address_country": "Česká republika",
        "website": "https://www.seznam.cz",
        "type": ContactType.COMPANY,
        "tags": ["media", "tech", "enterprise"],
    },
    {
        "company_name": "Zásilkovna s.r.o.",
        "email": "obchod@zasilkovna.cz",
        "phone": "+420 216 216 216",
        "ico": "28408306",
        "dic": "CZ28408306",
        "address_street": "Lihovarská 1060/12",
        "address_city": "Praha 9",
        "address_zip": "19000",
        "address_country": "Česká republika",
        "website": "https://www.zasilkovna.cz",
        "type": ContactType.COMPANY,
        "tags": ["logistika", "e-commerce"],
    },
    {
        "company_name": "Heureka Group a.s.",
        "email": "partneri@heureka.cz",
        "phone": "+420 222 510 510",
        "ico": "07822774",
        "dic": "CZ07822774",
        "address_street": "Karolinská 706/3",
        "address_city": "Praha 8",
        "address_zip": "18600",
        "address_country": "Česká republika",
        "website": "https://www.heureka.cz",
        "type": ContactType.COMPANY,
        "tags": ["e-commerce", "marketplace"],
    },
    {
        "company_name": "Kofola ČeskoSlovensko a.s.",
        "email": "b2b@kofola.cz",
        "phone": "+420 558 651 111",
        "ico": "29217355",
        "dic": "CZ29217355",
        "address_street": "Nad Porubkou 2278/31a",
        "address_city": "Ostrava",
        "address_zip": "70800",
        "address_country": "Česká republika",
        "website": "https://www.kofola.cz",
        "type": ContactType.COMPANY,
        "tags": ["fmcg", "nápoje", "enterprise"],
    },
    {
        "company_name": "Pilsner Urquell a.s.",
        "email": "export@plzensky-prazdroj.cz",
        "phone": "+420 377 061 111",
        "ico": "45357366",
        "dic": "CZ45357366",
        "address_street": "U Prazdroje 7",
        "address_city": "Plzeň",
        "address_zip": "30100",
        "address_country": "Česká republika",
        "website": "https://www.prazdroj.cz",
        "type": ContactType.COMPANY,
        "tags": ["fmcg", "pivovar", "vip"],
    },
    {
        "company_name": "Slovak Telekom, a.s.",
        "email": "biznis@telekom.sk",
        "phone": "+421 2 5878 1111",
        "ico": "35763469",
        "dic": "SK2020273893",
        "address_street": "Bajkalská 28",
        "address_city": "Bratislava",
        "address_zip": "81762",
        "address_country": "Slovensko",
        "website": "https://www.telekom.sk",
        "type": ContactType.COMPANY,
        "tags": ["telekomunikace", "enterprise", "international"],
    },
    {
        "company_name": "Tatra banka, a.s.",
        "email": "korporat@tatrabanka.sk",
        "phone": "+421 2 5919 1000",
        "ico": "00686930",
        "dic": "SK2020408522",
        "address_street": "Hodžovo námestie 3",
        "address_city": "Bratislava",
        "address_zip": "81106",
        "address_country": "Slovensko",
        "website": "https://www.tatrabanka.sk",
        "type": ContactType.COMPANY,
        "tags": ["finance", "banka", "international"],
    },
    {
        "company_name": "Allegro.eu S.A.",
        "email": "partners@allegro.eu",
        "phone": "+48 22 462 81 00",
        "ico": "",
        "dic": "PL5223047119",
        "address_street": "ul. Grunwaldzka 182",
        "address_city": "Poznań",
        "address_zip": "60-166",
        "address_country": "Polsko",
        "website": "https://allegro.eu",
        "type": ContactType.COMPANY,
        "tags": ["e-commerce", "marketplace", "international"],
    },
    {
        "company_name": "SAP Deutschland SE",
        "email": "info.de@sap.com",
        "phone": "+49 6227 7-47474",
        "ico": "",
        "dic": "DE143454214",
        "address_street": "Hasso-Plattner-Ring 7",
        "address_city": "Walldorf",
        "address_zip": "69190",
        "address_country": "Německo",
        "website": "https://www.sap.com",
        "type": ContactType.COMPANY,
        "tags": ["software", "enterprise", "international"],
    },
    {
        "company_name": "ÚNMZ",
        "email": "kontakt@unmz.cz",
        "phone": "+420 221 802 101",
        "ico": "48135267",
        "dic": "CZ48135267",
        "address_street": "Biskupský dvůr 1148/5",
        "address_city": "Praha 1",
        "address_zip": "11000",
        "address_country": "Česká republika",
        "website": "https://www.unmz.cz",
        "type": ContactType.COMPANY,
        "tags": ["veřejný-sektor", "stát"],
    },
    {
        "company_name": "Fakultní nemocnice Brno",
        "email": "obchod@fnbrno.cz",
        "phone": "+420 532 232 111",
        "ico": "65269705",
        "dic": "CZ65269705",
        "address_street": "Jihlavská 20",
        "address_city": "Brno",
        "address_zip": "62500",
        "address_country": "Česká republika",
        "website": "https://www.fnbrno.cz",
        "type": ContactType.COMPANY,
        "tags": ["zdravotnictví", "veřejný-sektor"],
    },
    {
        "company_name": "ČSOB Pojišťovna, a.s.",
        "email": "korporat@csobpoj.cz",
        "phone": "+420 466 100 777",
        "ico": "45534306",
        "dic": "CZ699000761",
        "address_street": "Masarykovo nám. 1458",
        "address_city": "Pardubice",
        "address_zip": "53002",
        "address_country": "Česká republika",
        "website": "https://www.csobpoj.cz",
        "type": ContactType.COMPANY,
        "tags": ["pojištění", "finance", "enterprise"],
    },
    {
        "company_name": "Notino, s.r.o.",
        "email": "obchod@notino.cz",
        "phone": "+420 543 421 911",
        "ico": "27609057",
        "dic": "CZ27609057",
        "address_street": "Londýnské nám. 881/6",
        "address_city": "Brno",
        "address_zip": "63900",
        "address_country": "Česká republika",
        "website": "https://www.notino.cz",
        "type": ContactType.COMPANY,
        "tags": ["e-commerce", "kosmetika"],
    },
    {
        "company_name": "Productboard Inc.",
        "email": "hello@productboard.com",
        "phone": "+420 222 111 222",
        "ico": "29063612",
        "dic": "CZ29063612",
        "address_street": "Karlovo náměstí 290/16",
        "address_city": "Praha 2",
        "address_zip": "12000",
        "address_country": "Česká republika",
        "website": "https://www.productboard.com",
        "type": ContactType.COMPANY,
        "tags": ["software", "saas", "tech"],
    },
    {
        "company_name": "Mews Systems s.r.o.",
        "email": "sales@mews.com",
        "phone": "+420 296 826 870",
        "ico": "29004157",
        "dic": "CZ29004157",
        "address_street": "Nám. I.P. Pavlova 1789/5",
        "address_city": "Praha 2",
        "address_zip": "12000",
        "address_country": "Česká republika",
        "website": "https://www.mews.com",
        "type": ContactType.COMPANY,
        "tags": ["software", "saas", "hospitality"],
    },
    {
        "company_name": "Smart Plumber s.r.o.",
        "email": "info@smartplumber.cz",
        "phone": "+420 777 123 456",
        "ico": "08123456",
        "dic": "CZ08123456",
        "address_street": "Vinohradská 1234/56",
        "address_city": "Praha 2",
        "address_zip": "12000",
        "address_country": "Česká republika",
        "website": "https://www.smartplumber.cz",
        "type": ContactType.COMPANY,
        "tags": ["řemesla", "smb"],
    },
    {
        "company_name": "Café Lounge s.r.o.",
        "email": "info@cafelounge.cz",
        "phone": "+420 257 404 020",
        "ico": "27082441",
        "dic": "CZ27082441",
        "address_street": "Plaská 615/8",
        "address_city": "Praha 5",
        "address_zip": "15000",
        "address_country": "Česká republika",
        "website": "https://www.cafelounge.cz",
        "type": ContactType.COMPANY,
        "tags": ["gastronomie", "smb"],
    },
]

# Additional persons. company_index_offset is *relative* to MORE_COMPANIES so
# we can compute the absolute company index after CUSTOMERS_COMPANIES.
MORE_PERSONS = [
    ("Daniel", "Beneš", "daniel.benes@cez.cz", "+420 723 042 111", 0, ["CFO", "decision-maker"]),
    ("Iva", "Mašková", "iva.maskova@cez.cz", "+420 725 042 222", 0, ["procurement"]),
    ("Ondřej", "Vlček", "ondrej.vlcek@avast.com", "+420 728 005 111", 1, ["CEO", "decision-maker", "vip"]),
    ("Lukáš", "Sedlář", "lukas.sedlar@avast.com", "+420 728 005 122", 1, ["security", "tech"]),
    ("Ivo", "Lukačovič", "ivo.lukacovic@firma.seznam.cz", "+420 731 694 333", 2, ["founder", "vip"]),
    ("Tereza", "Hanušová", "tereza.hanusova@firma.seznam.cz", "+420 731 694 334", 2, ["marketing"]),
    ("Simona", "Kijonková", "simona.kijonkova@zasilkovna.cz", "+420 736 216 216", 3, ["CEO", "vip"]),
    ("Martin", "Kočí", "martin.koci@zasilkovna.cz", "+420 736 216 217", 3, ["operations"]),
    ("Tomáš", "Braverman", "tomas.braverman@heureka.cz", "+420 733 510 510", 4, ["CEO", "decision-maker"]),
    ("Jana", "Vodičková", "jana.vodickova@heureka.cz", "+420 733 510 511", 4, ["finance"]),
    ("Jannis", "Samaras", "jannis.samaras@kofola.cz", "+420 558 651 222", 5, ["CEO", "vip"]),
    ("René", "Musil", "rene.musil@kofola.cz", "+420 558 651 223", 5, ["IT"]),
    ("Tomáš", "Petráček", "tomas.petracek@prazdroj.cz", "+420 377 061 222", 6, ["export", "obchod"]),
    ("Lucia", "Halmová", "lucia.halmova@telekom.sk", "+421 905 781 111", 7, ["B2B", "international"]),
    ("Michal", "Liday", "michal.liday@tatrabanka.sk", "+421 911 919 100", 8, ["CEO", "vip"]),
    ("Roy", "Perticucci", "roy.perticucci@allegro.eu", "+48 601 462 100", 9, ["COO", "international"]),
    ("Christian", "Klein", "c.klein@sap.com", "+49 6227 747 100", 10, ["CEO", "vip", "international"]),
    ("Pavel", "Rakušan", "pavel.rakusan@unmz.cz", "+420 221 802 102", 11, ["veřejný-sektor"]),
    ("Petra", "Drlíčková", "petra.drlickova@fnbrno.cz", "+420 532 232 222", 12, ["IT", "veřejný-sektor"]),
    ("Filip", "Diviš", "filip.divis@csobpoj.cz", "+420 466 100 800", 13, ["procurement", "finance"]),
    ("Michal", "Marek", "michal.marek@notino.cz", "+420 736 421 911", 14, ["CTO", "tech"]),
    ("Hubert", "Palán", "hubert.palan@productboard.com", "+420 776 111 222", 15, ["founder", "vip"]),
    ("Matt", "Welle", "matt.welle@mews.com", "+420 736 826 870", 16, ["CEO", "vip", "international"]),
    ("Karel", "Štika", "karel.stika@smartplumber.cz", "+420 777 123 457", 17, ["majitel", "smb"]),
    ("Eva", "Kratochvílová", "eva.kratochvilova@cafelounge.cz", "+420 731 404 020", 18, ["majitelka", "smb"]),
    # Standalone persons (no company link)
    ("Anna", "Marešová", "anna.maresova@gmail.com", "+420 777 800 800", None, ["freelance", "designer"]),
    ("Jakub", "Polák", "jakub.polak@email.cz", "+420 778 800 801", None, ["consultant"]),
    ("Veronika", "Černá", "veronika.cerna@seznam.cz", "+420 778 800 802", None, ["coach"]),
    ("Robert", "Krejčí", "robert.krejci@protonmail.com", "+420 778 800 803", None, ["investor"]),
    ("Klára", "Bartošová", "klara.bartosova@outlook.cz", "+420 778 800 804", None, ["smb", "agentura"]),
]

# Additional records — start at index 10 (after the original 10).
# Spread across categories, stages, sources, currencies, with deal values
# from a few thousand up to several million for charts/aggregates testing.
# (title, status, source, value, currency, company_index, contact_person_index,
#  category_slug, stage_order, notes, days_ago_created)
MORE_RECORDS = [
    ("AI doporučovací systém – ČEZ", RecordStatus.PROPOSAL, RecordSource.REFERRAL,
     Decimal("980000.00"), "CZK", 8, 8, "prileziosti", 2,
     "Personalizace tarifů pomocí ML. RFP probíhá.", 35),
    ("Customer support automatizace – ČEZ", RecordStatus.NEGOTIATION, RecordSource.EMAIL,
     Decimal("450000.00"), "CZK", 8, 9, "prileziosti", 3,
     "Voicebot + chatbot pro klientský servis.", 21),
    ("Bezpečnostní školení Avast – HR rollout", RecordStatus.WON, RecordSource.WEB,
     Decimal("75000.00"), "CZK", 9, 10, "prileziosti", 4,
     "Roční licence + workshop. Smlouva podepsána.", 60),
    ("Penetrační test mobilní aplikace – Avast", RecordStatus.NEW, RecordSource.REFERRAL,
     Decimal("145000.00"), "CZK", 9, 11, "prileziosti", 0,
     "Předběžné dotazy. Plánováno pro Q4.", 5),
    ("Reklamní kampaň Q4 – Seznam Sklik", RecordStatus.PROPOSAL, RecordSource.COLD_CALL,
     Decimal("220000.00"), "CZK", 10, 12, "prileziosti", 2,
     "Performance kampaň pro klíčového zákazníka.", 14),
    ("Migrace Seznam pošta na nové prostředí", RecordStatus.CONTACTED, RecordSource.EMAIL,
     Decimal("310000.00"), "CZK", 10, 13, "prileziosti", 1,
     "Technická analýza zahájena.", 7),
    ("Optimalizace doručovacích tras – Zásilkovna", RecordStatus.WON, RecordSource.REFERRAL,
     Decimal("520000.00"), "CZK", 11, 14, "realizace", 1,
     "Realizace fáze 1 zahájena. Předpoklad ROI 8 měsíců.", 90),
    ("API integrace s e-shopy – Zásilkovna", RecordStatus.NEGOTIATION, RecordSource.WEB,
     Decimal("180000.00"), "CZK", 11, 15, "prileziosti", 3,
     "Připravuje se finální verze smlouvy.", 18),
    ("Comparison engine refresh – Heureka", RecordStatus.PROPOSAL, RecordSource.REFERRAL,
     Decimal("1200000.00"), "CZK", 12, 16, "prileziosti", 2,
     "Velký projekt redesignu výpočtu skóre.", 28),
    ("Marketing autopilot – Heureka", RecordStatus.LOST, RecordSource.SOCIAL,
     Decimal("90000.00"), "CZK", 12, 17, "prileziosti", 5,
     "Prohráno proti interní implementaci. Ponechat na sledování.", 75),
    ("Implementace WMS – Kofola Krnov", RecordStatus.WON, RecordSource.COLD_CALL,
     Decimal("3200000.00"), "CZK", 13, 18, "realizace", 2,
     "Projekt v termínu. Probíhá akceptační testování.", 120),
    ("BI reporting – Kofola CZ&SK", RecordStatus.NEW, RecordSource.REFERRAL,
     Decimal("280000.00"), "CZK", 13, 19, "prileziosti", 0,
     "Sjednocení reportingu napříč pobočkami.", 3),
    ("Servisní smlouva – Plzeňský Prazdroj", RecordStatus.WON, RecordSource.EMAIL,
     Decimal("48000.00"), "EUR", 14, 20, "sprava", 0,
     "Dlouhodobá podpora export modulu.", 200),
    ("Cross-border CRM rollout – Slovak Telekom", RecordStatus.PROPOSAL, RecordSource.REFERRAL,
     Decimal("65000.00"), "EUR", 15, 21, "prileziosti", 2,
     "Multi-tenant nasazení napříč SK pobočkami.", 22),
    ("Compliance audit – Tatra banka", RecordStatus.NEGOTIATION, RecordSource.COLD_CALL,
     Decimal("85000.00"), "EUR", 16, 22, "prileziosti", 3,
     "DORA + AML readiness review.", 11),
    ("Marketplace API SDK – Allegro", RecordStatus.PROPOSAL, RecordSource.WEB,
     Decimal("120000.00"), "EUR", 17, 23, "prileziosti", 2,
     "Custom SDK pro CZ obchodníky.", 16),
    ("Konektor SAP S/4HANA – pilot", RecordStatus.CONTACTED, RecordSource.REFERRAL,
     Decimal("95000.00"), "EUR", 18, 24, "prileziosti", 1,
     "Společné PoC s lokálním partnerem.", 9),
    ("Digitalizace formulářů – ÚNMZ", RecordStatus.NEW, RecordSource.OTHER,
     Decimal("420000.00"), "CZK", 19, 25, "prileziosti", 0,
     "Veřejná zakázka – sledujeme přes registr.", 2),
    ("PACS modernizace – FN Brno", RecordStatus.PROPOSAL, RecordSource.OTHER,
     Decimal("2500000.00"), "CZK", 20, 26, "prileziosti", 2,
     "Tendr na obnovu zobrazovacího systému.", 40),
    ("Pojistné události – workflow ČSOB", RecordStatus.WON, RecordSource.EMAIL,
     Decimal("390000.00"), "CZK", 21, 27, "realizace", 1,
     "Realizace běží – sprint 4 z 8.", 55),
    ("E-shop personalizace – Notino", RecordStatus.NEGOTIATION, RecordSource.WEB,
     Decimal("680000.00"), "CZK", 22, 28, "prileziosti", 3,
     "A/B test framework + ML doporučení.", 12),
    ("Onboarding journey – Productboard", RecordStatus.WON, RecordSource.REFERRAL,
     Decimal("42000.00"), "USD", 23, 29, "prileziosti", 4,
     "PLG growth hack pro nové uživatele.", 65),
    ("Channel manager rollout – Mews", RecordStatus.PROPOSAL, RecordSource.SOCIAL,
     Decimal("38000.00"), "EUR", 24, 30, "prileziosti", 2,
     "Pilot na 5 hotelech v Praze.", 19),
    ("Webová prezentace – Smart Plumber", RecordStatus.WON, RecordSource.WEB,
     Decimal("38000.00"), "CZK", 25, 31, "prileziosti", 4,
     "Malá zakázka – referenční web pro řemeslníky.", 100),
    ("Rezervační systém – Café Lounge", RecordStatus.WON, RecordSource.SOCIAL,
     Decimal("25000.00"), "CZK", 26, 32, "prileziosti", 4,
     "POS + online rezervace.", 80),
    ("Long-term support – Café Lounge", RecordStatus.NEW, RecordSource.REFERRAL,
     Decimal("18000.00"), "CZK", 26, 32, "sprava", 0,
     "Návazná dlouhodobá podpora.", 8),
    # Records linked to standalone persons (no company)
    ("Coaching platform MVP – Veronika Černá", RecordStatus.CONTACTED, RecordSource.REFERRAL,
     Decimal("120000.00"), "CZK", None, 35, "prileziosti", 1,
     "Vlastní platforma pro online kurzy.", 25),
    ("Investiční portál – Robert Krejčí", RecordStatus.NEW, RecordSource.OTHER,
     Decimal("150000.00"), "CZK", None, 36, "prileziosti", 0,
     "Privátní investor, hledá softwarového partnera.", 4),
    # Lost / canceled / archived – useful for filter testing
    ("CRM evaluation – Datart", RecordStatus.LOST, RecordSource.WEB,
     Decimal("60000.00"), "CZK", 6, 6, "prileziosti", 5,
     "Klient zvolil konkurenci. Zaznamenáno pro reporting.", 110),
    ("Strategická spolupráce – ČS pobočky", RecordStatus.CANCELED, RecordSource.REFERRAL,
     Decimal("0.00"), "CZK", 7, 7, "prileziosti", 5,
     "Projekt zastaven na straně klienta.", 130),
    # More existing-account expansions across categories
    ("Mobilní aplikace pro řidiče – Rohlík (Realizace)", RecordStatus.WON, RecordSource.REFERRAL,
     Decimal("450000.00"), "CZK", 0, 0, "realizace", 2,
     "Předání produkčního prostředí. UX ladění probíhá.", 150),
    ("Long-term Premium SLA – Komerční banka", RecordStatus.WON, RecordSource.EMAIL,
     Decimal("96000.00"), "CZK", 1, 1, "sprava", 1,
     "Premium podpora 24/7. Quarterly review nastaveno.", 220),
    ("E-mail marketing automatizace – Alza", RecordStatus.NEW, RecordSource.WEB,
     Decimal("85000.00"), "CZK", 2, 2, "prileziosti", 0,
     "Návazný projekt po B2B portálu.", 6),
    ("Fleet analytics – Škoda Auto (rozšíření)", RecordStatus.NEGOTIATION, RecordSource.REFERRAL,
     Decimal("110000.00"), "EUR", 3, 3, "prileziosti", 3,
     "Pilot rozšířen o predikci poruch.", 17),
    ("Mall katalog migrace – fáze 2", RecordStatus.PROPOSAL, RecordSource.EMAIL,
     Decimal("95000.00"), "CZK", 4, 4, "prileziosti", 2,
     "Konsolidace dat se Slovenskem.", 13),
    ("O2 IoT pilot – chytré měřáky", RecordStatus.NEW, RecordSource.SOCIAL,
     Decimal("220000.00"), "CZK", 5, 5, "prileziosti", 0,
     "Zájem o 1000 jednotek pro pilotní region.", 1),
    ("Datart loyalty refresh", RecordStatus.PROPOSAL, RecordSource.REFERRAL,
     Decimal("72000.00"), "CZK", 6, 6, "prileziosti", 2,
     "Modernizace věrnostního programu.", 26),
    ("ČS Mobilní bankovnictví – UX audit", RecordStatus.WON, RecordSource.COLD_CALL,
     Decimal("58000.00"), "CZK", 7, 7, "prileziosti", 4,
     "Krátký 4týdenní audit s deliverables.", 70),
    ("ČS InternetBanking – komponentní knihovna", RecordStatus.NEW, RecordSource.REFERRAL,
     Decimal("310000.00"), "CZK", 7, 7, "prileziosti", 0,
     "Návazný projekt po UX auditu.", 2),
    ("KB pravidelný školící program", RecordStatus.WON, RecordSource.EMAIL,
     Decimal("44000.00"), "CZK", 1, 1, "sprava", 0,
     "Roční vzdělávací rámec pro 200 zaměstnanců.", 180),
]

# Activity templates by type for realistic timeline generation across many
# records.  Each entry: (ActivityType, czech body template).
ACTIVITY_BANK: list[tuple[ActivityType, str]] = [
    (ActivityType.COMMENT, "Interní poznámka: zákazník působí dobře připraveně, zkrátit prodejní cyklus."),
    (ActivityType.COMMENT, "Domluveno s týmem priorit – tato příležitost má vysokou váhu."),
    (ActivityType.EMAIL_OUT, "Odeslán follow-up e-mail s odkazem na případové studie."),
    (ActivityType.EMAIL_OUT, "Zaslána aktualizovaná nabídka s upravenými cenami."),
    (ActivityType.EMAIL_IN, "Klient potvrdil příjem dokumentace a slíbil odpověď do týdne."),
    (ActivityType.EMAIL_IN, "Doručena žádost o doplnění technických parametrů."),
    (ActivityType.CALL, "Telefonát – diskuse otevřených otázek, 25 minut."),
    (ActivityType.CALL, "Krátký call s decision-makerem, dohodnut další postup."),
    (ActivityType.MEETING, "Osobní schůzka v sídle klienta – workshop priorit."),
    (ActivityType.MEETING, "Online schůzka přes MS Teams, 60 minut, prezentace řešení."),
    (ActivityType.SMS_OUT, "Odeslána SMS připomínka před zítřejší schůzkou."),
    (ActivityType.SMS_IN, "Klient potvrdil schůzku SMSkou."),
    (ActivityType.WHATSAPP_OUT, "Whatsapp zpráva – zaslán odkaz na sdílený dokument."),
    (ActivityType.WHATSAPP_IN, "Whatsapp odpověď – preferované termíny pro další call."),
    (ActivityType.CHAT, "Krátká chat zpráva v interním kanálu pro koordinaci."),
    (ActivityType.MEETING_SCHEDULED, "Naplánována schůzka v kalendáři pro příští týden."),
    (ActivityType.CALL_SCHEDULED, "Naplánován telefonát na 14:00."),
    (ActivityType.EVENT_SCHEDULED, "Pozvánka na výroční konferenci klienta zařazena."),
    (ActivityType.FILE_UPLOAD, "Nahrán dokument: technická specifikace v2.pdf"),
    (ActivityType.FILE_UPLOAD, "Nahrána prezentace pro tendrovou komisi."),
    (ActivityType.LINK, "Sdílen externí odkaz: srovnání řešení v Gartner kvadrantu."),
    (ActivityType.VOICE_MEMO, "Hlasová poznámka: shrnutí dnešní schůzky."),
    (ActivityType.PAYMENT_RECEIVED, "Přijata platba dle smlouvy – zálohová faktura uhrazena."),
    (ActivityType.INVOICE_SENT, "Odeslána zálohová faktura č. 2026-0145."),
    (ActivityType.SIGNATURE_REQUESTED, "Vyžádán elektronický podpis přes DocuSign."),
    (ActivityType.AI_SUMMARY, "AI shrnutí: zákazník je v rozhodovací fázi, hlavní bariérou je rozpočet Q4."),
    (ActivityType.AI_SUGGESTED_ACTION, "Doporučení: připravit ROI kalkulaci v české koruně do 48 hodin."),
    (ActivityType.SYSTEM_NOTE, "Systémová poznámka: status synchronizován z externího systému."),
    (ActivityType.TIME_LOGGED, "Zalogovány 2 hodiny práce – příprava nabídky."),
    (ActivityType.PINNED, "Tato aktivita byla připnuta k záznamu pro snadný přístup."),
]


PROPOSAL_TEMPLATES_DATA = [
    {
        "name": "Standardní implementace CRM",
        "intro_text": "Vážený zákazníku,\n\nrádi bychom Vám představili nabídku implementace CRM systému LeadLab.",
        "closing_text": "Děkujeme za Vaši důvěru a těšíme se na spolupráci.\n\nS pozdravem,\nTým LeadLab",
        "items": [
            ("Analýza a návrh řešení", Decimal("8"), Decimal("2400"), Decimal("0"), Decimal("21")),
            ("Implementace základního modulu", Decimal("40"), Decimal("2200"), Decimal("0"), Decimal("21")),
            ("Datová migrace", Decimal("16"), Decimal("2400"), Decimal("0"), Decimal("21")),
            ("Školení uživatelů (8 osob)", Decimal("1"), Decimal("18000"), Decimal("0"), Decimal("21")),
            ("Roční podpora SLA", Decimal("12"), Decimal("3500"), Decimal("0"), Decimal("21")),
        ],
    },
    {
        "name": "Quick-start balíček SMB",
        "intro_text": "Děkujeme za zájem. Připravili jsme pro Vás cenově dostupný balíček.",
        "closing_text": "Cena je platná 30 dní od data nabídky.",
        "items": [
            ("Onboarding workshop", Decimal("1"), Decimal("12000"), Decimal("0"), Decimal("21")),
            ("Konfigurace pipeline (1 workspace)", Decimal("1"), Decimal("9000"), Decimal("0"), Decimal("21")),
            ("Šablona faktur a nabídek", Decimal("1"), Decimal("6000"), Decimal("10"), Decimal("21")),
        ],
    },
    {
        "name": "Bezpečnostní audit",
        "intro_text": "Předkládáme nabídku na bezpečnostní audit dle ISO 27001.",
        "closing_text": "Audit zahrnuje závěrečnou zprávu a roadmapu nápravných opatření.",
        "items": [
            ("Vstupní rozhovor + sběr podkladů", Decimal("8"), Decimal("3000"), Decimal("0"), Decimal("21")),
            ("Penetrační test webové aplikace", Decimal("24"), Decimal("3500"), Decimal("0"), Decimal("21")),
            ("Závěrečná zpráva + prezentace", Decimal("8"), Decimal("3000"), Decimal("0"), Decimal("21")),
        ],
    },
]

FIRM_CATALOG_ITEMS = [
    ("Konzultace seniorního architekta (hod.)", Decimal("1"), Decimal("3500"), Decimal("0"), Decimal("21"), "SRV-ARCH-01"),
    ("Vývoj backend (hod.)", Decimal("1"), Decimal("2400"), Decimal("0"), Decimal("21"), "SRV-DEV-BE-01"),
    ("Vývoj frontend (hod.)", Decimal("1"), Decimal("2200"), Decimal("0"), Decimal("21"), "SRV-DEV-FE-01"),
    ("UX/UI návrh (hod.)", Decimal("1"), Decimal("2000"), Decimal("0"), Decimal("21"), "SRV-UX-01"),
    ("DevOps a CI/CD setup", Decimal("1"), Decimal("28000"), Decimal("0"), Decimal("21"), "SRV-OPS-01"),
    ("LeadLab Pro – roční licence (1 uživatel)", Decimal("12"), Decimal("499"), Decimal("0"), Decimal("21"), "LIC-PRO-USR"),
    ("LeadLab Enterprise – roční licence (1 uživatel)", Decimal("12"), Decimal("899"), Decimal("0"), Decimal("21"), "LIC-ENT-USR"),
    ("Datová migrace (paušál)", Decimal("1"), Decimal("45000"), Decimal("5"), Decimal("21"), "SRV-MIG-01"),
    ("Onboarding workshop (1 den)", Decimal("1"), Decimal("18000"), Decimal("0"), Decimal("21"), "SRV-ONB-01"),
    ("Penetrační test (paušál)", Decimal("1"), Decimal("85000"), Decimal("0"), Decimal("21"), "SRV-SEC-PT"),
    ("Mimopracovní zásah (sazba)", Decimal("1"), Decimal("4500"), Decimal("0"), Decimal("21"), "SRV-OOH-01"),
    ("Cestovní náhrady (km)", Decimal("1"), Decimal("12"), Decimal("0"), Decimal("21"), "REIMB-KM"),
]

# Per-record proposals.
# Each entry: (record_index, title, status, currency, days_offset, items)
# items: list of tuples (description, qty, unit_price, discount, vat_rate)
PROPOSALS_DATA = [
    (0, "Nabídka – CRM pro Rohlík.cz", ProposalStatus.SENT, "CZK", -10, [
        ("Implementace základního CRM", Decimal("1"), Decimal("85000"), Decimal("0"), Decimal("21")),
        ("Integrace SAP", Decimal("1"), Decimal("65000"), Decimal("0"), Decimal("21")),
        ("Školení (8 osob)", Decimal("1"), Decimal("18000"), Decimal("0"), Decimal("21")),
        ("Roční podpora", Decimal("12"), Decimal("1500"), Decimal("0"), Decimal("21")),
    ]),
    (1, "Pilot KB Smíchov – nabídka", ProposalStatus.VIEWED, "CZK", -5, [
        ("PoC nasazení – pobočka", Decimal("1"), Decimal("220000"), Decimal("0"), Decimal("21")),
        ("Workshop pro pobočkové týmy", Decimal("3"), Decimal("18000"), Decimal("0"), Decimal("21")),
        ("Reporting + analytics", Decimal("1"), Decimal("75000"), Decimal("5"), Decimal("21")),
    ]),
    (2, "Redesign B2B portálu – Alza", ProposalStatus.ACCEPTED, "CZK", -45, [
        ("UX/UI redesign", Decimal("80"), Decimal("2000"), Decimal("0"), Decimal("21")),
        ("Frontend implementace", Decimal("160"), Decimal("2200"), Decimal("0"), Decimal("21")),
        ("Backend API změny", Decimal("60"), Decimal("2400"), Decimal("0"), Decimal("21")),
    ]),
    (5, "Cloudová migrace O2 – komplexní nabídka", ProposalStatus.SENT, "CZK", -7, [
        ("Discovery & assessment", Decimal("80"), Decimal("3000"), Decimal("0"), Decimal("21")),
        ("Migrace 80 aplikací", Decimal("1"), Decimal("420000"), Decimal("0"), Decimal("21")),
        ("Cutover support 24/7", Decimal("1"), Decimal("180000"), Decimal("0"), Decimal("21")),
    ]),
    (7, "Bezpečnostní audit – Česká spořitelna", ProposalStatus.VIEWED, "CZK", -15, [
        ("Penetrační testy webových aplikací", Decimal("1"), Decimal("85000"), Decimal("0"), Decimal("21")),
        ("Compliance report GDPR", Decimal("1"), Decimal("35000"), Decimal("0"), Decimal("21")),
    ]),
    (10, "AI doporučovací systém – ČEZ – návrh", ProposalStatus.SENT, "CZK", -12, [
        ("Datová příprava + analytika", Decimal("80"), Decimal("3500"), Decimal("0"), Decimal("21")),
        ("Vývoj ML modelu", Decimal("160"), Decimal("3500"), Decimal("0"), Decimal("21")),
        ("MLOps + nasazení", Decimal("80"), Decimal("3500"), Decimal("0"), Decimal("21")),
    ]),
    (12, "Bezpečnostní školení Avast", ProposalStatus.ACCEPTED, "CZK", -55, [
        ("Roční licence – 50 uživatelů", Decimal("50"), Decimal("1200"), Decimal("0"), Decimal("21")),
        ("Workshop pro IT tým", Decimal("1"), Decimal("18000"), Decimal("0"), Decimal("21")),
    ]),
    (16, "Optimalizace doručovacích tras – Zásilkovna", ProposalStatus.ACCEPTED, "CZK", -85, [
        ("Diskovery + datový audit", Decimal("1"), Decimal("85000"), Decimal("0"), Decimal("21")),
        ("Algoritmus + integrace", Decimal("1"), Decimal("385000"), Decimal("0"), Decimal("21")),
        ("Pilotní nasazení (region Praha)", Decimal("1"), Decimal("65000"), Decimal("0"), Decimal("21")),
    ]),
    (18, "Comparison engine refresh – Heureka", ProposalStatus.SENT, "CZK", -25, [
        ("Návrh nového skóre algoritmu", Decimal("1"), Decimal("280000"), Decimal("0"), Decimal("21")),
        ("Implementace + A/B test rámec", Decimal("1"), Decimal("720000"), Decimal("0"), Decimal("21")),
        ("Hand-over a školení", Decimal("1"), Decimal("85000"), Decimal("0"), Decimal("21")),
    ]),
    (19, "Marketing autopilot – Heureka (zamítnuto)", ProposalStatus.REJECTED, "CZK", -70, [
        ("Marketingový dashboard", Decimal("1"), Decimal("60000"), Decimal("0"), Decimal("21")),
        ("Drip kampaně", Decimal("1"), Decimal("30000"), Decimal("0"), Decimal("21")),
    ]),
    (20, "Implementace WMS – Kofola Krnov", ProposalStatus.ACCEPTED, "CZK", -115, [
        ("WMS licence + setup", Decimal("1"), Decimal("1200000"), Decimal("0"), Decimal("21")),
        ("Hardware (čtečky, tiskárny)", Decimal("1"), Decimal("780000"), Decimal("5"), Decimal("21")),
        ("Implementační projekt", Decimal("1"), Decimal("1100000"), Decimal("0"), Decimal("21")),
    ]),
    (24, "Compliance audit – Tatra banka", ProposalStatus.SENT, "EUR", -8, [
        ("DORA readiness assessment", Decimal("1"), Decimal("28000"), Decimal("0"), Decimal("20")),
        ("AML procesní audit", Decimal("1"), Decimal("32000"), Decimal("0"), Decimal("20")),
        ("Závěrečná zpráva + prezentace", Decimal("1"), Decimal("12000"), Decimal("0"), Decimal("20")),
    ]),
    (28, "PACS modernizace – FN Brno (tendr)", ProposalStatus.SENT, "CZK", -30, [
        ("HW + storage", Decimal("1"), Decimal("1100000"), Decimal("0"), Decimal("21")),
        ("Software a integrace", Decimal("1"), Decimal("980000"), Decimal("0"), Decimal("21")),
        ("3 roky podpory", Decimal("36"), Decimal("12000"), Decimal("0"), Decimal("21")),
    ]),
    (30, "E-shop personalizace – Notino", ProposalStatus.DRAFT, "CZK", -2, [
        ("Architektura personalizace", Decimal("1"), Decimal("120000"), Decimal("0"), Decimal("21")),
        ("Vývoj doporučovacího jádra", Decimal("1"), Decimal("420000"), Decimal("0"), Decimal("21")),
        ("A/B test framework", Decimal("1"), Decimal("140000"), Decimal("0"), Decimal("21")),
    ]),
    (44, "Long-term Premium SLA – KB", ProposalStatus.ACCEPTED, "CZK", -200, [
        ("Premium SLA 24/7 (12 měsíců)", Decimal("12"), Decimal("8000"), Decimal("0"), Decimal("21")),
    ]),
    (39, "ČS Mobilní bankovnictví – UX audit (expirovaná verze)", ProposalStatus.EXPIRED, "CZK", -120, [
        ("UX audit + workshop", Decimal("1"), Decimal("48000"), Decimal("0"), Decimal("21")),
    ]),
]

# Revenue items linked to records (won deals etc.)
# (record_index, title, amount, currency, days_ago, recurrence)
REVENUE_ITEMS_DATA = [
    (2, "Záloha 50 % – B2B portál Alza", Decimal("47500.00"), "CZK", 40, ExpenseItemRecurrence.ONCE),
    (2, "Doplatek po předání – B2B portál Alza", Decimal("47500.00"), "CZK", 5, ExpenseItemRecurrence.ONCE),
    (6, "Roční SLA – Datart", Decimal("28000.00"), "CZK", 90, ExpenseItemRecurrence.YEARLY),
    (9, "Měsíční podpora – KB", Decimal("3000.00"), "CZK", 30, ExpenseItemRecurrence.MONTHLY),
    (9, "Měsíční podpora – KB", Decimal("3000.00"), "CZK", 60, ExpenseItemRecurrence.MONTHLY),
    (12, "Bezpečnostní školení Avast – fakturace", Decimal("75000.00"), "CZK", 55, ExpenseItemRecurrence.ONCE),
    (16, "Záloha 30 % – Zásilkovna optimalizace", Decimal("156000.00"), "CZK", 80, ExpenseItemRecurrence.ONCE),
    (20, "Milestone 1 – Kofola WMS", Decimal("1200000.00"), "CZK", 100, ExpenseItemRecurrence.ONCE),
    (20, "Milestone 2 – Kofola WMS", Decimal("1000000.00"), "CZK", 30, ExpenseItemRecurrence.ONCE),
    (22, "Pojistné události workflow – ČSOB", Decimal("195000.00"), "CZK", 50, ExpenseItemRecurrence.ONCE),
    (32, "Productboard onboarding – fakturace", Decimal("42000.00"), "USD", 60, ExpenseItemRecurrence.ONCE),
    (34, "Smart Plumber – web", Decimal("38000.00"), "CZK", 95, ExpenseItemRecurrence.ONCE),
    (35, "Café Lounge – rezervační systém", Decimal("25000.00"), "CZK", 75, ExpenseItemRecurrence.ONCE),
    (41, "Rohlík fáze 2 – záloha", Decimal("210000.00"), "CZK", 145, ExpenseItemRecurrence.ONCE),
    (44, "KB SLA – měsíční", Decimal("8000.00"), "CZK", 20, ExpenseItemRecurrence.MONTHLY),
]

# Expense items
EXPENSE_ITEMS_DATA = [
    (0, "Subdodávka SAP konzultace", Decimal("38000.00"), "CZK", 25, ExpenseItemRecurrence.ONCE),
    (5, "AWS konzultace – PoC", Decimal("15000.00"), "CZK", 12, ExpenseItemRecurrence.ONCE),
    (7, "Externí pentester (subkontrakt)", Decimal("45000.00"), "CZK", 18, ExpenseItemRecurrence.ONCE),
    (None, "Cestovné Praha – Brno (tým)", Decimal("4200.00"), "CZK", 7, ExpenseItemRecurrence.ONCE),
    (None, "Měsíční licence GitHub Enterprise", Decimal("12000.00"), "CZK", 5, ExpenseItemRecurrence.MONTHLY),
    (None, "Měsíční licence Atlassian Cloud", Decimal("9800.00"), "CZK", 5, ExpenseItemRecurrence.MONTHLY),
    (None, "Roční pojištění odpovědnosti", Decimal("38000.00"), "CZK", 200, ExpenseItemRecurrence.YEARLY),
    (10, "Cloud GPU pro trénink ML modelu", Decimal("28500.00"), "CZK", 14, ExpenseItemRecurrence.ONCE),
    (20, "Hardware – čtečky kódů (zálohy)", Decimal("180000.00"), "CZK", 110, ExpenseItemRecurrence.ONCE),
    (24, "Cestovné Bratislava (audit)", Decimal("8500.00"), "EUR", 9, ExpenseItemRecurrence.ONCE),
    (None, "Marketingová kampaň LinkedIn", Decimal("18000.00"), "CZK", 30, ExpenseItemRecurrence.MONTHLY),
    (None, "Konference WebExpo – sponzoring", Decimal("65000.00"), "CZK", 60, ExpenseItemRecurrence.ONCE),
]

# Time entries: (record_index, duration_minutes, description, is_billable, days_ago)
TIME_ENTRIES_DATA = [
    (0, 120, "Příprava SAP integrační analýzy", True, 5),
    (0, 90, "Schůzka s IT týmem Rohlík", True, 4),
    (0, 240, "Návrh datového modelu", True, 3),
    (1, 180, "Příprava webináře KB", True, 12),
    (1, 60, "Follow-up s účastníky", True, 11),
    (2, 480, "Implementace komponentů Alza", True, 30),
    (2, 360, "Code review + QA", True, 28),
    (5, 300, "AWS migration sizing", True, 8),
    (5, 240, "Vyhodnocení nákladového modelu", True, 6),
    (7, 480, "Penetrační testy fáze 1", True, 14),
    (10, 360, "Trénink ML modelu", True, 10),
    (10, 90, "Code review", True, 9),
    (16, 600, "Vývoj algoritmu Zásilkovna", True, 60),
    (20, 720, "On-site instalace WMS Krnov", True, 95),
    (20, 480, "Konfigurace WMS modulů", True, 88),
    (22, 240, "Testování workflow ČSOB", True, 45),
    (32, 180, "Onboarding workshop Productboard", True, 65),
    (34, 240, "Web Smart Plumber – CMS setup", True, 92),
    (None, 60, "Týdenní interní porada", False, 3),
    (None, 30, "Networking call s partnerem", False, 7),
]

# Checkpoints (record_index, name, days_offset, completed, description)
CHECKPOINTS_DATA = [
    (0, "Podpis NDA", -25, True, "Podepsáno oběma stranami."),
    (0, "Technická schůzka SAP", -10, True, "Specifikace integrace dokončena."),
    (0, "Předložení finální nabídky", 3, False, "Termín dle dohody."),
    (0, "Plánovaný kick-off", 21, False, ""),
    (2, "Kick-off projektu Alza", -42, True, ""),
    (2, "Předání designové fáze", -14, True, ""),
    (2, "Go-live B2B portálu", 7, False, "Probíhá UAT."),
    (5, "PoC schválení", -3, True, ""),
    (5, "Pilot start", 14, False, ""),
    (5, "Production cut-over", 90, False, ""),
    (10, "Sběr dat z provozu", -5, True, ""),
    (10, "Vyhodnocení A/B testu", 28, False, ""),
    (16, "Pilot region Praha", -50, True, "ROI v souladu s plánem."),
    (20, "Akceptace WMS modulu", -10, True, ""),
    (20, "Závěrečná akceptace", 30, False, ""),
    (28, "Otevření obálek tendru", 18, False, "Veřejná zakázka."),
]

# Saved views — useful filtering presets
SAVED_VIEWS_DATA = [
    {
        "name": "Hot deals – velké příležitosti",
        "entity": "opportunities",
        "filters": {"status": ["proposal", "negotiation"], "min_value": 200000},
        "sort_by": "value", "sort_dir": "desc",
        "columns": ["title", "company", "status", "value", "assigned_to"],
    },
    {
        "name": "Moje aktivní záznamy",
        "entity": "opportunities",
        "filters": {"assigned_to": "me", "status": ["new", "contacted", "proposal", "negotiation"]},
        "sort_by": "updated_at", "sort_dir": "desc",
        "columns": ["title", "status", "value", "updated_at"],
    },
    {
        "name": "Vyhráno tento kvartál",
        "entity": "opportunities",
        "filters": {"status": ["won"], "won_date_within_days": 90},
        "sort_by": "value", "sort_dir": "desc",
        "columns": ["title", "company", "value", "updated_at"],
    },
    {
        "name": "Slovensko & EU klienti",
        "entity": "directory",
        "filters": {"country": ["Slovensko", "Polsko", "Německo"]},
        "sort_by": "company_name", "sort_dir": "asc",
        "columns": ["company_name", "country", "tags"],
    },
    {
        "name": "VIP kontakty",
        "entity": "directory",
        "filters": {"tags": ["vip"]},
        "sort_by": "last_name", "sort_dir": "asc",
        "columns": ["first_name", "last_name", "email", "tags"],
    },
    {
        "name": "Bez aktivity 14+ dní",
        "entity": "opportunities",
        "filters": {"no_activity_days": 14, "status": ["new", "contacted", "proposal"]},
        "sort_by": "updated_at", "sort_dir": "asc",
        "columns": ["title", "company", "status", "updated_at"],
    },
]

# Record scoring rules: (field, operand, score_delta)
SCORING_RULES_DATA = [
    ("status", "negotiation", 25),
    ("status", "proposal", 15),
    ("status", "contacted", 5),
    ("source", "referral", 10),
    ("source", "cold_call", -5),
    ("value_gte", 500000, 20),
    ("value_gte", 1000000, 15),
    ("last_activity_days_lte", 7, 10),
]





# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Populate the database with a demo workspace, contacts, records, "
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
            defaults={"role": InvitationRole.OWNER},
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

        # ---- companies (core + extended) ----
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
                    "assigned_to": user,
                    "created_by": user,
                },
            )
            companies.append(company)
            if created:
                self.stdout.write(f" + Firma: {company.company_name}")

        for data in MORE_COMPANIES:
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
                    "assigned_to": user,
                    "created_by": user,
                },
            )
            companies.append(company)
            if created:
                self.stdout.write(f" + Firma: {company.company_name}")

        # ---- persons (core + extended) ----
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
                    "assigned_to": user,
                    "created_by": user,
                },
            )
            persons.append(person)
            if created:
                self.stdout.write(f" + Kontakt: {person.first_name} {person.last_name}")

        more_company_offset = len(CUSTOMERS_COMPANIES)
        for first_name, last_name, p_email, phone, rel_company_idx, tags in MORE_PERSONS:
            linked_company = None
            company_name = ""
            if rel_company_idx is not None:
                abs_idx = more_company_offset + rel_company_idx
                if abs_idx < len(companies):
                    linked_company = companies[abs_idx]
                    company_name = linked_company.company_name
            person, created = Customer.objects.get_or_create(
                firm=firm,
                email=p_email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "company": linked_company,
                    "company_name": company_name,
                    "type": ContactType.PERSON,
                    "tags": list(tags),
                    "assigned_to": user,
                    "created_by": user,
                },
            )
            persons.append(person)
            if created:
                self.stdout.write(f" + Kontakt: {person.first_name} {person.last_name}")

        # ---- additional team members ----
        team_users: list = [user]
        for tm_email, tm_first, tm_last, tm_role in TEAM_MEMBERS:
            tm_user, tm_created = User.objects.get_or_create(
                email=tm_email,
                defaults={
                    "first_name": tm_first,
                    "last_name": tm_last,
                    "is_active": True,
                },
            )
            if tm_created:
                tm_user.set_password("Demo1234!")
                tm_user.save()
                self.stdout.write(f" + Uživatel: {tm_email}")
            Membership.objects.get_or_create(
                user=tm_user,
                firm=firm,
                defaults={"role": tm_role},
            )
            team_users.append(tm_user)

        # ---- records (core + extended) ----
        records: list[PipelineRecord] = []
        for data in RECORDS:
            company = companies[data["company_index"]]
            contact_person = persons[data["contact_person_index"]]
            cat_slug = data.get("category_slug", "prileziosti")
            stage_order = data.get("stage_order", 0)
            category = categories_by_slug.get(cat_slug)
            stage = stages_by_slug.get(cat_slug, {}).get(stage_order)

            record, created = PipelineRecord.objects.get_or_create(
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
                    "created_by": user,
                    "category": category,
                    "current_stage": stage,
                    "notes": data.get("notes", ""),
                },
            )
            records.append(record)
            if created:
                self.stdout.write(f" + Záznam: {record.title}")

        # Extended records — distribute assignment across the whole team and
        # set realistic historical/future created_at.
        rng = random.Random(42)
        now = timezone.now()
        for tup in MORE_RECORDS:
            (title, status, source, value, currency, company_idx,
             contact_idx, cat_slug, stage_order, notes, days_ago) = tup
            company = companies[company_idx] if company_idx is not None else None
            contact_person = persons[contact_idx] if contact_idx is not None else None
            category = categories_by_slug.get(cat_slug)
            stage = stages_by_slug.get(cat_slug, {}).get(stage_order)
            assignee = rng.choice(team_users)

            record, created = PipelineRecord.objects.get_or_create(
                firm=firm,
                title=title,
                defaults={
                    "status": status,
                    "source": source,
                    "value": value,
                    "currency": currency,
                    "company": company,
                    "contact_person": contact_person,
                    "assigned_to": assignee,
                    "created_by": user,
                    "category": category,
                    "current_stage": stage,
                    "notes": notes,
                },
            )
            records.append(record)
            if created:
                # Backdate created_at for realistic timeline distribution.
                created_at = now - timedelta(days=days_ago, hours=rng.randint(0, 23))
                PipelineRecord.objects.filter(pk=record.pk).update(
                    created_at=created_at,
                    updated_at=created_at + timedelta(hours=rng.randint(1, 240)),
                )
                self.stdout.write(f" + Záznam: {record.title}")

        # ---- core activities (deterministic) ----
        for record_index, activity_list in ACTIVITIES_BY_RECORD.items():
            if record_index >= len(records):
                continue
            target_record = records[record_index]
            if Activity.objects.filter(record=target_record).exists():
                continue
            for body, atype in activity_list:
                Activity.objects.create(
                    record=target_record,
                    user=user,
                    type=atype,
                    content_text=body,
                )
            self.stdout.write(
                f" + {len(activity_list)} aktivit na '{target_record.title}'"
            )

        # ---- extended activities (programmatic, varied types & dates) ----
        ext_activity_count = 0
        for idx, target_record in enumerate(records[len(RECORDS):], start=len(RECORDS)):
            if Activity.objects.filter(record=target_record).exists():
                continue
            # 4–9 activities per record, distributed back in time.
            n = rng.randint(4, 9)
            base_offset = rng.randint(20, 90)
            for i in range(n):
                atype, body = rng.choice(ACTIVITY_BANK)
                a_user = rng.choice(team_users)
                created = Activity.objects.create(
                    record=target_record,
                    user=a_user,
                    type=atype,
                    content_text=body,
                )
                ts = now - timedelta(
                    days=max(0, base_offset - i * rng.randint(1, 5)),
                    hours=rng.randint(0, 23),
                    minutes=rng.randint(0, 59),
                )
                Activity.objects.filter(pk=created.pk).update(created_at=ts)
                ext_activity_count += 1
        if ext_activity_count:
            self.stdout.write(f" + {ext_activity_count} doplňujících aktivit")

        # ---- projects ----
        projects_by_name: dict[str, Project] = {}
        for project_name in PROJECTS:
            project, created = Project.objects.get_or_create(firm=firm, name=project_name)
            projects_by_name[project_name] = project
            if created:
                self.stdout.write(f" + Projekt: {project_name}")

        # ---- tasks (core + extended) ----
        for title, record_index, days_offset, priority, status in TASKS:
            if record_index >= len(records):
                continue
            target_record = records[record_index]
            task, created = Task.objects.get_or_create(
                firm=firm,
                title=title,
                record=target_record,
                defaults={
                    "assigned_to": user,
                    "due_date": now + timedelta(days=days_offset),
                    "priority": priority,
                    "status": status,
                    "is_completed": status == TaskStatus.DONE,
                    "completed_at": now if status == TaskStatus.DONE else None,
                    "created_by": user,
                },
            )
            if created:
                self.stdout.write(f" + Úkol: {title}")

        ext_tasks: list[Task] = []
        for tup in EXTENDED_TASKS:
            (title, rec_idx, days_offset, priority, status, kind,
             is_pinned, is_archived, est_minutes) = tup
            target_record = None
            if rec_idx is not None and rec_idx < len(records):
                target_record = records[rec_idx]
            assignee = rng.choice(team_users)
            task, created = Task.objects.get_or_create(
                firm=firm,
                title=title,
                record=target_record,
                defaults={
                    "assigned_to": assignee,
                    "created_by": user,
                    "due_date": now + timedelta(days=days_offset),
                    "priority": priority,
                    "status": status,
                    "kind": kind,
                    "is_completed": status == TaskStatus.DONE,
                    "completed_at": (now + timedelta(days=days_offset))
                    if status == TaskStatus.DONE
                    else None,
                    "completed_by": assignee if status == TaskStatus.DONE else None,
                    "is_pinned": is_pinned,
                    "is_archived": is_archived,
                    "estimated_minutes": est_minutes,
                },
            )
            ext_tasks.append(task)
            if created:
                # add watchers (other team members)
                watchers = [u for u in team_users if u != assignee][:2]
                if watchers:
                    task.watchers.add(*watchers)
                self.stdout.write(f" + Úkol: {title}")

        # ---- streamline TODOs / sub-tasks on selected extended tasks ----
        for ext_idx, items in STREAMLINE_ITEMS_DATA.items():
            if ext_idx >= len(ext_tasks):
                continue
            parent_task = ext_tasks[ext_idx]
            if StreamlineItem.objects.filter(task=parent_task).exists():
                continue
            for order, (kind, text, is_resolved) in enumerate(items):
                StreamlineItem.objects.create(
                    task=parent_task,
                    kind=kind,
                    text=text,
                    is_resolved=is_resolved,
                    resolved_at=now if is_resolved else None,
                    resolved_by=user if is_resolved else None,
                    order=order,
                    created_by=user,
                )

        # ---- proposal templates + their items ----
        for tpl_def in PROPOSAL_TEMPLATES_DATA:
            tpl, tpl_created = ProposalTemplate.objects.get_or_create(
                firm=firm,
                name=tpl_def["name"],
                defaults={
                    "intro_text": tpl_def["intro_text"],
                    "closing_text": tpl_def["closing_text"],
                },
            )
            if tpl_created:
                for pos, item in enumerate(tpl_def["items"]):
                    desc, qty, unit, disc, vat = item
                    ProposalTemplateItem.objects.create(
                        template=tpl,
                        description=desc,
                        quantity=qty,
                        unit_price=unit,
                        discount=disc,
                        vat_rate=vat,
                        position=pos,
                    )
                self.stdout.write(f" + Šablona nabídky: {tpl.name}")

        # ---- firm proposal catalog items ----
        for pos, (desc, qty, unit, disc, vat, sku) in enumerate(FIRM_CATALOG_ITEMS):
            FirmProposalItem.objects.get_or_create(
                firm=firm,
                sku=sku,
                defaults={
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit,
                    "discount": disc,
                    "vat_rate": vat,
                    "position": pos,
                },
            )

        # ---- proposals + items ----
        proposals_created = 0
        for tup in PROPOSALS_DATA:
            rec_idx, title, status, currency, days_offset, items_def = tup
            if rec_idx >= len(records):
                continue
            target_record = records[rec_idx]
            sent_at = now + timedelta(days=days_offset) if status != ProposalStatus.DRAFT else None
            responded_at = None
            view_count = 0
            first_viewed_at = None
            if status in (ProposalStatus.VIEWED, ProposalStatus.ACCEPTED, ProposalStatus.REJECTED):
                view_count = rng.randint(2, 12)
                first_viewed_at = (sent_at or now) + timedelta(hours=rng.randint(2, 96))
            if status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED):
                responded_at = (first_viewed_at or now) + timedelta(days=rng.randint(1, 14))

            proposal, created = Proposal.objects.get_or_create(
                firm=firm,
                title=title,
                defaults={
                    "record": target_record,
                    "customer": target_record.contact_person,
                    "status": status,
                    "currency": currency,
                    "expiry_date": (now + timedelta(days=30)).date(),
                    "intro_text": "Vážený kliente, zasíláme Vám nezávaznou nabídku.",
                    "closing_text": "Děkujeme za Váš čas. Tým LeadLab.",
                    "sent_at": sent_at,
                    "first_viewed_at": first_viewed_at,
                    "responded_at": responded_at,
                    "view_count": view_count,
                    "created_by": user,
                    "assigned_to": rng.choice(team_users),
                },
            )
            if created:
                for pos, (desc, qty, unit, disc, vat) in enumerate(items_def):
                    ProposalItem.objects.create(
                        proposal=proposal,
                        description=desc,
                        quantity=qty,
                        unit_price=unit,
                        discount=disc,
                        vat_rate=vat,
                        position=pos,
                    )
                proposals_created += 1
        if proposals_created:
            self.stdout.write(f" + Nabídek vytvořeno: {proposals_created}")

        # ---- revenue items ----
        for tup in REVENUE_ITEMS_DATA:
            rec_idx, title, amount, currency, days_ago, recurrence = tup
            if rec_idx >= len(records):
                continue
            target_record = records[rec_idx]
            RevenueItem.objects.get_or_create(
                firm=firm,
                title=title,
                date=(now - timedelta(days=days_ago)).date(),
                defaults={
                    "user": user,
                    "record": target_record,
                    "customer": target_record.contact_person,
                    "amount": amount,
                    "currency": currency,
                    "recurrence": recurrence,
                    "notes": "",
                },
            )

        # ---- expense items ----
        for tup in EXPENSE_ITEMS_DATA:
            rec_idx, title, amount, currency, days_ago, recurrence = tup
            target_record = None
            if rec_idx is not None and rec_idx < len(records):
                target_record = records[rec_idx]
            ExpenseItem.objects.get_or_create(
                firm=firm,
                title=title,
                date=(now - timedelta(days=days_ago)).date(),
                defaults={
                    "user": user,
                    "record": target_record,
                    "amount": amount,
                    "currency": currency,
                    "recurrence": recurrence,
                    "notes": "",
                },
            )

        # ---- time entries ----
        for idx, tup in enumerate(TIME_ENTRIES_DATA):
            rec_idx, duration, description, billable, days_ago = tup
            target_record = None
            if rec_idx is not None and rec_idx < len(records):
                target_record = records[rec_idx]
            started_at = now - timedelta(days=days_ago, hours=8 + (idx % 8))
            ended_at = started_at + timedelta(minutes=duration)
            TimeEntry.objects.get_or_create(
                firm=firm,
                description=description,
                duration_minutes=duration,
                defaults={
                    "user": rng.choice(team_users),
                    "record": target_record,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "is_billable": billable,
                    "hourly_rate": Decimal("2200") if billable else None,
                },
            )

        # ---- checkpoints ----
        for tup in CHECKPOINTS_DATA:
            rec_idx, name, days_offset, completed, description = tup
            if rec_idx >= len(records):
                continue
            target_record = records[rec_idx]
            Checkpoint.objects.get_or_create(
                record=target_record,
                name=name,
                defaults={
                    "date": (now + timedelta(days=days_offset)).date(),
                    "is_completed": completed,
                    "description": description,
                },
            )

        # ---- saved views ----
        for sv in SAVED_VIEWS_DATA:
            SavedView.objects.get_or_create(
                user=user,
                firm=firm,
                entity=sv["entity"],
                name=sv["name"],
                defaults={
                    "filters": sv["filters"],
                    "sort_by": sv["sort_by"],
                    "sort_dir": sv["sort_dir"],
                    "columns": sv["columns"],
                },
            )

        # ---- record scoring rules ----
        for field, operand, score_delta in SCORING_RULES_DATA:
            RecordScoringRule.objects.get_or_create(
                firm=firm,
                field=field,
                operand=operand,
                defaults={"score_delta": score_delta},
            )

        # ---- notifications for the owner inbox ----
        for event, payload, days_ago, is_read in NOTIFICATIONS_DATA:
            existing = Notification.objects.filter(
                firm=firm, user=user, event=event, payload=payload,
            ).first()
            if existing:
                continue
            n_obj = Notification.objects.create(
                firm=firm,
                user=user,
                event=event,
                payload=payload,
                is_read=is_read,
            )
            Notification.objects.filter(pk=n_obj.pk).update(
                created_at=now - timedelta(days=days_ago),
            )

        # ---- summary ----
        proposals_total = Proposal.objects.filter(firm=firm).count()
        activities_total = Activity.objects.filter(record__firm=firm).count()
        tasks_total = Task.objects.filter(firm=firm).count()
        revenue_total = RevenueItem.objects.filter(firm=firm).count()
        expense_total = ExpenseItem.objects.filter(firm=firm).count()
        time_total = TimeEntry.objects.filter(firm=firm).count()

        self.stdout.write(self.style.SUCCESS(
            f"\nDemonstační data úspěšně načtena!"
            f"\n  Členové týmu:        {Membership.objects.filter(firm=firm).count()}"
            f"\n  Firmy (kontakty):    {sum(1 for c in companies)}"
            f"\n  Osoby (kontakty):    {len(persons)}"
            f"\n  Pipeline záznamy:    {len(records)}"
            f"\n  Aktivity:            {activities_total}"
            f"\n  Úkoly:               {tasks_total}"
            f"\n  Nabídky:             {proposals_total}"
            f"\n  Šablony nabídek:     {ProposalTemplate.objects.filter(firm=firm).count()}"
            f"\n  Katalog položek:     {FirmProposalItem.objects.filter(firm=firm).count()}"
            f"\n  Příjmy (RevenueItem):{revenue_total}"
            f"\n  Náklady (ExpenseItem):{expense_total}"
            f"\n  Časové záznamy:      {time_total}"
            f"\n  Milníky:             {Checkpoint.objects.filter(record__firm=firm).count()}"
            f"\n  Uložené pohledy:     {SavedView.objects.filter(firm=firm).count()}"
            f"\n  Skórovací pravidla:  {RecordScoringRule.objects.filter(firm=firm).count()}"
            f"\n  Notifikace:          {Notification.objects.filter(firm=firm).count()}"
            f"\n  Přihlašovací e-mail: {email}"
            f"\n  Heslo:               {password}"
        ))
