from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0007_alter_pluginconfig_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="firm",
            name="fakturoid_slug",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Fakturoid account slug (e.g. 'my-company'). Found in your Fakturoid URL.",
                max_length=255,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="firm",
            name="fakturoid_email",
            field=models.EmailField(
                blank=True,
                default="",
                help_text="Email address used to log in to Fakturoid.",
                max_length=254,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="firm",
            name="fakturoid_token",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Fakturoid API token (found in Fakturoid → Settings → API).",
                max_length=255,
            ),
            preserve_default=False,
        ),
    ]
