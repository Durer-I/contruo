"""Celery task: generate quantities export (Excel or PDF) and upload to storage."""

from __future__ import annotations

import logging
import uuid

from app.models.event_log import EventLog
from app.services import export_service
from app.tasks.celery_app import celery_app
from app.tasks.pdf_processing import SyncSession
from app.utils import storage

logger = logging.getLogger(__name__)


@celery_app.task(name="export.generate_quantities", bind=True, acks_late=True)
def generate_quantities_export(
    self,
    org_id_str: str,
    project_id_str: str,
    user_id_str: str,
    export_format: str,
) -> dict:
    org_id = uuid.UUID(org_id_str)
    project_id = uuid.UUID(project_id_str)
    user_id = uuid.UUID(user_id_str)
    task_id = self.request.id or "export"

    storage.ensure_bucket(storage.EXPORTS_BUCKET, public=False)

    with SyncSession() as session:
        data, filename, content_type = export_service.generate_export_bytes(
            session, org_id, project_id, export_format
        )
        path = f"{org_id_str}/exports/{task_id}/{filename}"
        storage.upload_bytes(storage.EXPORTS_BUCKET, path, data, content_type=content_type, upsert=True)

        ev = EventLog(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            event_type="export.generated",
            entity_type="project",
            entity_id=project_id,
            payload={"format": export_format, "storage_path": path, "filename": filename},
        )
        session.add(ev)
        session.commit()

    return {
        "org_id": org_id_str,
        "bucket": storage.EXPORTS_BUCKET,
        "path": path,
        "filename": filename,
        "content_type": content_type,
    }
