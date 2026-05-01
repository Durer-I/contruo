"""Per-stage content-hash cache for the AI Auto-Takeoff pipeline.

Re-runs on unchanged sheets short-circuit by reading the cached payload via
``cache_get``. Stage tasks call ``cache_get`` at the top, return early on a
hit, and call ``cache_put`` on completion.

The cache key is ``(org_id, content_hash, stage, model_version)``:

* ``content_hash`` -- SHA-256 of the relevant sheet inputs (PDF page bytes,
  scale calibration, etc.). See ``compute_sheet_content_hash``.
* ``stage`` -- the stage name (``title_block``, ``classification``, ...).
* ``model_version`` -- the provider+model id snapshot (e.g.
  ``anthropic:claude-sonnet-4-5``) so a model upgrade invalidates the cache
  cleanly without manual purges.

Cache writes are best-effort: if the row violates the unique constraint
(another worker beat us to it), we swallow the error and treat it as a hit on
the next read.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai_stage_cache import AiStageCache
from app.models.sheet import Sheet

logger = logging.getLogger(__name__)


def compute_plan_content_hash(
    plan_id: uuid.UUID,
    *,
    pdf_bytes: bytes | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Cache key input for plan-level stage outputs (e.g. title-block detection).

    Hashes the PDF bytes when supplied so a re-uploaded plan invalidates the
    cache. ``plan_id`` is included so distinct plans with bit-identical PDFs
    (rare, but possible across orgs) don't collide.
    """
    h = hashlib.sha256()
    h.update(b"plan|")
    h.update(str(plan_id).encode("utf-8"))
    h.update(b"|")
    if pdf_bytes is not None:
        h.update(hashlib.sha256(pdf_bytes).digest())
    h.update(b"|")
    if extra:
        h.update(
            json.dumps(extra, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
    return h.hexdigest()


def compute_sheet_content_hash(
    sheet: Sheet,
    *,
    pdf_bytes: bytes | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Compute the cache key input for a single sheet.

    Includes everything a stage's output legitimately depends on:

    * The sheet's PDF bytes (passed in by the caller; we do not download here
      to avoid coupling cache lookups to storage I/O).
    * Scale calibration (``scale_value``, ``scale_unit``) -- changing the scale
      changes wall thickness thresholds, so the cache must invalidate.
    * Page geometry (``width_px``, ``height_px``) for raster-fallback paths.
    * Any extra inputs the stage cares about (e.g. legend templates set).

    When ``pdf_bytes`` is None (e.g. cache lookups before download), the hash
    skips the PDF body. This is acceptable because storage paths are immutable
    -- the only way the body changes is a re-upload, which produces a new
    sheet row.
    """
    h = hashlib.sha256()
    h.update(str(sheet.id).encode("utf-8"))
    h.update(b"|")
    if sheet.scale_value is not None:
        h.update(f"scale={sheet.scale_value}:{sheet.scale_unit or ''}".encode("utf-8"))
    h.update(b"|")
    h.update(f"size={sheet.width_px or 0}x{sheet.height_px or 0}".encode("utf-8"))
    h.update(b"|")
    if pdf_bytes is not None:
        h.update(hashlib.sha256(pdf_bytes).digest())
    h.update(b"|")
    if extra:
        h.update(
            json.dumps(extra, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
    return h.hexdigest()


def cache_get(
    session: Session,
    *,
    org_id: uuid.UUID,
    content_hash: str,
    stage: str,
    model_version: str,
) -> dict[str, Any] | None:
    """Return the cached payload for a stage key, or ``None`` on miss.

    Bumps ``hit_count`` and ``last_accessed_at`` on a hit so we can spot hot
    keys when planning prune policies.
    """
    stmt = select(AiStageCache).where(
        AiStageCache.org_id == org_id,
        AiStageCache.content_hash == content_hash,
        AiStageCache.stage == stage,
        AiStageCache.model_version == model_version,
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    payload = row.value_jsonb
    try:
        session.execute(
            update(AiStageCache)
            .where(AiStageCache.id == row.id)
            .values(
                hit_count=AiStageCache.hit_count + 1,
                last_accessed_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    except Exception:
        # Hit-count bump is best-effort; do not fail the lookup over telemetry.
        session.rollback()
        logger.exception("Failed to bump ai_stage_cache hit_count for %s", row.id)
    return payload


def cache_invalidate(
    session: Session,
    *,
    org_id: uuid.UUID,
    content_hash: str,
    stage: str,
    model_version: str | None = None,
) -> int:
    """Delete cached stage outputs matching the key. Returns the row count.

    Used by the manual title-block endpoint when the user overrides the
    auto-detected bbox -- otherwise a future AI run would cache-hit the
    stale auto bbox and re-write wrong sheet names. Passing
    ``model_version=None`` deletes every model-version row for the
    ``(org_id, content_hash, stage)`` triple, which is the safe default
    for "the user changed the inputs entirely" semantics.
    """
    where_clauses = [
        AiStageCache.org_id == org_id,
        AiStageCache.content_hash == content_hash,
        AiStageCache.stage == stage,
    ]
    if model_version is not None:
        where_clauses.append(AiStageCache.model_version == model_version)
    try:
        result = session.execute(delete(AiStageCache).where(*where_clauses))
        session.commit()
        return int(result.rowcount or 0)
    except Exception:
        session.rollback()
        logger.exception(
            "Failed to invalidate ai_stage_cache for stage=%s hash=%s", stage, content_hash
        )
        return 0


def cache_put(
    session: Session,
    *,
    org_id: uuid.UUID,
    content_hash: str,
    stage: str,
    model_version: str,
    value: dict[str, Any],
) -> None:
    """Write a stage output to the cache. Idempotent under unique-key race."""
    row = AiStageCache(
        org_id=org_id,
        content_hash=content_hash,
        stage=stage,
        model_version=model_version,
        value_jsonb=value,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        # Another worker wrote the same key first; treat as success.
        session.rollback()
        logger.info(
            "ai_stage_cache write lost the race for stage=%s hash=%s -- ok",
            stage,
            content_hash,
        )
    except Exception:
        session.rollback()
        logger.exception(
            "Failed to write ai_stage_cache for stage=%s hash=%s", stage, content_hash
        )
