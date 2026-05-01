# Generated for Krok 3 — StreamlineItem unification
# - Creates StreamlineItem table
# - Drops legacy TaskChecklistItem table
# - Drops parent_task column from Task (legacy sub-task hierarchy)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0045_task_is_all_day_alter_activity_type_alter_task_kind'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --------------------------------------------------------------------
        # 1. Create StreamlineItem table
        # --------------------------------------------------------------------
        migrations.CreateModel(
            name='StreamlineItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('text', models.CharField(max_length=500)),
                ('is_resolved', models.BooleanField(db_index=True, default=False)),
                ('order', models.PositiveSmallIntegerField(db_index=True, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('kind', models.CharField(choices=[('todo', 'TODO'), ('subtask', 'Sub-task')], db_index=True, default='todo', max_length=10)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_streamline_items', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_streamline_items', to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='streamline_items', to='crm.task')),
            ],
            options={
                'verbose_name': 'streamline item',
                'verbose_name_plural': 'streamline items',
                'ordering': ['kind', 'order', 'created_at'],
                'indexes': [
                    models.Index(fields=['task', 'kind', 'order'], name='crm_streaml_task_id_kind_order_idx'),
                    models.Index(fields=['task', 'kind', 'is_resolved'], name='crm_streaml_task_id_kind_resolved_idx'),
                ],
            },
        ),
        # --------------------------------------------------------------------
        # 2. Drop legacy TaskChecklistItem table
        # --------------------------------------------------------------------
        migrations.DeleteModel(
            name='TaskChecklistItem',
        ),
        # --------------------------------------------------------------------
        # 3. Drop parent_task FK column from Task
        # --------------------------------------------------------------------
        migrations.RemoveField(
            model_name='task',
            name='parent_task',
        ),
        # --------------------------------------------------------------------
        # 4. Add new ActivityType values for StreamlineItem events
        # --------------------------------------------------------------------
        migrations.AlterField(
            model_name='activity',
            name='type',
            field=models.CharField(
                choices=[
                    ('comment', 'Comment'),
                    ('email_out', 'Email (Outbound)'),
                    ('email_in', 'Email (Inbound)'),
                    ('call', 'Call'),
                    ('meeting', 'Meeting'),
                    ('status_change', 'Status Change'),
                    ('file_upload', 'File Upload'),
                    ('task_created', 'Task Created'),
                    ('task_assigned', 'Task Assigned'),
                    ('task_completed', 'Task Completed'),
                    ('task_archived', 'Task Archived'),
                    ('streamline_items_added', 'Streamline Items Added'),
                    ('streamline_item_resolved', 'Streamline Item Resolved'),
                    ('streamline_item_reopened', 'Streamline Item Reopened'),
                    ('priority_change', 'Priority Change'),
                    ('assignee_change', 'Assignee Change'),
                    ('due_date_change', 'Due Date Change'),
                    ('approval_requested', 'Approval Requested'),
                    ('approval_resolved', 'Approval Resolved'),
                    ('time_logged', 'Time Logged'),
                    ('voice_memo', 'Voice Memo'),
                    ('proposal_created', 'Proposal Created'),
                    ('proposal_accepted', 'Proposal Accepted'),
                    ('proposal_rejected', 'Proposal Rejected'),
                    ('proposal_viewed', 'Proposal Viewed'),
                    ('entity_change', 'Field Changed'),
                    ('sms_out', 'SMS (Outbound)'),
                    ('sms_in', 'SMS (Inbound)'),
                    ('whatsapp_out', 'WhatsApp (Outbound)'),
                    ('whatsapp_in', 'WhatsApp (Inbound)'),
                    ('chat', 'Chat Message'),
                    ('meeting_scheduled', 'Meeting Scheduled'),
                    ('call_scheduled', 'Call Scheduled'),
                    ('event_scheduled', 'Event Scheduled'),
                    ('task_expired', 'Task Expired'),
                    ('link', 'Link'),
                    ('payment_received', 'Payment Received'),
                    ('invoice_sent', 'Invoice Sent'),
                    ('signature_requested', 'Signature Requested'),
                    ('signature_completed', 'Signature Completed'),
                    ('ai_summary', 'AI Summary'),
                    ('ai_suggested_action', 'AI Suggested Action'),
                    ('system_note', 'System Note'),
                    ('tag_added', 'Tag Added'),
                    ('tag_removed', 'Tag Removed'),
                    ('mention', 'Mention'),
                    ('pinned', 'Pinned'),
                    ('unpinned', 'Unpinned'),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]

