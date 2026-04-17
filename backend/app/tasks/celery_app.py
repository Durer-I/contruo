from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "contruo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.test_task", "app.tasks.pdf_processing"],
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
)
