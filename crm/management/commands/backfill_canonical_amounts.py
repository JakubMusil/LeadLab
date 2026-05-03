"""
Management command: backfill_canonical_amounts

Recalculates canonical_amount for all financial records (Lead, ExpenseItem,
RevenueItem) across all firms.

For records where currency == firm.default_currency, sets canonical_amount
to amount directly (no rate conversion needed).  For other currencies,
attempts to look up the rate at the record's date; records where no rate is
available are skipped and counted as "pending".

Usage:
    python manage.py backfill_canonical_amounts
    python manage.py backfill_canonical_amounts --firm <firm_id>
    python manage.py backfill_canonical_amounts --dry-run
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Backfill canonical_amount for Lead, ExpenseItem, RevenueItem records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--firm",
            dest="firm_id",
            default=None,
            help="Only process records for the given firm UUID.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would happen without saving anything.",
        )

    def handle(self, *args, **options):
        from firms.models import Firm
        from crm.models import Lead, ExpenseItem, RevenueItem
        from crm.money import to_canonical

        dry_run = options["dry_run"]
        firm_id = options["firm_id"]

        if firm_id:
            firms = list(Firm.objects.filter(id=firm_id))
            if not firms:
                self.stderr.write(self.style.ERROR(f"Firm {firm_id} not found."))
                return
        else:
            firms = list(Firm.objects.all())

        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}Processing {len(firms)} firm(s)…"
        )

        total_updated = 0
        total_skipped = 0
        now = timezone.now()

        model_defs = [
            (Lead, "value", "created_at"),
            (ExpenseItem, "amount", "date"),
            (RevenueItem, "amount", "date"),
        ]

        for firm in firms:
            firm_updated = 0
            firm_skipped = 0

            for model_class, amount_field, date_field in model_defs:
                qs = model_class.objects.filter(firm=firm).exclude(**{amount_field: None})
                for obj in qs.iterator(chunk_size=500):
                    amount = getattr(obj, amount_field)
                    record_date = getattr(obj, date_field, None)
                    if hasattr(record_date, "date"):
                        record_date = record_date.date()

                    canonical, rate_used = to_canonical(
                        amount, obj.currency, firm, date=record_date
                    )

                    if canonical is None:
                        firm_skipped += 1
                        continue

                    if not dry_run:
                        obj.canonical_amount = canonical
                        obj.canonical_currency = firm.default_currency
                        obj.canonical_rate_used = rate_used
                        obj.canonical_updated_at = now
                        obj.save(update_fields=[
                            "canonical_amount", "canonical_currency",
                            "canonical_rate_used", "canonical_updated_at",
                        ])
                    firm_updated += 1

            self.stdout.write(
                f"  Firm {firm.name} ({firm.id}): "
                f"{firm_updated} updated, {firm_skipped} skipped (no rate)"
            )
            total_updated += firm_updated
            total_skipped += firm_skipped

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Done. Total: {total_updated} updated, {total_skipped} skipped."
            )
        )
