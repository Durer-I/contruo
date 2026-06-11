"""AI Auto-Takeoff Celery pipeline (Sprint AI-01 scaffolding).

Chained tasks model the pipeline (see ``ai_run_service.PIPELINE_STAGES``):

1. ``ai_pipeline.start_ai_run`` -- transition queued -> running, acquire the
   per-plan advisory lock, broadcast the status change.
2. ``ai_pipeline.stage_classification`` -- AI-02 (sheet text + OpenAI classification/naming).
3. ``ai_pipeline.stage_schedules_legends`` -- AI-03.
4. ``ai_pipeline.stage_element_detection`` -- AI-06/AI-07/AI-08.
5. ``ai_pipeline.stage_resolver_and_layer_write`` -- AI-04/AI-05.
6. ``ai_pipeline.finalize_ai_run`` -- transition to completed/failed, release
   lock, broadcast final status.

Standalone ``POST .../auto-name-sheets`` queues ``reextract_plan_titles``, which
uses the same sheet-text LLM path as Stage 2.

Each stage:

* Sets the active ``ai_run_id`` ContextVar so any model call inside the stage
  attributes its cost to this run.
* Sets the sync session factory ContextVar so cost writes find a DB session.
* Writes a ``record_stage_timing_sync`` entry capturing duration + cache hit.
* Catches its own exceptions, transitions the run to ``failed``, releases the
  lock, and stops the chain (subsequent stages see the failed state and skip).

In AI-01 every stage body is intentionally empty -- the framework runs end to
end and emits a clean multi-stage summary, but no detection happens. AI-02+
fill in each ``_stage_*_body`` without touching the chain ordering.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from celery import chain
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.middleware.error_handler import request_id_ctx
from app.models.ai_run import AiRun
from app.models.plan import Plan
from app.models.sheet import Sheet
from app.services import (
    ai_cache,
    ai_legend_detector,
    ai_legend_extractor,
    ai_models,
    ai_run_service,
    ai_schedule_extractor,
    ai_sheet_classifier,
    ai_sheet_filter,
    ai_sheet_text_llm,
    ai_tag_column,
    ai_title_block,
    liveblocks_service,
)
from app.tasks.celery_app import celery_app
from app.utils import storage

from app.services.ai_title_block import _sheet_eligible_for_auto_name

try:
    import fitz  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover -- declared in requirements.txt
    fitz = None

logger = logging.getLogger(__name__)

#: Sheet classification cache version lives in ``ai_sheet_text_llm.SHEET_TEXT_CLASSIFY_VERSION``.
#: AI-03 stage version. Bumped when the schedule extractor / tag-column
#: scorer / legend detector algorithm changes in a backward-incompatible way.
#: The model version (vision + LLM) is captured separately by the cache so a
#: pure-code change here invalidates cleanly without forcing a model swap.
SCHEDULES_LEGENDS_VERSION = "v3"


# ─── Sync engine (shared with pdf_processing pattern) ────────────────────────


def _sync_database_url(url: str) -> str:
    """Celery tasks are sync; swap asyncpg -> psycopg v3."""
    u = url.strip()
    if u.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + u.removeprefix("postgresql+asyncpg://")
    if u.startswith("postgresql://"):
        return "postgresql+psycopg://" + u.removeprefix("postgresql://")
    if u.startswith("postgres://"):
        return "postgresql+psycopg://" + u.removeprefix("postgres://")
    return u


_settings = get_settings()
_sync_engine = create_engine(
    _sync_database_url(_settings.database_url),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SyncSession = sessionmaker(bind=_sync_engine, expire_on_commit=False, class_=Session)


# ─── Telemetry ───────────────────────────────────────────────────────────────


def _log_ai_event(level: int, msg: str, /, **fields: Any) -> None:
    """Structured-log helper. ``ai_pipeline`` tag makes it easy to filter."""
    fields.setdefault("tag", "ai_pipeline")
    payload = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.log(level, "%s %s", msg, payload)


def _log_ai_failure(
    *,
    ai_run_id: uuid.UUID | str,
    stage: str,
    error: BaseException,
) -> None:
    """Log a stage failure with the metadata Sentry-style backends expect.

    Sentry SDK is not installed in AI-01; when it is wired we'll add a
    ``capture_exception`` call here behind a feature flag.
    """
    logger.exception(
        "ai_pipeline_failure ai_run_id=%s stage=%s error_type=%s message=%s",
        ai_run_id,
        stage,
        type(error).__name__,
        str(error)[:300],
    )


# ─── Pipeline configuration ──────────────────────────────────────────────────


PIPELINE_STAGES = ai_run_service.PIPELINE_STAGES  # re-export for convenience
TOTAL_STAGES = len(PIPELINE_STAGES)


def _broadcast_status(
    *,
    ai_run_id: uuid.UUID,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    status: str,
    stage: str | None = None,
    stage_index: int | None = None,
    error_message: str | None = None,
) -> None:
    """Push an ``ai_run.status_changed`` event into the project's Liveblocks room."""
    room = liveblocks_service.collaboration_room_id(org_id, project_id)
    payload: dict[str, Any] = {
        "ai_run_id": str(ai_run_id),
        "status": status,
        "total_stages": TOTAL_STAGES,
    }
    if stage is not None:
        payload["stage"] = stage
    if stage_index is not None:
        payload["stage_index"] = stage_index
    if error_message:
        payload["error_message"] = error_message[:200]
    liveblocks_service.broadcast_event_sync(
        room_id=room, event_type="ai_run.status_changed", data=payload
    )


