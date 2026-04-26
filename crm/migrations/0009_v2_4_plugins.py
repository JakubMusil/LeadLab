# Generated for v2.4 — Email Sequences plugin

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0008_v2_3_proposals"),
        ("firms", "0006_plugin_config"),
    ]

    operations = [
        # EmailSequence
        migrations.CreateModel(
            name="EmailSequence",
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
                ("description", models.TextField(blank=True)),
                (
                    "trigger_status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("proposal", "Proposal"),
                            ("negotiation", "Negotiation"),
                            ("won", "Won"),
                            ("lost", "Lost"),
                            ("canceled", "Canceled"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "email sequence",
                "verbose_name_plural": "email sequences",
                "ordering": ["name"],
            },
        ),
        migrations.AddIndex(
            model_name="emailsequence",
            index=models.Index(
                fields=["firm", "trigger_status", "is_active"],
                name="crm_emailseq_firm_trigger_idx",
            ),
        ),
        # EmailSequenceStep
        migrations.CreateModel(
            name="EmailSequenceStep",
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
                    "sequence",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="crm.emailsequence",
                    ),
                ),
                (
                    "step_order",
                    models.PositiveSmallIntegerField(default=0),
                ),
                (
                    "delay_days",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Days after the previous step before this email is sent.",
                    ),
                ),
                ("subject", models.CharField(max_length=255)),
                ("body_template", models.TextField()),
            ],
            options={
                "verbose_name": "email sequence step",
                "verbose_name_plural": "email sequence steps",
                "ordering": ["sequence", "step_order"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="emailsequencestep",
            unique_together={("sequence", "step_order")},
        ),
        # SequenceEnrollment
        migrations.CreateModel(
            name="SequenceEnrollment",
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
                    "sequence",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="enrollments",
                        to="crm.emailsequence",
                    ),
                ),
                (
                    "lead",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sequence_enrollments",
                        to="crm.lead",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=20,
                    ),
                ),
                ("current_step", models.PositiveSmallIntegerField(default=0)),
                (
                    "next_send_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("enrolled_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "sequence enrollment",
                "verbose_name_plural": "sequence enrollments",
                "ordering": ["-enrolled_at"],
            },
        ),
        migrations.AddIndex(
            model_name="sequenceenrollment",
            index=models.Index(
                fields=["status", "next_send_at"],
                name="crm_seqenroll_status_next_idx",
            ),
        ),
    ]
