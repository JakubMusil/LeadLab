"""
Migration: add created_by to Task; add TaskComment and TaskAttachment models.
"""
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
import crm.models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0013_task_watchers_description'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- Task.created_by --------------------------------------------------
        migrations.AddField(
            model_name='task',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who originally created this task.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_tasks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # --- TaskComment ------------------------------------------------------
        migrations.CreateModel(
            name='TaskComment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('content_html', models.TextField(help_text='Sanitised HTML content from the rich-text editor.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comments',
                    to='crm.task',
                )),
                ('author', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='task_comments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'task comment',
                'verbose_name_plural': 'task comments',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='taskcomment',
            index=models.Index(fields=['task', 'created_at'], name='crm_taskcom_task_id_created_idx'),
        ),

        # --- TaskAttachment ---------------------------------------------------
        migrations.CreateModel(
            name='TaskAttachment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file', models.FileField(upload_to=crm.models._task_attachment_upload_to)),
                ('original_filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(blank=True, max_length=100)),
                ('size_bytes', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='crm.task',
                )),
                ('uploaded_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='task_attachments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'task attachment',
                'verbose_name_plural': 'task attachments',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='taskattachment',
            index=models.Index(fields=['task', '-created_at'], name='crm_taskatt_task_id_created_idx'),
        ),
    ]