def _load_run_context(
    session: Session, ai_run_id: uuid.UUID
) -> tuple[AiRun, Plan]:
    run = session.get(AiRun, ai_run_id)
    if not run:
        raise RuntimeError(f"ai_run {ai_run_id} not found")
    plan = session.get(Plan, run.plan_id)
    if not plan:
        raise RuntimeError(f"plan {run.plan_id} not found")
    return run, plan


# ─── Stage runner ────────────────────────────────────────────────────────────


def _run_stage(
    *,
    ai_run_id_str: str,
    stage: str,
    body: Callable[[Session, AiRun, Plan], dict[str, Any] | None],
) -> str:
    """Execute one pipeline stage with telemetry, cost binding, and error handling.

    ``body`` does the actual work and returns a metadata dict (e.g.
    ``{"cache_hit": True}``). Stage timing + cache_hit flag are persisted
    automatically. Any exception transitions the run to ``failed`` and stops
    the chain by re-raising (Celery will mark downstream tasks as failed in
    their own check via ``_short_circuit_if_terminal``).
    """
    ai_run_id = uuid.UUID(ai_run_id_str)
    started = datetime.now(timezone.utc)
    perf_start = time.perf_counter()

    cost_run_token = ai_models.set_active_ai_run(ai_run_id)
    factory_token = ai_models.set_sync_session_factory(SyncSession)
    try:
        with SyncSession() as session:
            run, plan = _load_run_context(session, ai_run_id)
            if run.status in ("completed", "failed", "cancelled"):
                _log_ai_event(
                    logging.INFO,
                    "stage_short_circuit",
                    ai_run_id=ai_run_id,
                    stage=stage,
                    status=run.status,
                )
                return ai_run_id_str
            metadata = body(session, run, plan) or {}

        finished = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - perf_start) * 1000)
        with SyncSession() as session:
            ai_run_service.record_stage_timing_sync(
                session,
                ai_run_id=ai_run_id,
                stage=stage,
                duration_ms=duration_ms,
                cache_hit=bool(metadata.get("cache_hit", False)),
                started_at=started,
                finished_at=finished,
            )
            run = session.get(AiRun, ai_run_id)
            assert run is not None
            org_id = run.org_id
            project_id = run.project_id
            stage_index = (
                PIPELINE_STAGES.index(stage) + 1 if stage in PIPELINE_STAGES else None
            )

        _broadcast_status(
            ai_run_id=ai_run_id,
            org_id=org_id,
            project_id=project_id,
            status="running",
            stage=stage,
            stage_index=stage_index,
        )
        _log_ai_event(
            logging.INFO,
            "stage_completed",
            ai_run_id=ai_run_id,
            stage=stage,
            duration_ms=duration_ms,
            cache_hit=metadata.get("cache_hit", False),
        )
        return ai_run_id_str
    except Exception as exc:
        finished = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - perf_start) * 1000)
        _log_ai_failure(ai_run_id=ai_run_id, stage=stage, error=exc)
        try:
            with SyncSession() as session:
                ai_run_service.record_stage_timing_sync(
                    session,
                    ai_run_id=ai_run_id,
                    stage=stage,
                    duration_ms=duration_ms,
                    cache_hit=False,
                    started_at=started,
                    finished_at=finished,
                    error=str(exc),
                )
                ai_run_service.release_sheet_lock_sync(
                    session, plan_id=_get_plan_id(session, ai_run_id), sheet_id=None
                )
                ai_run_service.finalize_run_sync(
                    session,
                    ai_run_id=ai_run_id,
                    status="failed",
                    error_message=f"{stage}: {exc}",
                )
                run = session.get(AiRun, ai_run_id)
                if run is not None:
                    _broadcast_status(
                        ai_run_id=ai_run_id,
                        org_id=run.org_id,
                        project_id=run.project_id,
                        status="failed",
                        stage=stage,
                        error_message=str(exc),
                    )
        except Exception:
            logger.exception(
                "Failed to record stage failure for run %s stage %s", ai_run_id, stage
            )
        raise
    finally:
        ai_models.reset_active_ai_run(cost_run_token)
        ai_models.reset_sync_session_factory(factory_token)


def _get_plan_id(session: Session, ai_run_id: uuid.UUID) -> uuid.UUID:
    pid = session.execute(
        select(AiRun.plan_id).where(AiRun.id == ai_run_id)
    ).scalar_one()
    return pid


