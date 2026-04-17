"""Plan service: upload PDFs, list sheets, query processing status.

This module is responsible for creating the DB records and uploading the raw PDF
to Supabase Storage. Actual PDF parsing and sheet extraction runs asynchronously
in the ``pdf_processing`` Celery task.
"""

from __future__ import annotations

import uuid
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.sheet import Sheet
from app.models.project import Project
from app.services.event_service import log_event
from app.middleware.error_handler import AppException, NotFoundException
from app.utils import storage

logger = logging.getLogger(__name__)

#: Hard ceiling for uploaded plan PDFs. 200 MB accommodates large architectural sets.
#: Anything larger either has an embedded problem or isn't actually a plan.
MAX_PLAN_FILE_SIZE = 200 * 1024 * 1024


async def create_plan(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    *,
    filename: str,
    content: bytes,
    content_type: str | None = None,
) -> Plan:
    """Upload a PDF to Supabase Storage, create a `plans` row with status='processing',
    and queue the background processing task.

    Raises if the file is not a PDF, is over the size limit, or the project is missing.
    """
    if not filename.lower().endswith(".pdf"):
        raise AppException(code="INVALID_FILE_TYPE", message="Only PDF files are supported", status_code=400)

    if content_type and content_type.lower() not in ("application/pdf", "application/x-pdf"):
        raise AppException(code="INVALID_FILE_TYPE", message="File must be a PDF", status_code=400)

    if len(content) == 0:
        raise AppException(code="EMPTY_FILE", message="Uploaded file is empty", status_code=400)
    if len(content) > MAX_PLAN_FILE_SIZE:
        raise AppException(code="FILE_TOO_LARGE", message="Plan PDF must be under 200MB", status_code=400)

    # Cheap sanity check: PDFs start with "%PDF-".
    if not content.startswith(b"%PDF-"):
        raise AppException(code="INVALID_FILE_TYPE", message="File does not appear to be a valid PDF", status_code=400)

    # Verify the project exists in this org (RLS will also enforce, but we need a clean 404).
    stmt = select(Project).where(Project.id == project_id, Project.org_id == org_id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise NotFoundException("project", str(project_id))

    plan_id = uuid.uuid4()
    # Sanitize filename to avoid path traversal or weird storage keys.
    safe_name = filename.replace("/", "_").replace("\\", "_")
    path = storage.plan_storage_path(org_id, plan_id, safe_name)

    # Ensure buckets exist in development; idempotent in prod since they'll be created once.
    storage.ensure_bucket(storage.PLANS_BUCKET, public=False)
    storage.ensure_bucket(storage.THUMBNAILS_BUCKET, public=False)

    try:
        storage.upload_bytes(
            storage.PLANS_BUCKET,
            path,
            content,
            content_type="application/pdf",
            upsert=True,
        )
    except Exception as e:
        logger.exception("Failed to upload plan to storage")
        raise AppException(code="UPLOAD_FAILED", message=f"Failed to upload plan: {e}", status_code=500)

    plan = Plan(
        id=plan_id,
        org_id=org_id,
        project_id=project_id,
        filename=safe_name,
        storage_path=path,
        file_size=len(content),
        page_count=None,
        status="processing",
        processed_pages=0,
        uploaded_by=uploaded_by,
    )
    db.add(plan)
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=uploaded_by,
        project_id=project_id,
        event_type="plan.uploaded",
        entity_type="plan",
        entity_id=plan_id,
        payload={"filename": safe_name, "size": len(content)},
    )

    # Queue the processing task. Imported inside the function to avoid a hard dependency
    # between the API layer and Celery for unit tests that mock this out.
    try:
        from app.tasks.pdf_processing import process_plan

        process_plan.delay(str(plan_id))
    except Exception as e:  # pragma: no cover -- broker down should not block upload acceptance
        logger.error("Failed to queue PDF processing task for plan %s: %s", plan_id, e)

    return plan


async def get_plan(db: AsyncSession, org_id: uuid.UUID, plan_id: uuid.UUID) -> Plan:
    stmt = select(Plan).where(Plan.id == plan_id, Plan.org_id == org_id)
    plan = (await db.execute(stmt)).scalar_one_or_none()
    if not plan:
        raise NotFoundException("plan", str(plan_id))
    return plan


async def list_project_plans(
    db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID
) -> list[Plan]:
    stmt = (
        select(Plan)
        .where(Plan.org_id == org_id, Plan.project_id == project_id)
        .order_by(Plan.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_project_sheets(
    db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID
) -> list[Sheet]:
    stmt = (
        select(Sheet)
        .where(Sheet.org_id == org_id, Sheet.project_id == project_id)
        .order_by(Sheet.plan_id, Sheet.page_number)
    )
    return list((await db.execute(stmt)).scalars().all())


def sheet_thumbnail_url(sheet: Sheet) -> str | None:
    if not sheet.thumbnail_path:
        return None
    return storage.signed_url(storage.THUMBNAILS_BUCKET, sheet.thumbnail_path)


async def get_plan_document_signed_url(
    db: AsyncSession, org_id: uuid.UUID, plan_id: uuid.UUID
) -> tuple[str, int]:
    """Return a time-limited signed URL to download the plan PDF from Supabase Storage."""
    plan = await get_plan(db, org_id, plan_id)
    if not plan.storage_path:
        raise AppException(
            code="PLAN_NO_STORAGE",
            message="Plan has no storage path",
            status_code=500,
        )
    url = storage.signed_url(storage.PLANS_BUCKET, plan.storage_path)
    if not url:
        raise AppException(
            code="DOCUMENT_URL_FAILED",
            message="Could not generate a signed URL for this plan",
            status_code=503,
        )
    return url, storage.SIGNED_URL_EXPIRES_SEC


async def retry_plan(
    db: AsyncSession,
    org_id: uuid.UUID,
    plan_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> Plan:
    """Re-queue a failed plan for processing."""
    plan = await get_plan(db, org_id, plan_id)
    if plan.status not in ("error", "processing"):
        raise AppException(
            code="PLAN_NOT_RETRYABLE",
            message=f"Plan with status '{plan.status}' cannot be retried",
            status_code=400,
        )

    plan.status = "processing"
    plan.error_message = None
    plan.processed_pages = 0
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        project_id=plan.project_id,
        event_type="plan.retry",
        entity_type="plan",
        entity_id=plan.id,
    )

    try:
        from app.tasks.pdf_processing import process_plan

        process_plan.delay(str(plan_id))
    except Exception as e:  # pragma: no cover
        logger.error("Failed to queue retry for plan %s: %s", plan_id, e)

    return plan
