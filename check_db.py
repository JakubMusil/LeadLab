import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadlab.settings")
django.setup()

from crm.models import Task, Activity, PipelineRecord
print("Tasks:", Task.objects.count())
print("Activities:", Activity.objects.count())
print("Leads:", PipelineRecord.objects.count())
