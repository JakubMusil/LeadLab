# Generated migration: add description, watchers, metadata to Task

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0012_rename_crm_automat_firm_id_trigger_active_idx_crm_automat_firm_id_b9f616_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='description',
            field=models.TextField(blank=True, help_text='Optional task description or notes.'),
        ),
        migrations.AddField(
            model_name='task',
            name='metadata',
            field=models.JSONField(blank=True, default=dict, help_text='Arbitrary structured data (e.g. extra assignees from @mentions).'),
        ),
        migrations.AddField(
            model_name='task',
            name='watchers',
            field=models.ManyToManyField(
                blank=True,
                help_text='Users who receive notifications about changes to this task.',
                related_name='watched_tasks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
