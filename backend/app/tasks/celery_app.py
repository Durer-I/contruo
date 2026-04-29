from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "contruo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.test_task", "app.tasks.pdf_processing", "app.tasks.export_generation"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Auto-retry transient failures on every task with a sane backoff.
    # Per-task ``retry_backoff`` / ``retry_kwargs`` may override these defaults.
    task_annotations={
        "*": {
            "autoretry_for": (IOError, ConnectionError, TimeoutError),
            "retry_backoff": True,
            "retry_backoff_max": 300,
            "retry_jitter": True,
            "max_retries": 3,
        }
    },
)