# ─── Tasks ───────────────────────────────────────────────────────────────────


@celery_app.task(
    name="ai_pipeline.start_ai_run",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def start_ai_run(self, ai_run_id_str: str) -> str:
    """Transition queued -> running, acquire the per-plan advisory lock,
    and announce the run start to other users in the project.
    """
    ai_run_id = uuid.UUID(ai_run_id_str)
    request_id_ctx.set(f"ai_run:{ai_run_id}")
    try:
        with SyncSession() as session:
            run = session.get(AiRun, ai_run_id)
            if not run:
                raise RuntimeError(f"ai_run {ai_run_id} not found at start")
            if run.status not in ("queued", "running"):
                _log_ai_event(
                    logging.WARNING,
                    "start_ai_run_skipped",
                    ai_run_id=ai_run_id,
                    status=run.status,
                )
                return ai_run_id_str

            acquired = ai_run_service.acquire_sheet_lock_sync(
                session, plan_id=run.plan_id, sheet_id=None
            )
            if not acquired:
                # Surface a clean failure rather than enter a busy spin -- the
                # API guard normally catches this, but we belt-and-suspender it.
                ai_run_service.finalize_run_sync(
                    session,
                    ai_run_id=ai_run_id,
                    status="failed",
                    error_message="Another AI run holds the lock for this plan.",
                )
                _broadcast_status(
                    ai_run_id=ai_run_id,
                    org_id=run.org_id,
                    project_id=run.project_id,
                    status="failed",
                    error_message="lock contention",
                )
                return ai_run_id_str

            ai_run_service.update_status_sync(
                session, ai_run_id=ai_run_id, status="running"
            )
            session.refresh(run)
            org_id, project_id = run.org_id, run.project_id

        _broadcast_status(
            ai_run_id=ai_run_id,
            org_id=org_id,
            project_id=project_id,
            status="running",
            stage="start",
            stage_index=0,
        )
        _log_ai_event(
            logging.INFO,
            "ai_run_started",
            ai_run_id=ai_run_id,
            org_id=org_id,
            project_id=project_id,
        )
        return ai_run_id_str
    except Exception as exc:
        _log_ai_failure(ai_run_id=ai_run_id, stage="start", error=exc)
        try:
            with SyncSession() as session:
                run = session.get(AiRun, ai_run_id)
                if run is not None:
                    ai_run_service.release_sheet_lock_sync(
                        session, plan_id=run.plan_id, sheet_id=None
                    )
                    ai_run_service.finalize_run_sync(
                        session,
                        ai_run_id=ai_run_id,
                        status="failed",
                        error_message=f"start: {exc}",
                    )
                    _broadcast_status(
                        ai_run_id=ai_run_id,
                        org_id=run.org_id,
                        project_id=run.project_id,
                        status="failed",
                        stage="start",
                        error_message=str(exc),
                    )
        except Exception:
            logger.exception("Failed to clean up failed start for run %s", ai_run_id)
        raise


# ─── Stage no-op bodies (filled in by AI-02+) ────────────────────────────────


def _noop_stage(_session: Session, _run: AiRun, _plan: Plan) -> dict[str, Any]:
    """Default stage body: do nothing, report no cache hit."""
    return {"cache_hit": False}


# ─── AI-02: Stage classification body ───────────────────────────────────────


def _stage_classification_body(
    session: Session, run: AiRun, plan: Plan
) -> dict[str, Any]:
    """Stage 2: PyMuPDF structured text + batched OpenAI Responses per sheet."""
    settings = get_settings()
    sheets = list(
        session.execute(
            select(Sheet)
            .where(Sheet.plan_id == plan.id)
            .order_by(Sheet.page_number)
        )
        .scalars()
        .all()
    )
    if not sheets:
        return {"cache_hit": True}

    pdf_bytes = storage.download_bytes(storage.PLANS_BUCKET, plan.storage_path)

    eligible = {
        s.id: _sheet_eligible_for_auto_name(s, overwrite_manual=False) for s in sheets
    }
    cache_hits, llm_by_page, _rows = ai_sheet_text_llm.execute_sheet_text_llm_for_plan(
        session,
        org_id=run.org_id,
        sheets=sheets,
        pdf_bytes=pdf_bytes,
        sheet_eligible_for_names=eligible,
    )

    counters = ai_sheet_classifier.ClassificationCounters()
    for sheet in sheets:
        idx = int(sheet.page_number or 1) - 1
        item = llm_by_page.get(idx)
        if item:
            num_str = item.get("sheet_number")
            num_clean = (str(num_str).strip() if num_str is not None else "") or None
            discipline = ai_sheet_classifier.infer_discipline_from_sheet_number(
                num_clean
            )
            if discipline is None:
                discipline = "other"
            try:
                conf = float(item.get("confidence") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            st_llm = item.get("sheet_type")
            sheet_type = ai_sheet_text_llm.coerce_sheet_type(
                st_llm if isinstance(st_llm, str) else None
            )
            cat = item.get("category")
            cat_str = str(cat).strip() if cat is not None else None
            r = ai_sheet_classifier.ClassificationResult(
                sheet_id=sheet.id,
                discipline=discipline,
                sheet_type=sheet_type,
                confidence=conf,
                method="text_llm",
                notes="",
            )
            counters.add(
                r,
                low_threshold=settings.ai_classification_confidence_threshold,
                category=cat_str or None,
            )
        else:
            r = ai_sheet_classifier.ClassificationResult(
                sheet_id=sheet.id,
                discipline="other",
                sheet_type="other",
                confidence=0.0,
                method="text_llm",
                notes="no_llm_response",
            )
            counters.add(
                r,
                low_threshold=settings.ai_classification_confidence_threshold,
                category=None,
            )

    ai_run_service.merge_summary_jsonb_sync(
        session,
        ai_run_id=run.id,
        payload={"classification": counters.as_summary()},
    )
    ai_run_service.update_summary_counters_sync(
        session,
        ai_run_id=run.id,
        deltas={
            "stage_2_total_sheets": counters.total,
            "stage_2_lexical": counters.lexical_count,
            "stage_2_vision": counters.vision_count,
            "stage_2_text_llm": counters.text_llm_count,
            "stage_2_low_confidence": counters.low_confidence_count,
            "stage_2_cache_hits": cache_hits,
        },
    )
    return {"cache_hit": cache_hits == len(sheets)}


@celery_app.task(name="ai_pipeline.stage_classification", bind=True, acks_late=True)
def stage_classification(self, ai_run_id_str: str) -> str:
    return _run_stage(
        ai_run_id_str=ai_run_id_str,
        stage="classification",
        body=_stage_classification_body,
    )


# ─── AI-03: Stage schedules + legends body ───────────────────────────────────


def _stage_schedules_legends_body(
    session: Session, run: AiRun, plan: Plan
) -> dict[str, Any]:
    """Stage 3a: extract schedule tables + legend symbols on the relevant sheets.

    Pipeline:

    1. Filter sheets by ``sheet_name`` keyword (``ai_sheet_filter``). The
       AI-02 classifier output is intentionally NOT used as a gate here --
       its accuracy issues are tracked under AI-03c, and the prototype
       (``AI/controller/title.py``) proves keyword filtering is the right
       choice for Stage 3a.
    2. Download the plan PDF once; reuse the same bytes for pdfplumber
       (table / rect detection) and PyMuPDF (legend cropping).
    3. Per-sheet content-hash cache (separate keys for schedules + legends).
       On hit: skip extraction + LLM; persistence still runs (idempotent
       primary legend PNG upload, fresh DB rows tied to *this* ``ai_run_id``).
    4. Persist ``extracted_schedules`` + ``extracted_legends`` rows. (Scale /
       rotation variant assets and ``extracted_legend_variants`` are deferred.)
       Failures on individual sheets are
       logged and swallowed -- one bad sheet does not fail the stage.
    """
    schedule_sheets = ai_sheet_filter.select_schedule_sheets(session, plan_id=plan.id)
    legend_sheets = ai_sheet_filter.select_legend_sheets(session, plan_id=plan.id)

    if not schedule_sheets and not legend_sheets:
        ai_run_service.merge_summary_jsonb_sync(
            session,
            ai_run_id=run.id,
            payload={
                "schedules_legends": {
                    "schedule_sheets": 0,
                    "legend_sheets": 0,
                    "skipped": "no_matching_sheets",
                }
            },
        )
        return {"cache_hit": True}

    try:
        pdf_bytes = storage.download_bytes(storage.PLANS_BUCKET, plan.storage_path)
    except Exception:
        logger.exception(
            "stage_schedules_legends: PDF download failed plan=%s", plan.id
        )
        raise

    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    try:
        import io as _io
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover -- declared in requirements.txt
        raise RuntimeError("pdfplumber is not installed") from exc

    model_versions = ai_models.model_versions_snapshot()
    schedules_model_version = (
        f"vision:{model_versions.get('vision', 'unknown')}|"
        f"schedules_llm:{_settings.ai_schedules_llm_provider}:{_settings.ai_schedules_llm_model}"
    )
    _cleanup_part = "off"
    if _settings.ai_legend_cleanup_enabled:
        _cleanup_part = (
            f"{_settings.ai_legend_cleanup_llm_provider}:"
            f"{_settings.ai_legend_cleanup_llm_model}"
        )
    legends_model_version = (
        f"detector:{SCHEDULES_LEGENDS_VERSION}|cleanup:{_cleanup_part}"
    )

    counters = {
        "schedule_sheets": 0,
        "schedule_sheets_with_tables": 0,
        "schedules_extracted": 0,
        "schedule_vision_fallbacks": 0,
        "schedule_llm_tag_tiebreaks": 0,
        "schedule_cache_hits": 0,
        "legend_sheets": 0,
        "legend_sheets_with_symbols": 0,
        "legend_symbols_extracted": 0,
        "legend_variants_written": 0,
        "legend_cache_hits": 0,
    }

    fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    plumber_doc = pdfplumber.open(_io.BytesIO(pdf_bytes))
    try:
        for sheet in schedule_sheets:
            counters["schedule_sheets"] += 1
            try:
                _process_schedule_sheet(
                    session=session,
                    run=run,
                    plan=plan,
                    sheet=sheet,
                    fitz_doc=fitz_doc,
                    plumber_doc=plumber_doc,
                    pdf_bytes=pdf_bytes,
                    model_version=schedules_model_version,
                    counters=counters,
                )
            except Exception:
                logger.exception(
                    "stage_schedules_legends: per-sheet schedule failure sheet_id=%s",
                    sheet.id,
                )

        for sheet in legend_sheets:
            counters["legend_sheets"] += 1
            try:
                _process_legend_sheet(
                    session=session,
                    run=run,
                    plan=plan,
                    sheet=sheet,
                    fitz_doc=fitz_doc,
                    plumber_doc=plumber_doc,
                    pdf_bytes=pdf_bytes,
                    model_version=legends_model_version,
                    counters=counters,
                )
            except Exception:
                logger.exception(
                    "stage_schedules_legends: per-sheet legend failure sheet_id=%s",
                    sheet.id,
                )
    finally:
        try:
            plumber_doc.close()
        except Exception:  # pragma: no cover
            pass
        try:
            fitz_doc.close()
        except Exception:  # pragma: no cover
            pass

    ai_run_service.merge_summary_jsonb_sync(
        session,
        ai_run_id=run.id,
        payload={"schedules_legends": dict(counters)},
    )
    ai_run_service.update_summary_counters_sync(
        session,
        ai_run_id=run.id,
        deltas={
            "stage_3_schedule_sheets": counters["schedule_sheets"],
            "stage_3_schedules_extracted": counters["schedules_extracted"],
            "stage_3_legend_sheets": counters["legend_sheets"],
            "stage_3_legend_symbols": counters["legend_symbols_extracted"],
            "stage_3_legend_variants": counters["legend_variants_written"],
            "stage_3_schedule_cache_hits": counters["schedule_cache_hits"],
            "stage_3_legend_cache_hits": counters["legend_cache_hits"],
        },
    )

    total_sheets = counters["schedule_sheets"] + counters["legend_sheets"]
    total_hits = counters["schedule_cache_hits"] + counters["legend_cache_hits"]
    return {"cache_hit": total_sheets > 0 and total_hits == total_sheets}


def _process_schedule_sheet(
    *,
    session: Session,
    run: AiRun,
    plan: Plan,
    sheet: Sheet,
    fitz_doc: Any,
    plumber_doc: Any,
    pdf_bytes: bytes,
    model_version: str,
    counters: dict[str, int],
) -> None:
    page_index = (sheet.page_number or 1) - 1
    if page_index < 0 or page_index >= len(plumber_doc.pages):
        return

    sheet_hash = ai_cache.compute_sheet_content_hash(sheet, pdf_bytes=pdf_bytes)
    cached = ai_cache.cache_get(
        session,
        org_id=run.org_id,
        content_hash=sheet_hash,
        stage="schedules_v1",
        model_version=model_version,
    )

    plumber_page = plumber_doc.pages[page_index]
    fitz_page = fitz_doc.load_page(page_index)
    page_width = float(fitz_page.rect.width)
    page_height = float(fitz_page.rect.height)

    if cached:
        candidates = ai_schedule_extractor.deserialize_candidates(
            cached.get("candidates") or []
        )
        column_scores_serialized = cached.get("column_scores") or []
        counters["schedule_cache_hits"] += 1
    else:
        vision_factory = ai_schedule_extractor.render_page_for_vision_factory(
            fitz_page, dpi=_settings.ai_schedule_vision_dpi
        )
        try:
            vision_model = ai_models.get_vision_model()
        except Exception:
            vision_model = None
            logger.exception(
                "stage_schedules_legends: vision model factory failed; heuristic-only"
            )
        candidates = ai_schedule_extractor.extract_schedules_for_page(
            plumber_page=plumber_page,
            page_width=page_width,
            page_height=page_height,
            vision_model=vision_model,
            vision_image_bytes=vision_factory if vision_model else None,
        )
        column_scores_list: list[ai_tag_column.ColumnScores] = []
        for candidate in candidates:
            scores = ai_tag_column.score_columns(
                headers=candidate.headers,
                rows=candidate.rows,
                db=session,
                org_id=run.org_id,
            )
            column_scores_list.append(scores)
            if scores.used_llm:
                counters["schedule_llm_tag_tiebreaks"] += 1
            if candidate.extraction_method == "vision":
                counters["schedule_vision_fallbacks"] += 1
        column_scores_serialized = [
            {
                "tag_column_index": s.tag_column_index,
                "description_column_index": s.description_column_index,
                "quantity_column_index": s.quantity_column_index,
                "dimension_column_indexes": s.dimension_column_indexes,
                "material_column_index": s.material_column_index,
                "used_llm": s.used_llm,
                "notes": s.notes,
            }
            for s in column_scores_list
        ]
        ai_cache.cache_put(
            session,
            org_id=run.org_id,
            content_hash=sheet_hash,
            stage="schedules_v1",
            model_version=model_version,
            value={
                "candidates": ai_schedule_extractor.serialize_candidates(candidates),
                "column_scores": column_scores_serialized,
            },
        )

    if not candidates:
        return
    counters["schedule_sheets_with_tables"] += 1

    from app.models.extracted_schedule import ExtractedSchedule

    for candidate, scores_payload in zip(candidates, column_scores_serialized):
        if not isinstance(scores_payload, dict):
            scores_payload = {}
        row = ExtractedSchedule(
            org_id=run.org_id,
            ai_run_id=run.id,
            sheet_id=sheet.id,
            bbox_pdf=dict(candidate.bbox_pdf),
            tag_column_index=scores_payload.get("tag_column_index"),
            description_column_index=scores_payload.get("description_column_index"),
            quantity_column_index=scores_payload.get("quantity_column_index"),
            dimension_column_indexes=scores_payload.get("dimension_column_indexes"),
            material_column_index=scores_payload.get("material_column_index"),
            extracted_table_jsonb=candidate.as_table_jsonb(),
            extraction_method=candidate.extraction_method,
        )
        session.add(row)
        try:
            session.commit()
            counters["schedules_extracted"] += 1
        except Exception:
            session.rollback()
            logger.exception(
                "stage_schedules_legends: extracted_schedules insert failed sheet=%s",
                sheet.id,
            )


def _process_legend_sheet(
    *,
    session: Session,
    run: AiRun,
    plan: Plan,
    sheet: Sheet,
    fitz_doc: Any,
    plumber_doc: Any,
    pdf_bytes: bytes,
    model_version: str,
    counters: dict[str, int],
) -> None:
    page_index = (sheet.page_number or 1) - 1
    if page_index < 0 or page_index >= len(plumber_doc.pages):
        return

    sheet_hash = ai_cache.compute_sheet_content_hash(sheet, pdf_bytes=pdf_bytes)
    cached = ai_cache.cache_get(
        session,
        org_id=run.org_id,
        content_hash=sheet_hash,
        stage="legends_v1",
        model_version=model_version,
    )

    plumber_page = plumber_doc.pages[page_index]
    fitz_page = fitz_doc.load_page(page_index)

    if cached:
        counters["legend_cache_hits"] += 1
        # Fast-path on cache hit: skip detection + rendering + uploading;
        # write fresh DB rows pointing at the deterministic storage paths
        # the previous run already populated.
        persisted = ai_legend_extractor.persist_from_cached_metadata(
            db=session,
            cached=cached.get("persisted") or [],
            org_id=run.org_id,
            plan_id=plan.id,
            sheet_id=sheet.id,
            ai_run_id=run.id,
        )
    else:
        candidates = ai_legend_detector.detect_legend_symbols(plumber_page=plumber_page)
        if not candidates:
            ai_cache.cache_put(
                session,
                org_id=run.org_id,
                content_hash=sheet_hash,
                stage="legends_v1",
                model_version=model_version,
                value={
                    "candidates": [],
                    "persisted": [],
                },
            )
            return
        persisted = ai_legend_extractor.persist_legend_candidates(
            db=session,
            fitz_page=fitz_page,
            candidates=candidates,
            org_id=run.org_id,
            plan_id=plan.id,
            sheet_id=sheet.id,
            ai_run_id=run.id,
        )
        ai_cache.cache_put(
            session,
            org_id=run.org_id,
            content_hash=sheet_hash,
            stage="legends_v1",
            model_version=model_version,
            value={
                "candidates": ai_legend_detector.serialize_candidates(candidates),
                "persisted": [p.as_cached_dict() for p in persisted],
            },
        )


    if persisted:
        counters["legend_sheets_with_symbols"] += 1
        counters["legend_symbols_extracted"] += len(persisted)
        counters["legend_variants_written"] += sum(p.variant_count for p in persisted)


@celery_app.task(name="ai_pipeline.stage_schedules_legends", bind=True, acks_late=True)
def stage_schedules_legends(self, ai_run_id_str: str) -> str:
    return _run_stage(
        ai_run_id_str=ai_run_id_str,
        stage="schedules_legends",
        body=_stage_schedules_legends_body,
    )


@celery_app.task(name="ai_pipeline.stage_element_detection", bind=True, acks_late=True)
def stage_element_detection(self, ai_run_id_str: str) -> str:
    return _run_stage(
        ai_run_id_str=ai_run_id_str, stage="element_detection", body=_noop_stage
    )


@celery_app.task(
    name="ai_pipeline.stage_resolver_and_layer_write", bind=True, acks_late=True
)
def stage_resolver_and_layer_write(self, ai_run_id_str: str) -> str:
    return _run_stage(
        ai_run_id_str=ai_run_id_str,
        stage="resolver_and_layer_write",
        body=_noop_stage,
    )


@celery_app.task(name="ai_pipeline.finalize_ai_run", bind=True, acks_late=True)
def finalize_ai_run(self, ai_run_id_str: str) -> str:
    """Mark the run completed, release the lock, and broadcast a final status."""
    ai_run_id = uuid.UUID(ai_run_id_str)
    started = datetime.now(timezone.utc)
    perf_start = time.perf_counter()
    try:
        with SyncSession() as session:
            run = session.get(AiRun, ai_run_id)
            if not run:
                raise RuntimeError(f"ai_run {ai_run_id} not found at finalize")
            if run.status in ("failed", "cancelled"):
                _log_ai_event(
                    logging.INFO,
                    "finalize_skipped",
                    ai_run_id=ai_run_id,
                    status=run.status,
                )
                return ai_run_id_str
            ai_run_service.release_sheet_lock_sync(
                session, plan_id=run.plan_id, sheet_id=None
            )
            ai_run_service.finalize_run_sync(
                session, ai_run_id=ai_run_id, status="completed"
            )
            org_id, project_id = run.org_id, run.project_id

        finished = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - perf_start) * 1000)
        with SyncSession() as session:
            ai_run_service.record_stage_timing_sync(
                session,
                ai_run_id=ai_run_id,
                stage="finalize",
                duration_ms=duration_ms,
                cache_hit=False,
                started_at=started,
                finished_at=finished,
            )

        _broadcast_status(
            ai_run_id=ai_run_id,
            org_id=org_id,
            project_id=project_id,
            status="completed",
            stage="finalize",
            stage_index=TOTAL_STAGES,
        )
        _log_ai_event(
            logging.INFO,
            "ai_run_completed",
            ai_run_id=ai_run_id,
            duration_ms=duration_ms,
        )
        return ai_run_id_str
    except Exception as exc:
        _log_ai_failure(ai_run_id=ai_run_id, stage="finalize", error=exc)
        try:
            with SyncSession() as session:
                run = session.get(AiRun, ai_run_id)
                if run is not None:
                    ai_run_service.release_sheet_lock_sync(
                        session, plan_id=run.plan_id, sheet_id=None
                    )
                    ai_run_service.finalize_run_sync(
                        session,
                        ai_run_id=ai_run_id,
                        status="failed",
                        error_message=f"finalize: {exc}",
                    )
                    _broadcast_status(
                        ai_run_id=ai_run_id,
                        org_id=run.org_id,
                        project_id=run.project_id,
                        status="failed",
                        stage="finalize",
                        error_message=str(exc),
                    )
        except Exception:
            logger.exception("Failed to clean up finalize failure for %s", ai_run_id)
        raise


