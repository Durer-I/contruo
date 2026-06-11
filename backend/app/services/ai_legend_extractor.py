"""Stage 3a: legend symbol cropping and primary-template persistence.

Takes the ``LegendCandidate`` list from ``ai_legend_detector`` and:

1. Renders each candidate's primary (1.00x scale, 0deg rotation) PNG from
   the fitz page at ``ai_legend_crop_dpi`` (default 300).
2. Computes ``template_hash = sha256(primary_bytes)`` -- the resolver's
   stable identity for "this symbol" across runs / sheets.
3. Uploads that single PNG to Supabase Storage at the deterministic path from
   ``app.utils.legend_storage``. Idempotent on re-run.
4. Writes one ``extracted_legends`` row per detected symbol. Multi-scale /
   multi-rotation variant assets and ``extracted_legend_variants`` rows are
   deferred (AI-06); ``PersistedLegend.variant_count`` is always ``0``.

Returns a list of ``PersistedLegend`` summaries the caller uses to populate
``summary_jsonb`` counters on the AI run.

What this module deliberately does NOT do:

* OCR-based label extraction. The detector pulls labels from the PDF text
  layer (always pristine), so OCR isn't on the AI-03 hot path. Image-only
  legends with rasterized labels are deferred to AI-03c.
* LLM label cleanup. Same reason -- text-layer labels are clean. The
  ``ai_legend_label_llm_min_confidence`` setting is plumbed through for
  AI-03c when OCR labels enter the picture.
"""
from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.extracted_legend import ExtractedLegend
from app.services.ai_legend_detector import LegendCandidate
from app.utils.legend_storage import (
    compute_template_hash,
    variant_filename,
    variant_storage_path,
)
from app.utils.storage import PLANS_BUCKET, upload_bytes

logger = logging.getLogger(__name__)


@dataclass
class PersistedLegend:
    """Per-symbol summary returned to the pipeline body.

    Used to grow ``summary_jsonb`` counters, build the response of the
    internal-debug API endpoint without re-querying the DB, and -- crucially --
    populate the legend cache so cache hits can persist DB rows without
    re-rendering or re-uploading the PNGs.
    """

    extracted_legend_id: uuid.UUID
    label: str
    template_hash: str
    primary_storage_path: str
    variant_count: int
    confidence: float
    bbox_pdf: dict[str, float] = field(default_factory=dict)
    extraction_method: str = ""
    notes: dict[str, Any] = field(default_factory=dict)

    def as_cached_dict(self) -> dict[str, Any]:
        """JSON-safe dict for ``ai_stage_cache``. ``extracted_legend_id`` is
        intentionally NOT cached -- it's per-run and would be wrong on re-run.
        """
        return {
            "label": self.label,
            "template_hash": self.template_hash,
            "primary_storage_path": self.primary_storage_path,
            "variant_count": self.variant_count,
            "confidence": float(self.confidence),
            "bbox_pdf": dict(self.bbox_pdf),
            "extraction_method": self.extraction_method,
            "notes": dict(self.notes),
        }


def persist_legend_candidates(
    *,
    db: Session,
    fitz_page: Any,
    candidates: list[LegendCandidate],
    org_id: uuid.UUID,
    plan_id: uuid.UUID,
    sheet_id: uuid.UUID,
    ai_run_id: uuid.UUID,
) -> list[PersistedLegend]:
    """Crop, upload the primary PNG, and write ``extracted_legends`` rows.

    Args:
        db: Sync SQLAlchemy session held by the Celery worker. Caller manages
            the outer transaction; this function commits per symbol so a
            failure on symbol N+1 doesn't roll back symbols 1..N (consistent
            with the "best-effort, log and move on" stage policy).
        fitz_page: ``fitz.Page`` for rendering the primary crop. Caller
            owns document lifetime.
        candidates: As produced by ``detect_legend_symbols``.
        org_id / plan_id / sheet_id / ai_run_id: Scoping IDs.

    Returns:
        One ``PersistedLegend`` per symbol that was successfully written;
        symbols that failed mid-pipeline are skipped (and logged).
    """
    if not candidates:
        return []

    settings = get_settings()
    dpi = settings.ai_legend_crop_dpi

    out: list[PersistedLegend] = []
    seen_hashes: set[str] = set()

    for candidate in candidates:
        try:
            primary_bytes = _render_primary_png(fitz_page, candidate.bbox_pdf, dpi=dpi)
        except Exception:
            logger.exception(
                "legend_extractor: primary render failed; sheet_id=%s label=%s",
                sheet_id,
                candidate.label,
            )
            continue
        if not primary_bytes:
            continue

        template_hash = compute_template_hash(primary_bytes)
        # Within a single sheet's run, dedupe identical symbols (a flaky
        # detector or two adjacent sibling rects with the same label can
        # produce duplicates). Cross-sheet dedup is intentionally NOT done
        # here -- AI-04 needs to know "symbol X appears on sheets A and B".
        if template_hash in seen_hashes:
            logger.info(
                "legend_extractor: skipping duplicate hash on sheet_id=%s label=%s",
                sheet_id,
                candidate.label,
            )
            continue
        seen_hashes.add(template_hash)

        primary_path = variant_storage_path(
            org_id, plan_id, template_hash=template_hash, scale=1.0, rotation=0
        )
        try:
            upload_bytes(
                PLANS_BUCKET,
                primary_path,
                primary_bytes,
                content_type="image/png",
                upsert=True,
            )
        except Exception:
            logger.exception(
                "legend_extractor: primary upload failed; path=%s", primary_path
            )
            continue

        legend = ExtractedLegend(
            org_id=org_id,
            ai_run_id=ai_run_id,
            sheet_id=sheet_id,
            bbox_pdf=dict(candidate.bbox_pdf),
            label=candidate.label[:255],
            template_storage_path=primary_path,
            template_hash=template_hash,
            extraction_method=candidate.extraction_method or "vector",
        )
        db.add(legend)
        try:
            db.commit()
            db.refresh(legend)
        except Exception:
            db.rollback()
            logger.exception(
                "legend_extractor: extracted_legends insert failed; label=%s",
                candidate.label,
            )
            continue

        out.append(
            PersistedLegend(
                extracted_legend_id=legend.id,
                label=legend.label,
                template_hash=template_hash,
                primary_storage_path=primary_path,
                variant_count=0,
                confidence=float(candidate.confidence),
                bbox_pdf=dict(candidate.bbox_pdf),
                extraction_method=legend.extraction_method,
                notes={"sibling_count": int(candidate.sibling_count)},
            )
        )

    return out


