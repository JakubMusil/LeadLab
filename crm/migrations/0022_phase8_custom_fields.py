from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0021_phase7_recurrence_approval_templates"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskCustomField",
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
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("number", "Number"),
                            ("date", "Date"),
                            ("dropdown", "Dropdown"),
                            ("checkbox", "Checkbox"),
                            ("url", "URL"),
                        ],
                        default="text",
                        max_length=20,
                    ),
                ),
                ("options", models.JSONField(blank=True, default=list)),
                ("is_required", models.BooleanField(default=False)),
                ("position", models.PositiveIntegerField(db_index=True, default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "task custom field",
                "verbose_name_plural": "task custom fields",
                "ordering": ["position", "name"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="TaskCustomFieldValue",
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
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="custom_field_values",
                        to="crm.task",
                    ),
                ),
                (
                    "field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="values",
                        to="crm.taskcustomfield",
                    ),
                ),
                ("value_text", models.TextField(blank=True)),
                (
                    "value_number",
                    models.DecimalField(
                        blank=True, decimal_places=6, max_digits=20, null=True
                    ),
                ),
                ("value_date", models.DateField(blank=True, null=True)),
                ("value_bool", models.BooleanField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "task custom field value",
                "verbose_name_plural": "task custom field values",
            },
        ),
        migrations.AddIndex(
            model_name="taskcustomfield",
            index=models.Index(
                fields=["firm", "position"], name="crm_taskcf_firm_pos_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="taskcustomfieldvalue",
            unique_together={("task", "field")},
        ),
    ]