# ─── Pipeline prep: best-effort auto-name before ``start_ai_run`` ────────────


@celery_app.task(
    name="ai_pipeline.pipeline_prep_auto_name",
    bind=True,
    acks_late=True,
)
def pipeline_prep_auto_name(self, plan_id_str: str) -> str:
    """Reserved Celery task name; chain entry removed — Stage 2 owns naming."""
    return "prep_auto_name_skipped"



# ─── Public chain builder ────────────────────────────────────────────────────


def build_pipeline_chain(ai_run_id: uuid.UUID, plan_id: uuid.UUID):
    """Construct the Celery chain for an AI run.

    Order: ``start_ai_run`` (immutable) → classification → schedules/legends → … → finalize.

    Use ``build_pipeline_chain(run.id, run.plan_id).apply_async()`` from the API
    handler after commit. Recorded ``PIPELINE_STAGES`` / UI stage count unchanged.
    """
    s = str(ai_run_id)
    p = str(plan_id)
    return chain(
        start_ai_run.si(s),
        stage_classification.s(),
        stage_schedules_legends.s(),
        stage_element_detection.s(),
        stage_resolver_and_layer_write.s(),
        finalize_ai_run.s(),
    )


# ─── AI-02b: standalone auto-name-sheets task ────────────────────────────────