def persist_from_cached_metadata(
    *,
    db: Session,
    cached: list[dict[str, Any]],
    org_id: uuid.UUID,
    plan_id: uuid.UUID,
    sheet_id: uuid.UUID,
    ai_run_id: uuid.UUID,
) -> list[PersistedLegend]:
    """Cache-hit fast path: write fresh DB rows for ``ai_run_id`` from cached
    extractor metadata, *without* re-rendering or re-uploading PNGs.

    Storage paths are deterministic (``template_hash`` for the primary crop), so
    a cache hit guarantees the primary PNG already exists in the bucket from the
    earlier run. Skipping the rendering / upload work cuts a re-run on a
    plan with many legend sheets from heavy I/O to a handful of DB inserts.

    The trade-off: a manual deletion of files from the bucket would leave
    DB rows pointing at missing storage paths until the cache is invalidated
    or the plan re-uploaded. Acceptable for V1 -- bucket files aren't
    deleted on the AI path.
    """
    if not cached:
        return []

    out: list[PersistedLegend] = []
    seen_hashes: set[str] = set()

    for entry in cached:
        if not isinstance(entry, dict):
            continue
        template_hash = str(entry.get("template_hash") or "").strip()
        primary_path = str(entry.get("primary_storage_path") or "").strip()
        label = str(entry.get("label") or "")
        if not template_hash or not primary_path or not label:
            continue
        if template_hash in seen_hashes:
            continue
        seen_hashes.add(template_hash)

        bbox_raw = entry.get("bbox_pdf") or {}
        if not isinstance(bbox_raw, dict):
            bbox_raw = {}
        try:
            bbox_pdf = {
                "x0": float(bbox_raw.get("x0") or 0.0),
                "y0": float(bbox_raw.get("y0") or 0.0),
                "x1": float(bbox_raw.get("x1") or 0.0),
                "y1": float(bbox_raw.get("y1") or 0.0),
            }
        except (TypeError, ValueError):
            continue

        legend = ExtractedLegend(
            org_id=org_id,
            ai_run_id=ai_run_id,
            sheet_id=sheet_id,
            bbox_pdf=bbox_pdf,
            label=label[:255],
            template_storage_path=primary_path,
            template_hash=template_hash,
            extraction_method=str(entry.get("extraction_method") or "vector"),
        )
        db.add(legend)
        try:
            db.commit()
            db.refresh(legend)
        except Exception:
            db.rollback()
            logger.exception(
                "legend_extractor: cached_extracted_legends insert failed; label=%s",
                label,
            )
            continue

        out.append(
            PersistedLegend(
                extracted_legend_id=legend.id,
                label=legend.label,
                template_hash=template_hash,
                primary_storage_path=primary_path,
                variant_count=0,
                confidence=float(entry.get("confidence") or 0.0),
                bbox_pdf=bbox_pdf,
                extraction_method=legend.extraction_method,
                notes={"source": "cache"},
            )
        )

    return out


# ``variant_filename`` is intentionally kept importable from this module so
# callers (e.g. internal API) can reconstruct paths without depending on the
# ``utils.legend_storage`` module directly.
__all__ = [
    "PersistedLegend",
    "persist_legend_candidates",
    "persist_from_cached_metadata",
    "variant_filename",
]


def _render_primary_png(fitz_page: Any, bbox_pdf: dict[str, float], *, dpi: int) -> bytes:
    """Render the legend bbox at ``dpi`` -> PNG bytes.

    Uses the same matrix scheme as ``app.utils.pdf.render_clip_to_png`` so a
    re-render at the same DPI on the same bytes produces the same hash.
    """
    import fitz  # type: ignore[import-untyped]
    from PIL import Image

    rect = fitz.Rect(
        float(bbox_pdf["x0"]),
        float(bbox_pdf["y0"]),
        float(bbox_pdf["x1"]),
        float(bbox_pdf["y1"]),
    )
    scale = max(1.0, dpi / 72.0)
    matrix = fitz.Matrix(scale, scale)
    pix = fitz_page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
