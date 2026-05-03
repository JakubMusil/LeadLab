import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadlab.settings")
django.setup()

from crm.models import Activity, Task, PipelineRecord
from firms.models import Firm
from django.db.models import Q
import uuid

task_id = uuid.uuid4()
print("Trying query...")
try:
    a = list(Activity.objects.filter(
        Q(metadata__task_id=str(task_id))
    ))
    print("Success!")
except Exception as e:
    print("Crash!", e)
