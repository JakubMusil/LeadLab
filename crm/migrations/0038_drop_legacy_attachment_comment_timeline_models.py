# Phases 2-5 cleanup: drop models that have been replaced by Activity + Document.
#
# Removed models:
#   - LeadAttachment       → replaced by Document (lead FK) + Activity(type=file_upload)
#   - TaskAttachment       → replaced by Document (task FK) + Activity(type=file_upload)
#   - TaskComment          → replaced by Activity(type=comment, task=...)
#   - TaskTimelineEntry    → replaced by Activity(task=...)
#   - TaskCommentReaction  → replaced by ActivityReaction(activity=...)
#   - TaskVoiceAttachment  → replaced by Activity(type=voice_memo) + Document
#   - LeadStatusHistory    → replaced by Activity(type=status_change) with metadata
#
# Data migrations are intentionally skipped — the system is still in development
# and there is no production data to preserve.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0037_activityreaction_activity_task_alter_activity_type_and_more"),
    ]

    operations = [
        # Drop TaskVoiceAttachment first (FK → TaskTimelineEntry)
        migrations.DeleteModel(name="TaskVoiceAttachment"),
        # Drop TaskCommentReaction (FK → TaskTimelineEntry)
        migrations.DeleteModel(name="TaskCommentReaction"),
        # Drop TaskTimelineEntry
        migrations.DeleteModel(name="TaskTimelineEntry"),
        # Drop TaskComment
        migrations.DeleteModel(name="TaskComment"),
        # Drop TaskAttachment
        migrations.DeleteModel(name="TaskAttachment"),
        # Drop LeadAttachment
        migrations.DeleteModel(name="LeadAttachment"),
        # Drop LeadStatusHistory
        migrations.DeleteModel(name="LeadStatusHistory"),
    ]
