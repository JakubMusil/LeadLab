import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadlab.settings")
django.setup()

from crm.models import Task, Activity
from django.db.models import Q

# Let's count tasks with NO activities
tasks_with_activity = Activity.objects.filter(task__isnull=False).values_list('task_id', flat=True)
tasks_with_meta_activity = Activity.objects.filter(metadata__has_key='task_id').values_list('metadata__task_id', flat=True)

# Note: sqlite doesn't support metadata__has_key
