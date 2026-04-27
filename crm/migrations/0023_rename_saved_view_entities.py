from django.db import migrations, models


def rename_entity_values(apps, schema_editor):
    SavedView = apps.get_model("crm", "SavedView")
    SavedView.objects.filter(entity="leads").update(entity="opportunities")
    SavedView.objects.filter(entity="customers").update(entity="directory")


def reverse_rename_entity_values(apps, schema_editor):
    SavedView = apps.get_model("crm", "SavedView")
    SavedView.objects.filter(entity="opportunities").update(entity="leads")
    SavedView.objects.filter(entity="directory").update(entity="customers")


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0022_phase8_custom_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="savedview",
            name="entity",
            field=models.CharField(
                choices=[("opportunities", "Příležitosti"), ("directory", "Adresář")],
                max_length=20,
            ),
        ),
        migrations.RunPython(rename_entity_values, reverse_rename_entity_values),
    ]
