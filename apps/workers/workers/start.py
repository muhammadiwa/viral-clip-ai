
import os

from celery import Celery

from .telemetry import configure_worker_telemetry

BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("workers", broker=BROKER_URL, backend=BROKER_URL)
celery_app.autodiscover_tasks(["workers.tasks"])
configure_worker_telemetry(celery_app)
