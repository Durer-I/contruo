"""Internal AI extractions debug endpoint (Sprint AI-03).

Owner / admin-only. Returns the full dump of ``extracted_schedules`` +
``extracted_legends`` (+ optional ``extracted_legend_variants`` rows when
present from older runs) for a given AI run,
with signed URLs for the legend symbol PNGs so the internal debug page can
visually verify the extractor output.

Not exposed to estimators -- the AI Auto-Takeoff feature surfaces extracted
data through the resolver / layer-write stages (AI-04, AI-05). This endpoint
exists for the engineering team to spot-check Stage 3a quality without
querying the database directly.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext, require_role
from app.models.ai_run import AiRun
from app.models.extracted_legend import ExtractedLegend
from app.models.extracted_legend_variant import ExtractedLegendVariant
from app.models.extracted_schedule import ExtractedSchedule
from app.models.sheet import Sheet
from app.schemas.internal_ai_extractions import (
    AiRunExtractionsResponse,
    ExtractedLegendRow,
    ExtractedLegendVariantRow,
    ExtractedScheduleRow,
)
from app.utils.storage import PLANS_BUCKET, signed_url

router = APIRouter(prefix="/internal/ai")

#: Cap on rows returned in the extracted-table preview. Full tables can have
#: 50+ rows -- the debug page is for visual spot-checking, not analysis.
SAMPLE_ROWS_PER_SCHEDULE = 5


@router.get(
    "/runs/{ai_run_id}/extractions",
    response_model=AiRunExtractionsResponse,
)
async def get_run_extractions(
    ai_run_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> AiRunExtractionsResponse:
    """Return every schedule + legend extracted by ``ai_run_id``.

    Org-scoped: a debug call from another org gets 404, not 403, to avoid
    leaking the existence of the run.
    """
    run = (
        await db.execute(
            select(AiRun).where(
                AiRun.id == ai_run_id,
                AiRun.org_id == auth.org_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="AI run not found")

    sheets_by_id = {
        row.id: row
        for row in (
            await db.execute(
                select(Sheet).where(Sheet.plan_id == run.plan_id)
            )
        )
        .scalars()
        .all()
    }

    schedule_rows = (
        await db.execute(
            select(ExtractedSchedule)
            .where(ExtractedSchedule.ai_run_id == ai_run_id)
            .order_by(ExtractedSchedule.created_at.asc())
        )
    ).scalars().all()

    legend_rows = (
        await db.execute(
            select(ExtractedLegend)
            .where(ExtractedLegend.ai_run_id == ai_run_id)
            .order_by(ExtractedLegend.created_at.asc())
        )
    ).scalars().all()

    legend_ids = [row.id for row in legend_rows]
    variants_by_legend: dict[uuid.UUID, list[ExtractedLegendVariant]] = {}
    if legend_ids:
        variant_rows = (
            await db.execute(
                select(ExtractedLegendVariant)
                .where(ExtractedLegendVariant.extracted_legend_id.in_(legend_ids))
                .order_by(
                    ExtractedLegendVariant.scale.asc(),
                    ExtractedLegendVariant.rotation.asc(),
                )
            )
        ).scalars().all()
        for v in variant_rows:
            variants_by_legend.setdefault(v.extracted_legend_id, []).append(v)

    schedules_out: list[ExtractedScheduleRow] = []
    for s in schedule_rows:
        sheet = sheets_by_id.get(s.sheet_id)
        table = s.extracted_table_jsonb or {}
        headers_raw = table.get("headers") or []
        rows_raw = table.get("rows") or []
        schedules_out.append(
            ExtractedScheduleRow(
                id=s.id,
                sheet_id=s.sheet_id,
                sheet_name=sheet.sheet_name if sheet else None,
                sheet_number=sheet.sheet_number if sheet else None,
                page_number=sheet.page_number if sheet else None,
                bbox_pdf=dict(s.bbox_pdf or {}),
                extraction_method=s.extraction_method,
                tag_column_index=s.tag_column_index,
                description_column_index=s.description_column_index,
                quantity_column_index=s.quantity_column_index,
                dimension_column_indexes=s.dimension_column_indexes,
                material_column_index=s.material_column_index,
                headers=[str(h) for h in headers_raw],
                row_count=len(rows_raw),
                sample_rows=[
                    [str(c) for c in (row if isinstance(row, list) else [])]
                    for row in rows_raw[:SAMPLE_ROWS_PER_SCHEDULE]
                ],
            )
        )

    legends_out: list[ExtractedLegendRow] = []
    for legend in legend_rows:
        sheet = sheets_by_id.get(legend.sheet_id)
        primary_url = signed_url(PLANS_BUCKET, legend.template_storage_path)
        variants = variants_by_legend.get(legend.id, [])
        variants_out = [
            ExtractedLegendVariantRow(
                scale=float(v.scale),
                rotation=int(v.rotation),
                template_storage_path=v.template_storage_path,
                signed_url=signed_url(PLANS_BUCKET, v.template_storage_path),
            )
            for v in variants
        ]
        legends_out.append(
            ExtractedLegendRow(
                id=legend.id,
                sheet_id=legend.sheet_id,
                sheet_name=sheet.sheet_name if sheet else None,
                sheet_number=sheet.sheet_number if sheet else None,
                page_number=sheet.page_number if sheet else None,
                label=legend.label,
                bbox_pdf=dict(legend.bbox_pdf or {}),
                template_hash=legend.template_hash,
                template_storage_path=legend.template_storage_path,
                primary_signed_url=primary_url,
                extraction_method=legend.extraction_method,
                variants=variants_out,
            )
        )

    summary = run.summary_jsonb or {}
    if isinstance(summary, dict):
        sl_summary = summary.get("schedules_legends") or {}
    else:
        sl_summary = {}

    return AiRunExtractionsResponse(
        ai_run_id=run.id,
        plan_id=run.plan_id,
        project_id=run.project_id,
        schedules=schedules_out,
        legends=legends_out,
        summary={
            "schedules_legends": sl_summary,
            "run_status": run.status,
            "schedule_count": len(schedules_out),
            "legend_count": len(legends_out),
        },
    )
