"""AI Auto-Takeoff Celery pipeline (Sprint AI-01 scaffolding).

Six chained tasks model the full pipeline:

1. ``ai_pipeline.start_ai_run`` -- transition queued -> running, acquire the
   per-plan advisory lock, broadcast the status change, hand off to stage 1.
2. ``ai_pipeline.stage_title_block`` -- AI-02b will populate. Today: no-op
   pass-through (the title-block work was reset for AI-02b; see
   ``sprints/ai/sprint-ai-02b.md``).
3. ``ai_pipeline.stage_classification`` -- AI-02.
4. ``ai_pipeline.stage_schedules_legends`` -- AI-03.
5. ``ai_pipeline.stage_element_detection`` -- AI-06/AI-07/AI-08.
6. ``ai_pipeline.stage_resolver_and_layer_write`` -- AI-04/AI-05.
7. ``ai_pipeline.finalize_ai_run`` -- transition to completed/failed, release
   lock, broadcast final status.

Each stage:

* Sets the active ``ai_run_id`` ContextVar so any model call inside the stage
  attributes its cost to this run.
* Sets the sync session factory ContextVar so cost writes find a DB session.
* Writes a ``record_stage_timing_sync`` entry capturing duration + cache hit.
* Catches its own exceptions, transitions the run to ``failed``, releases the
  lock, and stops the chain (subsequent stages see the failed state and skip).

In AI-01 every stage body is intentionally empty -- the framework runs end to
end and emits a clean six-stage summary, but no detection happens. AI-02+ will
fill in each ``_run_<stage>`` body without touching the chain wiring.
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
    ai_models,
    ai_run_service,
    ai_sheet_classifier,
    liveblocks_service,
)
from app.tasks.celery_app import celery_app
from app.utils import storage
from app.utils.pdf import render_thumbnail_for_classification

try:
    import fitz  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover -- declared in requirements.txt
    fitz = None

logger = logging.getLogger(__name__)


#: Stage versions baked into cache keys. Bump when the algorithm changes
#: in a way that would invalidate prior cache entries (e.g. a heuristic
#: refactor). The version is *separate* from the model version so a pure
#: code change can invalidate without forcing a model swap.
SHEET_CLASSIFY_VERSION = "lexical_v1"


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


# ─── AI-02b: Stage 1 (title block) body — placeholder ──────────────────────
#
# The auto-detection + manual-bbox flow shipped in AI-02 was reset so AI-02b
# can take a fresh swing at it. Until then, Stage 1 runs as a no-op and the
# pipeline proceeds straight into Stage 2 classification (which keys off
# ``sheets.sheet_name``, so missing titles just degrade lexical confidence
# without breaking the run). See ``sprints/ai/sprint-ai-02b.md`` for the
# replacement spec.


# ─── AI-02: Stage 2 (sheet classification) body ───────────────────────────────


def _stage_classification_body(
    session: Session, run: AiRun, plan: Plan
) -> dict[str, Any]:
    """Stage 2: lexical-first / vision-fallback classification of every sheet.

    Cache key is per-sheet content hash + ``SHEET_CLASSIFY_VERSION``. A re-run
    on unchanged sheets reads from cache (zero cost). Vision is invoked only
    on the bucket of (low-lexical-confidence AND interesting-sheet-type)
    sheets; cover/index/spec sheets are written from lexical even at low
    confidence.
    """
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

    model_version = ai_models.model_versions_snapshot().get("vision", "vision:unknown")

    lexical_results: list[ai_sheet_classifier.ClassificationResult] = []
    cache_hits = 0
    final_results: list[ai_sheet_classifier.ClassificationResult] = []
    needs_vision: list[ai_sheet_classifier.SheetForClassification] = []

    # First pass: try cache, then lexical.
    for sheet in sheets:
        sheet_hash = ai_cache.compute_sheet_content_hash(sheet)
        cached = ai_cache.cache_get(
            session,
            org_id=run.org_id,
            content_hash=sheet_hash,
            stage="classification",
            model_version=model_version,
        )
        if cached and {"discipline", "sheet_type"} <= cached.keys():
            try:
                conf = float(cached.get("confidence") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            cached_result = ai_sheet_classifier.ClassificationResult(
                sheet_id=sheet.id,
                discipline=str(cached["discipline"]),
                sheet_type=str(cached["sheet_type"]),
                confidence=conf,
                method=str(cached.get("method") or "lexical"),
                notes="cache",
            )
            cache_hits += 1
            final_results.append(cached_result)
            continue

        lexical = ai_sheet_classifier.classify_lexical(sheet.id, sheet.sheet_name)
        lexical_results.append(lexical)
        if ai_sheet_classifier.needs_vision_fallback(
            lexical, threshold=settings.ai_classification_confidence_threshold
        ):
            # Defer to the vision pass. Note: we still stash the lexical
            # guess so a vision failure falls back cleanly.
            needs_vision.append(
                ai_sheet_classifier.SheetForClassification(
                    sheet_id=sheet.id,
                    sheet_name=sheet.sheet_name,
                    content_hash=ai_cache.compute_sheet_content_hash(sheet),
                )
            )
        else:
            final_results.append(lexical)

    lexical_by_id = {r.sheet_id: r for r in lexical_results}
    sheet_by_id = {s.id: s for s in sheets}

    # Render thumbnails for the vision bucket (only if non-empty).
    if needs_vision:
        try:
            pdf_bytes = storage.download_bytes(
                storage.PLANS_BUCKET, plan.storage_path
            )
        except Exception:
            logger.exception(
                "stage_classification: PDF download failed plan=%s", plan.id
            )
            # Drop the vision bucket back to lexical to keep the pipeline moving.
            for s in needs_vision:
                final_results.append(lexical_by_id[s.sheet_id])
            needs_vision = []
            pdf_bytes = b""

        if pdf_bytes:
            if fitz is None:
                raise RuntimeError("PyMuPDF (fitz) is not installed")
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                rendered: list[ai_sheet_classifier.SheetForClassification] = []
                for s in needs_vision:
                    sheet_obj = sheet_by_id.get(s.sheet_id)
                    if sheet_obj is None:
                        continue
                    page_index = (sheet_obj.page_number or 1) - 1
                    if page_index < 0 or page_index >= doc.page_count:
                        final_results.append(lexical_by_id[s.sheet_id])
                        continue
                    try:
                        page = doc.load_page(page_index)
                        thumb = render_thumbnail_for_classification(page)
                    except Exception:
                        logger.exception(
                            "stage_classification: thumb render failed sheet=%s",
                            s.sheet_id,
                        )
                        final_results.append(lexical_by_id[s.sheet_id])
                        continue
                    rendered.append(
                        ai_sheet_classifier.SheetForClassification(
                            sheet_id=s.sheet_id,
                            sheet_name=s.sheet_name,
                            content_hash=s.content_hash,
                            thumbnail_png=thumb,
                        )
                    )

                if rendered:
                    try:
                        vision_model = ai_models.get_vision_model()
                        vision_results = ai_sheet_classifier.classify_vision_batch(
                            rendered,
                            vision_model=vision_model,
                            batch_size=settings.ai_vision_classify_batch_size,
                            lexical_by_id=lexical_by_id,
                        )
                    except Exception:
                        logger.exception(
                            "stage_classification: vision pass failed; falling back to lexical"
                        )
                        vision_results = [lexical_by_id[r.sheet_id] for r in rendered]
                    final_results.extend(vision_results)
            finally:
                try:
                    doc.close()
                except Exception:  # pragma: no cover
                    pass

    # Bulk update sheets.
    deduped: dict[uuid.UUID, ai_sheet_classifier.ClassificationResult] = {}
    for r in final_results:
        # Last write wins -- vision results follow lexical on the same sheet
        # so vision overrides cleanly.
        deduped[r.sheet_id] = r
    ai_sheet_classifier.bulk_upsert_classifications(session, deduped.values())

    # Cache new (non-cache-sourced) results.
    for r in deduped.values():
        if r.notes == "cache":
            continue
        sheet_obj = sheet_by_id.get(r.sheet_id)
        if sheet_obj is None:
            continue
        sheet_hash = ai_cache.compute_sheet_content_hash(sheet_obj)
        ai_cache.cache_put(
            session,
            org_id=run.org_id,
            content_hash=sheet_hash,
            stage="classification",
            model_version=model_version,
            value={
                "discipline": r.discipline,
                "sheet_type": r.sheet_type,
                "confidence": r.confidence,
                "method": r.method,
            },
        )

    counters = ai_sheet_classifier.ClassificationCounters()
    for r in deduped.values():
        counters.add(r, low_threshold=settings.ai_classification_confidence_threshold)
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
            "stage_2_low_confidence": counters.low_confidence_count,
            "stage_2_cache_hits": cache_hits,
        },
    )
    return {"cache_hit": cache_hits == len(sheets)}


@celery_app.task(name="ai_pipeline.stage_title_block", bind=True, acks_late=True)
def stage_title_block(self, ai_run_id_str: str) -> str:
    # Title-block work was reset for AI-02b -- this stage runs as a no-op
    # so the chain still walks all six stages. See sprint-ai-02b.md.
    return _run_stage(
        ai_run_id_str=ai_run_id_str,
        stage="title_block",
        body=_noop_stage,
    )


@celery_app.task(name="ai_pipeline.stage_classification", bind=True, acks_late=True)
def stage_classification(self, ai_run_id_str: str) -> str:
    return _run_stage(
        ai_run_id_str=ai_run_id_str,
        stage="classification",
        body=_stage_classification_body,
    )


@celery_app.task(name="ai_pipeline.stage_schedules_legends", bind=True, acks_late=True)
def stage_schedules_legends(self, ai_run_id_str: str) -> str:
    return _run_stage(
        ai_run_id_str=ai_run_id_str, stage="schedules_legends", body=_noop_stage
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


# ─── Public chain builder ────────────────────────────────────────────────────


def build_pipeline_chain(ai_run_id: uuid.UUID):
    """Construct the Celery chain for an AI run.

    Use ``build_pipeline_chain(run_id).apply_async()`` from the API handler to
    enqueue. Chain ordering matches ``PIPELINE_STAGES``.
    """
    s = str(ai_run_id)
    return chain(
        start_ai_run.s(s),
        stage_title_block.s(),
        stage_classification.s(),
        stage_schedules_legends.s(),
        stage_element_detection.s(),
        stage_resolver_and_layer_write.s(),
        finalize_ai_run.s(),
    )


