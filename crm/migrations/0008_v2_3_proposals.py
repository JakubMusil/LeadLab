# Generated for v2.3 — Business Proposals & Quote Builder

import uuid
import decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0007_v2_2_ux_intelligence"),
        ("firms", "0001_initial"),
    ]

    operations = [
        # ------------------------------------------------------------------
        # ProposalTemplate
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="ProposalTemplate",
            fields=[
                (
                    "firm",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="firms.firm",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("intro_text", models.TextField(blank=True)),
                ("closing_text", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "proposal template",
                "verbose_name_plural": "proposal templates",
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        # ------------------------------------------------------------------
        # ProposalTemplateItem
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="ProposalTemplateItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="crm.proposaltemplate",
                    ),
                ),
                ("description", models.CharField(max_length=500)),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=4, default=decimal.Decimal("1"), max_digits=14
                    ),
                ),
                (
                    "unit_price",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0"), max_digits=14
                    ),
                ),
                (
                    "discount",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        help_text="Discount percentage (0–100).",
                        max_digits=5,
                    ),
                ),
                (
                    "vat_rate",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        help_text="VAT rate percentage (e.g. 21 for 21%).",
                        max_digits=5,
                    ),
                ),
                ("position", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "verbose_name": "proposal template item",
                "verbose_name_plural": "proposal template items",
                "ordering": ["position"],
            },
        ),
        # ------------------------------------------------------------------
        # Proposal
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="Proposal",
            fields=[
                (
                    "firm",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="firms.firm",
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "lead",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proposals",
                        to="crm.lead",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("sent", "Sent"),
                            ("viewed", "Viewed"),
                            ("accepted", "Accepted"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("currency", models.CharField(default="CZK", max_length=3)),
                ("notes", models.TextField(blank=True)),
                ("intro_text", models.TextField(blank=True)),
                ("closing_text", models.TextField(blank=True)),
                (
                    "public_token",
                    models.UUIDField(
                        default=uuid.uuid4,
                        unique=True,
                        db_index=True,
                        help_text="Token used in the public (no-auth) proposal URL.",
                    ),
                ),
                (
                    "token_expires_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        help_text="When the public link expires.",
                    ),
                ),
                ("view_count", models.PositiveIntegerField(default=0)),
                ("first_viewed_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "proposal",
                "verbose_name_plural": "proposals",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="proposal",
            index=models.Index(fields=["lead", "-created_at"], name="crm_proposal_lead_created_idx"),
        ),
        migrations.AddIndex(
            model_name="proposal",
            index=models.Index(fields=["firm", "status"], name="crm_proposal_firm_status_idx"),
        ),
        # ------------------------------------------------------------------
        # ProposalItem
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="ProposalItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "proposal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="crm.proposal",
                    ),
                ),
                ("description", models.CharField(max_length=500)),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=4, default=decimal.Decimal("1"), max_digits=14
                    ),
                ),
                (
                    "unit_price",
                    models.DecimalField(
                        decimal_places=2, default=decimal.Decimal("0"), max_digits=14
                    ),
                ),
                (
                    "discount",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        help_text="Discount percentage (0–100).",
                        max_digits=5,
                    ),
                ),
                (
                    "vat_rate",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        help_text="VAT rate percentage (e.g. 21 for 21%).",
                        max_digits=5,
                    ),
                ),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "proposal item",
                "verbose_name_plural": "proposal items",
                "ordering": ["position", "created_at"],
            },
        ),
    ]
