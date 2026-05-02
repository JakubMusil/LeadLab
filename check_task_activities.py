import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadlab.settings")
django.setup()

from crm.models import Task, Activity
from django.db.models import Q

# Let's find a task that was recently created
task = Task.objects.order_by('-created_at').first()
if not task:
    print("No tasks found.")
else:
    print(f"Task ID: {task.id}, Title: {task.title}")
    
    # 1. Activities directly linked via task_id
    a1 = Activity.objects.filter(task=task)
    print(f"Activities with task=task: {a1.count()}")
    for a in a1:
        print(f" - {a.id} ({a.type})")
        
    # 2. Activities linked via metadata__task_id
    a2 = Activity.objects.filter(metadata__task_id=str(task.id))
    print(f"Activities with metadata__task_id: {a2.count()}")
    for a in a2:
        print(f" - {a.id} ({a.type})")
        
    # 3. What does list_task_activities query do?
    a_combined = Activity.objects.filter(Q(task=task) | Q(metadata__task_id=str(task.id)))
    print(f"Combined query count: {a_combined.count()}")
