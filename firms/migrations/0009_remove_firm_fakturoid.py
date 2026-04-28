from django.db import migrations, models


def copy_fakturoid_to_plugin_config(apps, schema_editor):
    """
    Data migration: copy Fakturoid credentials from Firm fields to PluginConfig.

    Only creates a PluginConfig record when all three credentials are present.
    Skips firms that already have a 'fakturoid' PluginConfig row (idempotent).
    """
    Firm = apps.get_model("firms", "Firm")
    PluginConfig = apps.get_model("firms", "PluginConfig")

    for firm in Firm.objects.exclude(fakturoid_slug=""):
        slug = firm.fakturoid_slug or ""
        email = firm.fakturoid_email or ""
        token = firm.fakturoid_token or ""
        if slug and email and token:
            PluginConfig.objects.get_or_create(
                firm=firm,
                plugin_name="fakturoid",
                defaults={
                    "enabled": True,
                    "config": {
                        "slug": slug,
                        "email": email,
                        "api_token": token,
                    },
                },
            )


def reverse_copy_to_firm_fields(apps, schema_editor):
    """
    Reverse migration: copy Fakturoid credentials from PluginConfig back to Firm fields.
    """
    Firm = apps.get_model("firms", "Firm")
    PluginConfig = apps.get_model("firms", "PluginConfig")

    for pc in PluginConfig.objects.filter(plugin_name="fakturoid"):
        cfg = pc.config or {}
        try:
            firm = Firm.objects.get(id=pc.firm_id)
            firm.fakturoid_slug = cfg.get("slug", "")
            firm.fakturoid_email = cfg.get("email", "")
            firm.fakturoid_token = cfg.get("api_token", "")
            firm.save(update_fields=["fakturoid_slug", "fakturoid_email", "fakturoid_token"])
        except Firm.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0008_firm_fakturoid"),
    ]

    operations = [
        migrations.RunPython(copy_fakturoid_to_plugin_config, reverse_copy_to_firm_fields),
        migrations.RemoveField(
            model_name="firm",
            name="fakturoid_slug",
        ),
        migrations.RemoveField(
            model_name="firm",
            name="fakturoid_email",
        ),
        migrations.RemoveField(
            model_name="firm",
            name="fakturoid_token",
        ),
    ]
