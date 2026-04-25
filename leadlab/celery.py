"""
Celery application configuration for LeadLab.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leadlab.settings")

app = Celery("leadlab")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
