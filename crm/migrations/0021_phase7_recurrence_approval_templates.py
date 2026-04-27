# Phase 7 — Opakující se tasky (Recurrence), Schválení (Approval), Šablony (Templates)

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0020_phase6_time_tracking'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------
        # Task — Recurrence fields
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='task',
            name='recurrence',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text=(
                    'Recurrence config, e.g. {"type": "daily|weekly|monthly|custom", '
                    '"interval": 1, "day_of_week": [1,3], "ends_at": null}. '
                    'Null means no recurrence.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='recurrence_parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='recurrence_instances',
                to='crm.task',
                help_text='Points to the original (root) recurring task this instance was spawned from.',
            ),
        ),
        # ------------------------------------------------------------------
        # Task — Approval workflow fields
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='task',
            name='approval_required',
            field=models.BooleanField(
                default=False,
                help_text='When True, the task must be approved before it is considered done.',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='approval_requested_from',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='approval_tasks',
                to=settings.AUTH_USER_MODEL,
                help_text='The user who is asked to approve this task.',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='approval_status',
            field=models.CharField(
                choices=[
                    ('none', 'None'),
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='none',
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='approval_note',
            field=models.TextField(
                blank=True,
                help_text='Optional note explaining the approval decision (especially rejection reason).',
            ),
        ),
        # ------------------------------------------------------------------
        # Update Task.Meta index to include approval_status
        # ------------------------------------------------------------------
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['firm', 'approval_status'], name='crm_task_firm_approval_idx'),
        ),
        # ------------------------------------------------------------------
        # TaskTemplate model
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description_html', models.TextField(blank=True, help_text='Rich-text HTML description (TipTap output).')),
                ('priority', models.CharField(
                    choices=[
                        ('none', 'None'),
                        ('low', 'Low'),
                        ('medium', 'Medium'),
                        ('high', 'High'),
                        ('critical', 'Critical'),
                    ],
                    default='medium',
                    max_length=20,
                )),
                ('estimated_minutes', models.PositiveIntegerField(blank=True, null=True, help_text='Estimated task duration in minutes.')),
                ('checklist_items', models.JSONField(blank=True, default=list, help_text='List of checklist item objects: [{"text": "...", "position": 0}].')),
                ('tags', models.JSONField(blank=True, default=list, help_text='List of tag strings pre-filled on tasks created from this template.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('firm', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='firms.firm')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_task_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'task template',
                'verbose_name_plural': 'task templates',
                'ordering': ['name'],
                'indexes': [models.Index(fields=['firm', 'name'], name='crm_tasktemplate_firm_name_idx')],
            },
        ),
    ]
