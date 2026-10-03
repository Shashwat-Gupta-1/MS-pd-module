"""Celery application instance, configured with Redis as broker/backend."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "msfincap",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],          # every module that defines tasks must be listed here
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,                    # a task is only acknowledged after it finishes (survives worker crashes)
    worker_prefetch_multiplier=1,           # long transcription jobs: take one task at a time
    task_track_started=True,
)
