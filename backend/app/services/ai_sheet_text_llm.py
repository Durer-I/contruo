"""Sheet classification + naming via PyMuPDF structured text + OpenAI Responses API.

Replaces lexical/vision classification and title-block heuristics for Stage 2 and
the auto-name-sheets task. See Sprint plan: batched ``gpt-5.4-mini`` analysis.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.sheet import Sheet
from app.services import ai_cache
from app.services.ai_models import with_cost_tracking
from app.services.ai_sheet_classifier import ALL_SHEET_TYPES, infer_discipline_from_sheet_number

logger = logging.getLogger(__name__)

#: Bump when classification/naming algorithm changes (cache invalidation).
SHEET_TEXT_CLASSIFY_VERSION = "text_llm_v2"


SHEET_TEXT_CLASSIFICATION_PROMPT = """
You are analyzing text extracted from a construction drawing sheet.

Your task is to classify the sheet based on its usefulness for quantity takeoff.

Return your answer strictly in valid JSON format.

Classification categories (choose ONE primary category):
1. "takeoff_required" → The sheet contains measurable elements directly used for quantity takeoff (dimensions, counts, material specs tied to quantities).
2. "supporting_information" → Contextual sheets such as notes, legends, sections, elevations, and details that assist interpretation but do not directly provide extractable quantities.
3. "reference_only" → Cover pages, indexes, title sheets, logos, disclaimers.
4. "schedule_sheet" → Sheets primarily composed of tabular schedules (door, window, equipment, panel schedules, etc.).
5. "uncertain" → The content is unclear or insufficient to determine.

Also add:
"sheet_type": one of ["plan", "schedule", "detail", "section", "elevation", "legend", "notes", "mixed", "unknown"]

Additionally, extract:
- "confidence": number between 0 and 1
- "sheet_name": name of the sheet
- "sheet_number": number of the sheet

Rules:
- If a sheet is primarily a schedule (tabular structure), ALWAYS classify it as "schedule_sheet".
- Schedule sheets typically contain repeated rows/columns and headers like "schedule", "mark", "type", "size".
- Only classify as "takeoff_required" if clear measurable quantities are present.
- If the text is noisy or incomplete, prefer "supporting_information" or "uncertain".
- Ensure "category" and "sheet_type" are logically consistent.
- Do NOT hallucinate missing context.
- Output ONLY JSON.

Return a JSON ARRAY. Each object must include a "page" field (0-based index matching the "--- PAGE N ---" markers in order).
Do not return a single object. Do not wrap in markdown.

