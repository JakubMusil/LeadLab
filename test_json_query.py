import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadlab.settings")
django.setup()

from crm.models import Activity, PipelineRecord
from django.db.models import Q
from firms.models import Firm

f = Firm.objects.create(name="test")
l = PipelineRecord.objects.create(title="Test PipelineRecord", firm=f)

a = Activity.objects.create(type="task_assigned", lead=l, metadata={"task_ids": ["123", "456"]})

q2 = Activity.objects.filter(metadata__contains={"task_ids": ["123"]}).count()
print(f"Contains match: {q2}")

a.delete()
l.delete()
f.delete()
