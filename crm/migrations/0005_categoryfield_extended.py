from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Extend CategoryField with value_type, widget, validation_rules,
    label_override, and help_text_override columns.

    All columns have non-null defaults so this is backwards-compatible
    with existing rows.
    """

    dependencies = [
        ("crm", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="categoryfield",
            name="value_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("number", "Number"),
                    ("currency", "Currency"),
                    ("date", "Date"),
                    ("datetime", "Date & Time"),
                    ("boolean", "Boolean"),
                    ("select", "Select (single)"),
                    ("multiselect", "Select (multiple)"),
                    ("url", "URL"),
                    ("email", "E-mail"),
                ],
                default="text",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="categoryfield",
            name="widget",
            field=models.CharField(
                choices=[
                    ("auto", "Auto (derive from type)"),
                    ("text_input", "Text input"),
                    ("textarea", "Textarea"),
                    ("number_input", "Number input"),
                    ("date_picker", "Date picker"),
                    ("datetime_picker", "Date & time picker"),
                    ("toggle", "Toggle / switch"),
                    ("select", "Select dropdown"),
                    ("multiselect", "Multi-select"),
                    ("color_picker", "Color picker"),
                    ("currency_input", "Currency input"),
                    ("rich_text", "Rich-text editor"),
                ],
                default="auto",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="categoryfield",
            name="validation_rules",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="categoryfield",
            name="label_override",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="categoryfield",
            name="help_text_override",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