Example object:
{
  "category": "takeoff_required",
  "sheet_type": "plan",
  "confidence": 0.92,
  "sheet_name": "Structural Plan",
  "sheet_number": "S1.0",
  "page": 0
}
""".strip()


#: Map LLM ``sheet_type`` strings into DB ``ALL_SHEET_TYPES``.
_LLM_SHEET_TYPE_TO_DB: dict[str, str] = {
    "plan": "plan",
    "schedule": "schedule",
    "detail": "detail",
    "section": "section",
    "elevation": "elevation",
    "legend": "legend",
    "notes": "legend",
    "mixed": "other",
    "unknown": "other",
}


def extract_structured_text(page: Any) -> str:
    """Extract line-joined text from a PyMuPDF page (``fitz.Page``).

    Uses ``get_text("dict")``, skips non-text blocks, joins spans per line.
    """
    data = page.get_text("dict")
    blocks = data.get("blocks") or []
    lines_out: list[str] = []

    for b in blocks:
        if b.get("type", 0) != 0:
            continue
        for line in b.get("lines") or []:
            spans = line.get("spans") or []
            line_text = " ".join(
                span["text"] for span in spans if span.get("text", "").strip()
            )
            if line_text.strip():
                lines_out.append(line_text.strip())

    return "\n".join(lines_out)


def hash_structured_text(text: str) -> str:
    """MD5 digest used for duplicate-page dedupe inside a batch (matches prototype)."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def create_batches(
    items: list[tuple[int, str]], *, batch_size: int
) -> Iterator[list[tuple[int, str]]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def coerce_sheet_type(llm_type: str | None) -> str:
    """Map model ``sheet_type`` into ``ALL_SHEET_TYPES``."""
    if not llm_type:
        return "other"
    key = str(llm_type).strip().lower()
    mapped = _LLM_SHEET_TYPE_TO_DB.get(key)
    if mapped is not None:
        return mapped
    if key in ALL_SHEET_TYPES:
        return key
    return "other"


def extract_all_page_texts(doc: Any) -> dict[int, str]:
    """0-based page index -> structured text for every PDF page (``0 .. page_count - 1``).

    Matches the prototype loop: enumerate all pages in order so batch windows align with
    physical sheet order.
    """
    count = int(doc.page_count or 0)
    out: dict[int, str] = {}
    for idx in range(count):
        page = doc.load_page(idx)
        out[idx] = extract_structured_text(page)
    return out


def run_sheet_text_llm_batches(
    *,
    page_texts: dict[int, str],
    batch_size: int | None = None,
    model: str | None = None,
    pages_needing_llm: set[int] | None = None,
) -> dict[int, dict[str, Any]]:
    """Call OpenAI Responses API in batches; return page index -> raw LLM object.

    Duplicate identical page text reuses the cached parsed row per MD5 (prototype behavior).
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    bs = batch_size if batch_size is not None else settings.ai_sheet_text_classify_batch_size
    if bs <= 0:
        bs = 10

    md = model if model is not None else settings.ai_sheet_text_classify_model

    needing: set[int] = (
        set(page_texts.keys())
        if pages_needing_llm is None
        else set(pages_needing_llm)
    )

    sorted_pages = sorted(page_texts.items(), key=lambda x: x[0])
    results: dict[int, dict[str, Any]] = {}
    hash_cache: dict[str, dict[str, Any]] = {}

    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openai SDK is not installed") from exc

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.ai_openai_llm_timeout_s,
        max_retries=settings.ai_openai_llm_max_retries,
    )

    for batch in create_batches(sorted_pages, batch_size=bs):
        batch_input = ""
        page_map: dict[int, str] = {}

        for page_num, page_text in batch:
            if page_num not in needing:
                continue
            text_hash = hash_structured_text(page_text)
            if text_hash in hash_cache:
                cached = copy.deepcopy(hash_cache[text_hash])
                cached["page"] = page_num
                results[page_num] = cached
                continue
            batch_input += f"\n\n--- PAGE {page_num} ---\n{page_text}"
            page_map[page_num] = text_hash

        if not batch_input.strip():
            continue

        with with_cost_tracking("openai.sheet_text_classify") as cost:
            response = client.responses.create(
                model=md,
                temperature=0,
                input=[
                    {"role": "system", "content": SHEET_TEXT_CLASSIFICATION_PROMPT},
                    {"role": "user", "content": batch_input},
                ],
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                inp = int(getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0)
                out_tok = int(getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0)
                cost.tokens_used = inp + out_tok
                cost.cost_cents = int(
                    inp / 1000.0 * settings.ai_openai_llm_input_per_1k_cents
                    + out_tok / 1000.0 * settings.ai_openai_llm_output_per_1k_cents
                    + 0.999999
                )

            raw_out = getattr(response, "output_text", None)
            output_path = Path(f"../test/test.json")
            with open(output_path, "w") as f:
                        json.dump(raw_out , f, indent=4)
            if raw_out is None:
                # Fallback for SDK variants
                out_list = getattr(response, "output", None)
                if out_list and len(out_list) > 0:
                    parts = getattr(out_list[0], "content", None) or []
                    if parts:
                        raw_out = getattr(parts[0], "text", None) or str(parts[0])

            if not raw_out:
                logger.warning("sheet_text_llm: empty response from OpenAI")
                continue

            try:
                parsed = json.loads(raw_out)
            except json.JSONDecodeError:
                logger.exception("sheet_text_llm: invalid JSON from model: %s", raw_out[:300])
                continue

            if not isinstance(parsed, list):
                logger.warning("sheet_text_llm: expected JSON array from model")
                continue

            for item in parsed:
                if not isinstance(item, dict):
                    continue
                try:
                    page_num = int(item["page"])
                except (KeyError, TypeError, ValueError):
                    continue
                fixed = copy.deepcopy(item)
                fixed["page"] = page_num
                results[page_num] = fixed
                if page_num in page_map:
                    hash_cache[page_map[page_num]] = copy.deepcopy(fixed)

        output_path = Path(f"../test/test.json")
        with open(output_path, "w") as f:
                        json.dump(results , f, indent=4)
    return results


@dataclass(frozen=True)
class SheetTextLlmUpsertRow:
    sheet_id: uuid.UUID
    discipline: str
    sheet_type: str
    confidence: float
    method: str
    patch_names: bool
    sheet_name: str | None
    sheet_number: str | None


def build_upsert_rows_for_sheets(
    sheets: list[Sheet],
    *,
    llm_by_page: dict[int, dict[str, Any]],
    sheet_eligible_for_names: dict[uuid.UUID, bool],
) -> list[SheetTextLlmUpsertRow]:
    """Turn LLM output into rows for ``bulk_upsert_sheet_text_llm``."""
    rows: list[SheetTextLlmUpsertRow] = []
    for sheet in sheets:
        idx = int(sheet.page_number or 1) - 1
        item = llm_by_page.get(idx)
        if not item:
            rows.append(
                SheetTextLlmUpsertRow(
                    sheet_id=sheet.id,
                    discipline="other",
                    sheet_type="other",
                    confidence=0.0,
                    method="text_llm",
                    patch_names=False,
                    sheet_name=None,
                    sheet_number=None,
                )
            )
            continue

        raw_name = item.get("sheet_name")
        raw_num = item.get("sheet_number")
        name_str = (str(raw_name).strip() if raw_name is not None else "") or None
        num_str = (str(raw_num).strip() if raw_num is not None else "") or None

        try:
            conf = float(item.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))

        st_llm = item.get("sheet_type")
        sheet_type = coerce_sheet_type(st_llm if isinstance(st_llm, str) else None)

        discipline = infer_discipline_from_sheet_number(num_str)
        if discipline is None:
            discipline = "other"

        eligible = sheet_eligible_for_names.get(sheet.id, False)
        patch_names = eligible and (name_str is not None or num_str is not None)

        rows.append(
            SheetTextLlmUpsertRow(
                sheet_id=sheet.id,
                discipline=discipline,
                sheet_type=sheet_type,
                confidence=conf,
                method="text_llm",
                patch_names=patch_names,
                sheet_name=name_str,
                sheet_number=num_str,
            )
        )
    return rows


def bulk_upsert_sheet_text_llm(
    session: Session,
    rows: Iterable[SheetTextLlmUpsertRow],
) -> int:
    """Single UPDATE … FROM jsonb for classification + optional sheet names."""
    row_list = list(rows)
    if not row_list:
        return 0

    payload = [
        {
            "sheet_id": str(r.sheet_id),
            "discipline": r.discipline,
            "sheet_type": r.sheet_type,
            "confidence": float(r.confidence),
            "method": r.method,
            "patch_names": r.patch_names,
            "sheet_name": r.sheet_name,
            "sheet_number": r.sheet_number,
        }
        for r in row_list
    ]

    stmt = text(
        """
        UPDATE sheets AS s
           SET discipline = v.discipline,
               sheet_type = v.sheet_type,
               classification_confidence = v.confidence,
               classification_method = v.method,
               sheet_name = CASE
                 WHEN v.patch_names AND v.sheet_name IS NOT NULL AND length(trim(v.sheet_name)) > 0
                   THEN trim(v.sheet_name)
                 ELSE s.sheet_name
               END,
               sheet_number = CASE
                 WHEN v.patch_names AND v.sheet_number IS NOT NULL AND length(trim(v.sheet_number)) > 0
                   THEN trim(v.sheet_number)
                 ELSE s.sheet_number
               END,
               sheet_name_source = CASE
                 WHEN v.patch_names AND (
                   (v.sheet_name IS NOT NULL AND length(trim(v.sheet_name)) > 0)
                   OR (v.sheet_number IS NOT NULL AND length(trim(v.sheet_number)) > 0)
                 )
                   THEN 'auto'
                 ELSE s.sheet_name_source
               END
          FROM (
            SELECT
              CAST(elem->>'sheet_id' AS uuid) AS sheet_id,
              elem->>'discipline' AS discipline,
              elem->>'sheet_type' AS sheet_type,
              CAST(elem->>'confidence' AS float) AS confidence,
              elem->>'method' AS method,
              CAST(elem->>'patch_names' AS boolean) AS patch_names,
              elem->>'sheet_name' AS sheet_name,
              elem->>'sheet_number' AS sheet_number
            FROM jsonb_array_elements(CAST(:payload AS jsonb)) AS elem
          ) AS v
         WHERE s.id = v.sheet_id
        """
    )

    import json as _json

    result = session.execute(stmt, {"payload": _json.dumps(payload)})
    return int(result.rowcount or 0)


def execute_sheet_text_llm_for_plan(
    session: Session,
    *,
    org_id: uuid.UUID,
    sheets: list[Sheet],
    pdf_bytes: bytes,
    sheet_eligible_for_names: dict[uuid.UUID, bool],
) -> tuple[int, dict[int, dict[str, Any]], int]:
    """Extract page text, merge cache + OpenAI batches, bulk-update ``sheets``.

    PDF bytes typically come from Supabase Storage (plan file). Text is extracted for
    every page ``0 .. N-1`` so LLM batches follow consecutive sheet order; results are
    mapped back to rows by ``page_number``.

    Returns ``(cache_hits, llm_by_page, rows_updated)``.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    sheets = sorted(sheets, key=lambda s: int(s.page_number or 1))

    model_version = (
        f"{SHEET_TEXT_CLASSIFY_VERSION}|{settings.ai_sheet_text_classify_model}"
    )

    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF (fitz) is not installed") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_texts = extract_all_page_texts(doc)
    finally:
        try:
            doc.close()
        except Exception:  # pragma: no cover
            pass

    llm_by_page: dict[int, dict[str, Any]] = {}
    cache_hits = 0
    pages_for_api: dict[int, str] = {}

    for sheet in sheets:
        idx = int(sheet.page_number or 1) - 1
        text = page_texts.get(idx, "")
        ch = ai_cache.compute_sheet_structured_text_cache_hash(sheet, text)
        cached = ai_cache.cache_get(
            session,
            org_id=org_id,
            content_hash=ch,
            stage="classification",
            model_version=model_version,
        )
        if cached and isinstance(cached.get("llm_item"), dict):
            llm_by_page[idx] = cached["llm_item"]
            cache_hits += 1
            continue
        pages_for_api[idx] = text

    if pages_for_api:
        fresh = run_sheet_text_llm_batches(
            page_texts=page_texts,
            batch_size=settings.ai_sheet_text_classify_batch_size,
            model=settings.ai_sheet_text_classify_model,
            pages_needing_llm=set(pages_for_api.keys()),
        )
        llm_by_page.update(fresh)
        for sheet in sheets:
            idx = int(sheet.page_number or 1) - 1
            if idx not in pages_for_api:
                continue
            item = llm_by_page.get(idx)
            if not item:
                continue
            text_body = page_texts.get(idx, "")
            ch = ai_cache.compute_sheet_structured_text_cache_hash(sheet, text_body)
            ai_cache.cache_put(
                session,
                org_id=org_id,
                content_hash=ch,
                stage="classification",
                model_version=model_version,
                value={"llm_item": item},
            )

    rows = build_upsert_rows_for_sheets(
        sheets,
        llm_by_page=llm_by_page,
        sheet_eligible_for_names=sheet_eligible_for_names,
    )
    written = bulk_upsert_sheet_text_llm(session, rows)

    return cache_hits, llm_by_page, written


__all__ = [
    "SHEET_TEXT_CLASSIFY_VERSION",
    "SHEET_TEXT_CLASSIFICATION_PROMPT",
    "SheetTextLlmUpsertRow",
    "bulk_upsert_sheet_text_llm",
    "build_upsert_rows_for_sheets",
    "coerce_sheet_type",
    "create_batches",
    "execute_sheet_text_llm_for_plan",
    "extract_all_page_texts",
    "extract_structured_text",
    "hash_structured_text",
    "run_sheet_text_llm_batches",
]
