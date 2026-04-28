"""Plan service: upload PDFs, list sheets, query processing status.

This module is responsible for creating the DB records and uploading the raw PDF
to Supabase Storage. Actual PDF parsing and sheet extraction runs asynchronously
in the ``pdf_processing`` Celery task.
"""

from __future__ import annotations

import asyncio
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, delete as sa_delete, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.sheet import Sheet
from app.models.project import Project
from app.services.event_service import log_event
from app.middleware.error_handler import AppException, NotFoundException
from app.utils import storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SheetSummary:
    """Lightweight sheet row for listing — excludes ``text_content`` and ``vector_snap_segments`` blobs."""

    id: uuid.UUID
    plan_id: uuid.UUID
    project_id: uuid.UUID
    page_number: int
    sheet_name: str | None
    scale_value: float | None
    scale_unit: str | None
    scale_label: str | None
    scale_source: str | None
    width_px: int | None
    height_px: int | None
    thumbnail_path: str | None
    created_at: datetime
    vector_snap_segment_count: int


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
) -> list[SheetSummary]:
    """List sheets for a project without loading ``text_content`` or ``vector_snap_segments`` JSON."""
    segment_count_expr = case(
        (Sheet.vector_snap_segments.is_(None), 0),
        (
            func.jsonb_typeof(Sheet.vector_snap_segments) == literal("array"),
            func.jsonb_array_length(Sheet.vector_snap_segments),
        ),
        else_=0,
    ).label("segment_count")

    stmt = (
        select(
            Sheet.id,
            Sheet.plan_id,
            Sheet.project_id,
            Sheet.page_number,
            Sheet.sheet_name,
            Sheet.scale_value,
            Sheet.scale_unit,
            Sheet.scale_label,
            Sheet.scale_source,
            Sheet.width_px,
            Sheet.height_px,
            Sheet.thumbnail_path,
            Sheet.created_at,
            segment_count_expr,
        )
        .where(Sheet.org_id == org_id, Sheet.project_id == project_id)
        .order_by(Sheet.plan_id, Sheet.page_number)
    )
    result = await db.execute(stmt)
    return [
        SheetSummary(
            id=row.id,
            plan_id=row.plan_id,
            project_id=row.project_id,
            page_number=row.page_number,
            sheet_name=row.sheet_name,
            scale_value=row.scale_value,
            scale_unit=row.scale_unit,
            scale_label=row.scale_label,
            scale_source=row.scale_source,
            width_px=row.width_px,
            height_px=row.height_px,
            thumbnail_path=row.thumbnail_path,
            created_at=row.created_at,
            vector_snap_segment_count=int(row.segment_count or 0),
        )
        for row in result.all()
    ]


def sheet_thumbnail_signed_url(thumbnail_path: str | None) -> str | None:
    """Signed GET URL for a thumbnail object path (no DB / ORM)."""
    if not thumbnail_path:
        return None
    return storage.signed_url(storage.THUMBNAILS_BUCKET, thumbnail_path)


def sheet_thumbnail_url(sheet: Sheet) -> str | None:
    return sheet_thumbnail_signed_url(sheet.thumbnail_path)


#: Max sheet IDs per ``POST .../sheets/thumbnail-urls`` request.
MAX_THUMBNAIL_URL_BATCH = 100
#: Concurrent Supabase sign calls per batch (sync client; use thread offload).
_THUMBNAIL_SIGN_CONCURRENCY = 16


async def resolve_thumbnail_urls_for_sheets(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    sheet_ids: list[uuid.UUID],
) -> dict[str, str | None]:
    """Load thumbnail paths for the given sheet ids and return signed URLs (parallel, bounded)."""
    if len(sheet_ids) > MAX_THUMBNAIL_URL_BATCH:
        raise AppException(
            code="THUMBNAIL_BATCH_TOO_LARGE",
            message=f"At most {MAX_THUMBNAIL_URL_BATCH} sheet_ids per request",
            status_code=400,
        )
    unique_ids = list(dict.fromkeys(sheet_ids))
    if not unique_ids:
        return {}

    stmt = (
        select(Sheet.id, Sheet.thumbnail_path)
        .where(
            Sheet.org_id == org_id,
            Sheet.project_id == project_id,
            Sheet.id.in_(unique_ids),
        )
    )
    rows = list((await db.execute(stmt)).all())
    found: dict[uuid.UUID, str | None] = {r.id: r.thumbnail_path for r in rows}
    if len(found) != len(unique_ids):
        raise AppException(
            code="SHEET_IDS_INVALID",
            message="One or more sheet ids are missing or not in this project",
            status_code=404,
        )

    sem = asyncio.Semaphore(_THUMBNAIL_SIGN_CONCURRENCY)

    async def _sign(sid: uuid.UUID, path: str | None) -> tuple[str, str | None]:
        if not path:
            return str(sid), None
        async with sem:
            url = await asyncio.to_thread(sheet_thumbnail_signed_url, path)
        return str(sid), url

    pairs = await asyncio.gather(*[_sign(sid, found[sid]) for sid in unique_ids])
    return dict(pairs)


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
    plan.processing_substep = None
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


async def delete_plan(
    db: AsyncSession,
    org_id: uuid.UUID,
    plan_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> None:
    """Permanently delete a plan, its sheets/measurements (DB cascade), and storage files.

    Refuses to delete the project's last plan: every project must have at least one
    drawing while it has measurements/scale tied to a sheet. Callers should delete the
    project itself if they truly want to remove everything.
    """
    plan = await get_plan(db, org_id, plan_id)

    remaining = await db.execute(
        select(func.count(Plan.id)).where(
            Plan.org_id == org_id, Plan.project_id == plan.project_id
        )
    )
    plan_count = int(remaining.scalar_one())
    if plan_count <= 1:
        raise AppException(
            code="LAST_PLAN_REQUIRED",
            message="Each project must keep at least one plan",
            status_code=400,
        )

    thumb_rows = await db.execute(
        select(Sheet.thumbnail_path).where(
            Sheet.org_id == org_id, Sheet.plan_id == plan_id
        )
    )
    thumb_paths = [t for (t,) in thumb_rows.all() if t]
    plan_path = plan.storage_path
    project_id = plan.project_id
    filename = plan.filename

    await db.execute(
        sa_delete(Plan).where(Plan.id == plan_id, Plan.org_id == org_id)
    )
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        project_id=project_id,
        event_type="plan.deleted",
        entity_type="plan",
        entity_id=plan_id,
        payload={"filename": filename},
    )

    # Storage cleanup is best-effort; DB row is already gone, so failures here just
    # leave orphaned blobs. Log loudly so they can be reclaimed by a sweeper later.
    try:
        if plan_path:
            storage.remove_files(storage.PLANS_BUCKET, [plan_path])
    except Exception as e:  # pragma: no cover - storage backend is mocked in tests
        logger.error("Failed to remove plan PDF for %s: %s", plan_id, e)
    try:
        if thumb_paths:
            storage.remove_files(storage.THUMBNAILS_BUCKET, thumb_paths)
    except Exception as e:  # pragma: no cover
        logger.error("Failed to remove %d thumbnails for plan %s: %s", len(thumb_paths), plan_id, e)
