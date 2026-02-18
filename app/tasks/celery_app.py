from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "nexo",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery.conf.update(
    timezone="UTC",
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    beat_schedule={
        "storage-cleanup-orphans": {
            "task": "app.tasks.tasks.storage_cleanup_orphans",
            "schedule": 60 * 30,
        }
    },
)

