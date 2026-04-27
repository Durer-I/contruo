"""Celery task: extract pages, sheet names, thumbnails, and text layer from a plan PDF.

Runs asynchronously so uploads return instantly. Updates the plan row with progress
after each page so the frontend can poll for "Processing page X of Y" status.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.plan import Plan
from app.models.sheet import Sheet
from app.tasks.celery_app import celery_app
from app.utils import storage
from app.utils.pdf import extract_pdf
from app.utils.scale_detect import detect_scale

logger = logging.getLogger(__name__)

#: Sheet rows committed per transaction during the persist phase (after PDF extract).
SHEET_INSERT_CHUNK = 20

#: Avoid one huge INSERT/commit (timeouts on pooler / long locks) for large drawings.
_MAX_TEXT_CHARS_PER_SHEET = 2_000_000
#: Still plenty for snap; full extract may collect more in memory during PDF parse.
_MAX_VECTOR_SEGMENTS_PER_SHEET = 12_000


def _sheet_text_for_db(raw: str | None) -> str | None:
    if not raw:
        return None
    if len(raw) <= _MAX_TEXT_CHARS_PER_SHEET:
        return raw
    return raw[: _MAX_TEXT_CHARS_PER_SHEET]


def _sheet_vectors_for_db(segments: list | None) -> list | None:
    if not segments:
        return None
    if len(segments) <= _MAX_VECTOR_SEGMENTS_PER_SHEET:
        return segments
    return segments[:_MAX_VECTOR_SEGMENTS_PER_SHEET]


def _sync_database_url(url: str) -> str:
    """Celery tasks are synchronous; asyncpg is async-only so swap it for psycopg v3.

    psycopg (v3) is declared in requirements.txt for worker use. SQLAlchemy picks
    the right driver from the ``+psycopg`` scheme.
    """
    u = url.strip()
    if u.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + u.removeprefix("postgresql+asyncpg://")
    if u.startswith("postgresql://"):
        return "postgresql+psycopg://" + u.removeprefix("postgresql://")
    if u.startswith("postgres://"):
        return "postgresql+psycopg://" + u.removeprefix("postgres://")
    return u


_settings = get_settings()
#: Sync engine dedicated to the Celery worker. Kept module-level so multiple invocations
#: reuse the connection pool.
_sync_engine = create_engine(
    _sync_database_url(_settings.database_url),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SyncSession = sessionmaker(bind=_sync_engine, expire_on_commit=False, class_=Session)


def _mark_error(plan_id: uuid.UUID, message: str) -> None:
    with SyncSession() as session:
        session.execute(
            update(Plan)
            .where(Plan.id == plan_id)
            .values(status="error", error_message=message[:500], processing_substep=None)
        )
        session.commit()


@celery_app.task(
    name="pdf_processing.process_plan",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def process_plan(self, plan_id_str: str) -> dict:
    """Process an uploaded plan PDF.

    Steps:
      1. Load the plan row and verify status == 'processing'.
      2. Download the PDF from Supabase Storage.
      3. Use PyMuPDF to extract page count, text, and thumbnails per page.
      4. Persist ``sheets`` rows, upload thumbnails, update the plan progress.
      5. Set plan.status = 'ready' on success, 'error' on failure.
    """
    plan_id = uuid.UUID(plan_id_str)

    try:
        with SyncSession() as session:
            plan = session.get(Plan, plan_id)
            if not plan:
                logger.warning("process_plan: plan %s not found", plan_id)
                return {"status": "not_found"}
            org_id = plan.org_id
            project_id = plan.project_id
            storage_path = plan.storage_path

            # Clear any existing sheets (in case this is a retry).
            session.execute(Sheet.__table__.delete().where(Sheet.plan_id == plan.id))
            session.execute(
                update(Plan)
                .where(Plan.id == plan_id)
                .values(
                    status="processing",
                    processed_pages=0,
                    error_message=None,
                    processing_substep=None,
                )
            )
            session.commit()
    except Exception as e:
        logger.exception("Failed to initialize plan processing")
        _mark_error(plan_id, str(e))
        return {"status": "error", "message": str(e)}

    try:
        pdf_bytes = storage.download_bytes(storage.PLANS_BUCKET, storage_path)
    except Exception as e:
        logger.exception("Failed to download plan PDF from storage")
        _mark_error(plan_id, f"Download failed: {e}")
        return {"status": "error", "message": str(e)}

    def _progress(processed: int, total: int) -> None:
        # Incremental progress checkpoint so the UI can show "Processing page X of Y".
        try:
            with SyncSession() as s:
                s.execute(
                    update(Plan)
                    .where(Plan.id == plan_id)
                    .values(
                        processed_pages=processed,
                        page_count=total,
                        processing_substep="extract",
                    )
                )
                s.commit()
        except Exception:
            logger.exception("Progress update failed (non-fatal)")

    def _persist_progress(saved: int, total_pages: int) -> None:
        """Second-phase progress: sheets written to DB (0 .. total_pages)."""
        try:
            with SyncSession() as s:
                s.execute(
                    update(Plan)
                    .where(Plan.id == plan_id)
                    .values(
                        processed_pages=saved,
                        page_count=total_pages,
                        processing_substep="persist",
                    )
                )
                s.commit()
        except Exception:
            logger.exception("Persist progress update failed (non-fatal)")

    try:
        result = extract_pdf(pdf_bytes, on_page=_progress)
    except Exception as e:
        logger.exception("PDF extraction failed")
        _mark_error(plan_id, f"PDF parse failed: {e}")
        return {"status": "error", "message": str(e)}

    # Persist sheets and upload thumbnails (chunked DB commits + progress for UI).
    try:
        storage.ensure_bucket(storage.THUMBNAILS_BUCKET, public=False)
        total_pages = result.page_count
        _persist_progress(0, total_pages)

        with SyncSession() as session:
            batch: list[dict] = []
            pages = list(result.pages)
            for idx, page in enumerate(pages):
                hint = detect_scale(
                    page.text_content or "", pdf_metadata=result.metadata
                )
                thumb_path = None
                if page.thumbnail_png:
                    thumb_path = storage.thumbnail_storage_path(
                        org_id, plan_id, page.page_number
                    )
                    try:
                        storage.upload_bytes(
                            storage.THUMBNAILS_BUCKET,
                            thumb_path,
                            page.thumbnail_png,
                            content_type="image/png",
                            upsert=True,
                        )
                    except Exception:
                        logger.exception("Thumbnail upload failed for page %s", page.page_number)
                        thumb_path = None

                batch.append(
                    {
                        "id": uuid.uuid4(),
                        "org_id": org_id,
                        "plan_id": plan_id,
                        "project_id": project_id,
                        "page_number": page.page_number,
                        "sheet_name": page.sheet_name,
                        "width_px": page.width_px,
                        "height_px": page.height_px,
                        "thumbnail_path": thumb_path,
                        "text_content": _sheet_text_for_db(page.text_content),
                        "scale_value": hint.scale_value if hint else None,
                        "scale_unit": hint.scale_unit if hint else None,
                        "scale_label": (hint.scale_label[:100] if hint else None),
                        "scale_source": "auto" if hint else None,
                        "vector_snap_segments": _sheet_vectors_for_db(
                            page.vector_snap_segments or None
                        ),
                    }
                )
                flush_batch = len(batch) >= SHEET_INSERT_CHUNK or idx == len(pages) - 1
                if flush_batch and batch:
                    session.bulk_insert_mappings(Sheet, batch)
                    session.commit()
                    saved = idx + 1
                    _persist_progress(saved, total_pages)
                    batch = []

            logger.info(
                "All sheets inserted for plan %s; marking ready (%s pages)",
                plan_id,
                result.page_count,
            )
            session.execute(
                update(Plan)
                .where(Plan.id == plan_id)
                .values(
                    status="ready",
                    page_count=result.page_count,
                    processed_pages=result.page_count,
                    error_message=None,
                    processing_substep=None,
                )
            )
            session.commit()
            logger.info("Plan %s marked ready", plan_id)
    except Exception as e:
        logger.exception("Failed to persist processed sheets")
        _mark_error(plan_id, f"Persist failed: {e}")
        return {"status": "error", "message": str(e)}

    logger.info("Processed plan %s (%s pages)", plan_id, result.page_count)
    return {"status": "ready", "page_count": result.page_count}
