from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0057_soft_delete_priority_b_c'),
    ]

    operations = [
        migrations.AddField(
            model_name='savedview',
            name='columns',
            field=models.JSONField(
                default=list,
                help_text='Ordered list of visible column IDs, e.g. ["status","value"]. Empty means default.',
            ),
        ),
    ]
