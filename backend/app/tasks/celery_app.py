from celery import Celery
from kombu import Queue

from app.config import get_settings

settings = get_settings()

#: AI pipeline tasks run on their own queue so heavy AI workloads don't starve
#: PDF processing or exports. Run a separate worker with
#: ``celery -A app.tasks.celery_app worker -Q ai_pipeline -n ai-worker@%h``.
AI_PIPELINE_QUEUE = "ai_pipeline"

celery_app = Celery(
    "contruo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.test_task",
        "app.tasks.pdf_processing",
        "app.tasks.export_generation",
        "app.tasks.ai_pipeline",
    ],
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
    task_default_queue="celery",
    task_queues=(
        Queue("celery"),
        Queue(AI_PIPELINE_QUEUE),
    ),
    # Route every ``ai_pipeline.*`` task name to the dedicated queue. Adding new
    # AI task names automatically gets routing without explicit registration.
    task_routes={
        "ai_pipeline.*": {"queue": AI_PIPELINE_QUEUE},
    },
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
