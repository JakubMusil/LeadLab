from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0009_remove_firm_fakturoid"),
    ]

    operations = [
        migrations.AddField(
            model_name="firm",
            name="default_currency",
            field=models.CharField(
                default="CZK",
                help_text="ISO 4217 currency code used as the reporting currency for this workspace.",
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="firm",
            name="number_locale",
            field=models.CharField(
                default="cs-CZ",
                help_text="BCP 47 locale tag controlling number/currency formatting (e.g. 'cs-CZ', 'en-US').",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="firm",
            name="exchange_rate_mode",
            field=models.CharField(
                choices=[("auto", "Automatic (ECB)"), ("manual", "Manual rates")],
                default="auto",
                help_text="How exchange rates are sourced for this workspace.",
                max_length=10,
            ),
        ),
    ]
