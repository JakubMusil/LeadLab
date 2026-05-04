"""
Management command: backfill_firm_currency

For each firm, sets default_currency to the most frequently used currency
among its PipelineRecord records.  Firms with no records are left at their current default.
"""
from collections import Counter

from django.core.management.base import BaseCommand

from crm.models import PipelineRecord
from firms.models import Firm


class Command(BaseCommand):
    help = (
        "Back-fill firm.default_currency based on the most-used currency "
        "in existing PipelineRecord records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be changed without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        firms = Firm.objects.all()
        updated = 0
        skipped = 0

        for firm in firms:
            records = PipelineRecord.objects.filter(firm=firm).exclude(currency="").values_list("currency", flat=True)
            if not records.exists():
                skipped += 1
                self.stdout.write(f"  SKIP  {firm.name}: no records")
                continue

            counts = Counter(records)
            most_common_currency, count = counts.most_common(1)[0]
            total_records = sum(counts.values())
            has_mix = len(counts) > 1

            if has_mix:
                self.stderr.write(
                    self.style.WARNING(
                        f"  WARN  {firm.name}: mixed currencies {dict(counts)}; "
                        f"setting to most common '{most_common_currency}'"
                    )
                )
            else:
                self.stdout.write(
                    f"  OK    {firm.name}: {most_common_currency} ({total_records} records)"
                )

            if firm.default_currency != most_common_currency:
                if dry_run:
                    self.stdout.write(
                        f"  [dry-run] Would set {firm.name}.default_currency "
                        f"{firm.default_currency!r} → {most_common_currency!r}"
                    )
                else:
                    firm.default_currency = most_common_currency
                    firm.save(update_fields=["default_currency"])
                updated += 1

        verb = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {verb} {updated} firm(s); {skipped} firm(s) skipped (no records)."
            )
        )
