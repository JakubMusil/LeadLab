from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0053_add_checklist_activity_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lead',
            name='description',
        ),
        migrations.RemoveField(
            model_name='realization',
            name='description',
        ),
    ]
