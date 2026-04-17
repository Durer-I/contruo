import time
from app.tasks.celery_app import celery_app


@celery_app.task(name="test_task")
def test_task(message: str = "Hello from Celery!") -> dict:
    """A simple test task to verify the Celery + Redis pipeline works."""
    time.sleep(2)
    return {"status": "completed", "message": message}
