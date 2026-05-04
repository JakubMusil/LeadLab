"""
Management command: seed_pipeline_categories

Creates the three default pipeline categories (Příležitosti, Realizace, Správa)
with their predefined stages and field configuration for a given firm.

Usage:
    python manage.py seed_pipeline_categories --firm-id <uuid>

Safe to run multiple times — existing objects are skipped (get_or_create).
Note: CategoryField defaults (value_type, widget, etc.) are only applied when a
field is first created. Existing fields will not be updated on subsequent runs.
"""

from __future__ import annotations

import uuid
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from crm.models import Category, CategoryField, Stage
from firms.models import Firm


# ---------------------------------------------------------------------------
# Default category definitions
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES = [
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
            {
                "field_key": "value_currency",
                "is_visible": True,
                "is_required": False,
                "order": 0,
                "value_type": "currency",
                "widget": "currency_input",
                "help_text_override": "Odhadovaná hodnota příležitosti",
            },
            {
                "field_key": "expires_at",
                "is_visible": True,
                "is_required": False,
                "order": 1,
                "value_type": "date",
                "widget": "date_picker",
                "help_text_override": "Datum vypršení platnosti nabídky",
            },
            {
                "field_key": "source",
                "is_visible": True,
                "is_required": False,
                "order": 2,
                "value_type": "select",
                "widget": "select",
                "validation_rules": {
                    "options": ["web", "email", "referral", "cold_call", "social", "other"],
                },
                "help_text_override": "Odkud přišel tento lead",
            },
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
            {
                "field_key": "date_range",
                "is_visible": True,
                "is_required": False,
                "order": 0,
                "value_type": "date",
                "widget": "date_picker",
                "help_text_override": "Datum zahájení a ukončení realizace",
            },
            {
                "field_key": "notes",
                "is_visible": True,
                "is_required": False,
                "order": 1,
                "value_type": "text",
                "widget": "textarea",
                "help_text_override": "Interní poznámky k realizaci",
            },
            {
                "field_key": "origin_record",
                "is_visible": True,
                "is_required": False,
                "order": 2,
                "value_type": "text",
                "widget": "text_input",
                "help_text_override": "Odkaz na zdrojovou příležitost",
            },
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
            {
                "field_key": "notes",
                "is_visible": True,
                "is_required": False,
                "order": 0,
                "value_type": "text",
                "widget": "textarea",
                "help_text_override": "Interní poznámky",
            },
            {
                "field_key": "expires_at",
                "is_visible": True,
                "is_required": False,
                "order": 1,
                "value_type": "date",
                "widget": "date_picker",
                "help_text_override": "Datum vypršení smlouvy nebo správy",
            },
        ],
    },
]


def seed_for_firm(firm: Firm) -> dict:
    """
    Seed the default categories/stages/fields for *firm*.

    Returns a dict with counts of created objects:
        {"categories": int, "stages": int, "fields": int}
    """
    counts = {"categories": 0, "stages": 0, "fields": 0}

    with transaction.atomic():
        for cat_def in DEFAULT_CATEGORIES:
            stage_defs = cat_def.pop("stages", [])
            field_defs = cat_def.pop("fields", [])

            category, created = Category.objects.get_or_create(
                firm=firm,
                slug=cat_def["slug"],
                defaults={
                    "name": cat_def["name"],
                    "icon": cat_def["icon"],
                    "color": cat_def["color"],
                    "order": cat_def["order"],
                },
            )
            if created:
                counts["categories"] += 1

            for stage_def in stage_defs:
                _, created = Stage.objects.get_or_create(
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
                if created:
                    counts["stages"] += 1

            for field_def in field_defs:
                _, created = CategoryField.objects.get_or_create(
                    category=category,
                    field_key=field_def["field_key"],
                    defaults={
                        "is_visible": field_def.get("is_visible", True),
                        "is_required": field_def.get("is_required", False),
                        "order": field_def.get("order", 0),
                        "value_type": field_def.get("value_type", "text"),
                        "widget": field_def.get("widget", "auto"),
                        "validation_rules": field_def.get("validation_rules", {}),
                        "label_override": field_def.get("label_override", ""),
                        "help_text_override": field_def.get("help_text_override", ""),
                    },
                )
                if created:
                    counts["fields"] += 1

    return counts


class Command(BaseCommand):
    help = "Seed default pipeline categories, stages, and fields for a given firm."

    def add_arguments(self, parser):
        parser.add_argument(
            "--firm-id",
            type=str,
            required=True,
            help="UUID of the firm to seed pipeline categories for.",
        )

    def handle(self, *args, **options):
        firm_id = options["firm_id"]
        try:
            firm = Firm.objects.get(id=firm_id)
        except (Firm.DoesNotExist, ValueError):
            raise CommandError(f"Firm with id '{firm_id}' not found.")

        counts = seed_for_firm(firm)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded firm '{firm.name}': "
                f"{counts['categories']} categories, "
                f"{counts['stages']} stages, "
                f"{counts['fields']} fields created."
            )
        )
