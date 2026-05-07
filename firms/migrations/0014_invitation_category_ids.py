from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("firms", "0013_ownership_transfer"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="invited_category_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of Category UUID strings to grant view access on accept (used when invited_default_scope='category').",
            ),
        ),
    ]
