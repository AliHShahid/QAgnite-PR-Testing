import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qa_agent.settings")

app = Celery("qa_agent")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

celery_app = app
