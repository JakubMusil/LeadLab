import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadlab.settings")
django.setup()

from crm.models import Task, Activity, Lead
print("Tasks:", Task.objects.count())
print("Activities:", Activity.objects.count())
print("Leads:", Lead.objects.count())