#: Celery retry delay (seconds) when the per-plan advisory lock is busy.
_AUTO_NAME_RETRY_DELAY_S = 5
#: Max retries on lock-busy. With backoff this caps wait at ~1 minute total
#: which is a reasonable bound: a typical re-extract finishes in <5s and any
#: contention should resolve far inside that window.
_AUTO_NAME_MAX_RETRIES = 5


@celery_app.task(
    name="ai_pipeline.reextract_plan_titles",
    bind=True,
    max_retries=_AUTO_NAME_MAX_RETRIES,
    default_retry_delay=_AUTO_NAME_RETRY_DELAY_S,
    acks_late=True,
)
def reextract_plan_titles_task(
    self, plan_id_str: str, overwrite_manual: bool = False
) -> dict[str, Any]:
    """Re-extract ``sheet_name`` + ``sheet_number`` for every sheet in a plan.

    Standalone task (NOT part of the AI Auto-Takeoff chain). Triggered by the
    ``POST /projects/{pid}/plans/{plan_id}/auto-name-sheets`` endpoint. Holds
    the same per-plan advisory lock the AI run uses, so an auto-name and an
    AI run on the same plan can't race the sheets table.

    On success: broadcasts ``sheets.auto_named`` into the project's
    Liveblocks room with the per-method counters so connected clients can
    refetch immediately. Polling in the workspace is the backstop.
    """
    plan_id = uuid.UUID(plan_id_str)
    request_id_ctx.set(f"auto_name:{plan_id}")
    started = datetime.now(timezone.utc)
    perf_start = time.perf_counter()

    settings = get_settings()
    if not settings.ai_auto_name_enabled:
        _log_ai_event(
            logging.WARNING,
            "auto_name_disabled",
            plan_id=plan_id,
        )
        return {"plan_id": str(plan_id), "skipped": "feature_disabled"}

    factory_token = ai_models.set_sync_session_factory(SyncSession)
    try:
        # Phase 1: load plan + acquire lock + download PDF.
        with SyncSession() as session:
            plan = session.get(Plan, plan_id)
            if not plan:
                raise RuntimeError(f"plan {plan_id} not found")
            if plan.status != "ready":
                _log_ai_event(
                    logging.WARNING,
                    "auto_name_plan_not_ready",
                    plan_id=plan_id,
                    status=plan.status,
                )
                return {"plan_id": str(plan_id), "skipped": "plan_not_ready"}

            acquired = ai_run_service.acquire_sheet_lock_sync(
                session, plan_id=plan_id, sheet_id=None
            )
            if not acquired:
                _log_ai_event(
                    logging.INFO,
                    "auto_name_lock_busy_retrying",
                    plan_id=plan_id,
                    retry_count=self.request.retries,
                )
                # Celery will re-call us after default_retry_delay.
                raise self.retry(exc=RuntimeError("plan lock busy"))

            org_id = plan.org_id
            project_id = plan.project_id
            storage_path = plan.storage_path

        try:
            try:
                pdf_bytes = storage.download_bytes(storage.PLANS_BUCKET, storage_path)
            except Exception as exc:
                _log_ai_failure(
                    ai_run_id=f"plan:{plan_id}",
                    stage="auto_name_download",
                    error=exc,
                )
                raise

            # Phase 2: per-sheet extraction + writes.
            with SyncSession() as session:
                plan = session.get(Plan, plan_id)
                if not plan:
                    raise RuntimeError(f"plan {plan_id} disappeared mid-task")
                counters = ai_title_block.reextract_titles_for_plan(
                    session,
                    plan,
                    pdf_bytes=pdf_bytes,
                    overwrite_manual=overwrite_manual,
                    llm_fallback=True,
                )
                session.commit()
        finally:
            # Always release the lock, even on failure inside the work block.
            try:
                with SyncSession() as session:
                    ai_run_service.release_sheet_lock_sync(
                        session, plan_id=plan_id, sheet_id=None
                    )
            except Exception:
                logger.exception(
                    "auto_name: release lock failed for plan=%s", plan_id
                )

        duration_ms = int((time.perf_counter() - perf_start) * 1000)
        _log_ai_event(
            logging.INFO,
            "auto_name_completed",
            plan_id=plan_id,
            duration_ms=duration_ms,
            **{f"counter_{k}": v for k, v in counters.as_summary().items() if isinstance(v, int)},
        )

        # Phase 3: broadcast for client refetch. Non-fatal on failure.
        try:
            room = liveblocks_service.collaboration_room_id(org_id, project_id)
            liveblocks_service.broadcast_event_sync(
                room_id=room,
                event_type="sheets.auto_named",
                data={
                    "plan_id": str(plan_id),
                    "duration_ms": duration_ms,
                    "counters": counters.as_summary(),
                },
            )
        except Exception:
            logger.exception(
                "auto_name: broadcast failed plan=%s (non-fatal)", plan_id
            )

        return {
            "plan_id": str(plan_id),
            "duration_ms": duration_ms,
            "started_at": started.isoformat(),
            "counters": counters.as_summary(),
        }
    except Exception as exc:
        # ``self.retry`` raises Retry, which we want to propagate untouched.
        from celery.exceptions import Retry  # local import keeps top-of-file lean

        if isinstance(exc, Retry):
            raise
        _log_ai_failure(ai_run_id=f"plan:{plan_id}", stage="auto_name", error=exc)
        # Best-effort lock release if we crashed before the finally block ran.
        try:
            with SyncSession() as session:
                ai_run_service.release_sheet_lock_sync(
                    session, plan_id=plan_id, sheet_id=None
                )
        except Exception:
            logger.exception(
                "auto_name: defensive lock release failed plan=%s", plan_id
            )
        raise
    finally:
        ai_models.reset_sync_session_factory(factory_token)


