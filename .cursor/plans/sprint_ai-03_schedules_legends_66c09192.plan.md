---
name: Sprint AI-03 schedules legends
overview: "Implement Stage 3a of the AI Auto-Takeoff pipeline: prototype-faithful schedule + legend extraction with keyword-based sheet filtering, deterministic heuristics first, vision/LLM only as escalation. Multi-scale legend templates stored in a dedicated variants table to keep AI-04 egress minimal. Internal debug surface for QA. No manual legend fallback (deferred to AI-03b). No classifier fix (deferred to AI-03c)."
todos:
  - id: migration-017
    content: "Migration 017: add schedule column-index fields to extracted_schedules + create extracted_legend_variants table; mirror in models"
    status: completed
  - id: settings-env
    content: Add AI-03 settings to config.py + .env.example (LLM provider/model, DPIs, confidence + margin thresholds, scale/rotation grid)
    status: completed
  - id: vision-extract-structured
    content: Wire AnthropicVisionModel.extract_structured (mirror classify_image pattern with cost tracking)
    status: completed
  - id: schedules-llm-factory
    content: Add ai_models.get_schedules_llm() factory (default OpenAI gpt-4o-mini)
    status: completed
  - id: sheet-filter-helper
    content: "ai_sheet_filter.py: shared keyword-based filter helpers for schedule + legend sheet selection (matches prototype)"
    status: completed
  - id: schedule-extractor
    content: "ai_schedule_extractor.py: lines_strict primary (prototype-faithful) + lines/text/vision escalation; row-width-variance scorer; bbox padding 40pts"
    status: completed
  - id: tag-column
    content: "ai_tag_column.py: 4-feature scorer + LLM fallback gating; tag/description/quantity/dimension/material column ID"
    status: completed
  - id: legend-detector
    content: "ai_legend_detector.py: port find_rectangles_text verbatim + additive layers (multi-direction labels, circles, polygons, confidence scoring)"
    status: completed
  - id: legend-storage-helper
    content: "legend_storage.py: deterministic filenames + org-scoped storage path helper"
    status: completed
  - id: legend-extractor
    content: "ai_legend_extractor.py: 300 DPI crops, 5x4 multi-scale/rotation variants, OCR + LLM label cleanup, persistence to extracted_legends + extracted_legend_variants"
    status: completed
  - id: pipeline-body
    content: Wire _stage_schedules_legends_body into ai_pipeline.py with caching + summary counters
    status: completed
  - id: internal-api
    content: "internal_ai_extractions.py: GET /internal/ai/runs/{rid}/extractions (owner+admin only); wire router"
    status: completed
  - id: internal-debug-page
    content: Frontend internal debug page rendering extracted tables + legend thumbnails (owner+admin gated)
    status: completed
  - id: tests-schedule
    content: test_ai_schedule_extractor.py + test_ai_tag_column.py with mocked vision/LLM
    status: pending
  - id: tests-legend
    content: test_ai_legend_detector.py + test_ai_legend_extractor.py with mocked storage
    status: pending
  - id: tests-pipeline
    content: Extend test_ai_pipeline_tasks.py and test_ai_models.py for the new bodies
    status: pending
  - id: docs-cleanup
    content: Update roadmap.md (AI-02b actuals + AI-03 shipped section + AI-03b/c stubs), sprint-ai-02b.md Part B, ai-pipeline.md
    status: completed
isProject: false
---

# Sprint AI-03: Schedule + Legend Extraction

## Scope guardrails

- **No manual legend fallback this sprint.** Confidence < 0.6 legend regions are skipped and counted in `summary_jsonb["schedules_legends"]["legend_skipped_low_confidence"]`. Future **AI-03b** sprint will land an async override pattern modelled on AI-02b's `auto-name-sheets`.
- **No classifier fix this sprint.** Sheet selection is keyword-based (matches the prototype). Future **AI-03c** sprint will replace AI-02's vision-on-thumbnail classifier with text-LLM-on-title.
- **No new chain shape.** `_stage_schedules_legends_body` swaps `_noop_stage` for `stage_schedules_legends` in `[backend/app/tasks/ai_pipeline.py](backend/app/tasks/ai_pipeline.py)`; `PIPELINE_STAGES` and `build_pipeline_chain` are untouched.
- **No `sheet_name` writes.** AI-03 reads sheets but never writes them. The `sheet_name_source='manual'` guard is irrelevant.

## Locked decisions

- **Sheet filter (schedules):** keyword-only — `sheet_name ILIKE ANY ('%schedule%','%abbreviation%','%symbols%')`. Matches `[AI/controller/title.py](AI/controller/title.py)` prototype exactly.
- **Sheet filter (legends):** keyword-only — `sheet_name ILIKE ANY ('%legend%','%symbol%','%abbreviation%','%reflected ceiling%','%rcp%','%finish%','%finishes%','%floor plan%')`. Avoids the every-page processing cost.
- **Schedule extractor base:** `page.find_tables({'vertical_strategy': 'lines_strict', 'horizontal_strategy': 'lines_strict'})` from `[AI/controller/find_tables.py](AI/controller/find_tables.py)`. Escalates to `lines`, then `text`, then vision only when prior step yields nothing or low-quality.
- **Legend detector base:** port `[AI/controller/legends.py](AI/controller/legends.py)` `find_rectangles_text` verbatim (same `tolerance=2`, `min_size=16`, group-by-rounded-coords, `has_text_inside` reject, `get_adjacent_text` for labels, `merge_rects`). Additive improvements layered on top, individually toggleable.
- **Multi-scale legend storage:** **Option B** — `extracted_legends` (one primary row per logical symbol) + new `extracted_legend_variants` table (one row per scale × rotation). Minimizes AI-04 egress.
- **LLM fallback path:** `OpenAILLMModel.structured_output` via a new `ai_models.get_schedules_llm()` factory (mirrors `get_title_block_llm`). `AnthropicLLMModel.structured_output` stays stubbed for AI-04.
- **Vision path:** wire `AnthropicVisionModel.extract_structured` (currently `NotImplementedError`) following the `classify_image` pattern.
- **Storage path:** `{org_id}/plans/{plan_id}/legends/{label_slug}__{scale}_{rot}_{template_hash[:12]}.png`.
- **Multi-page schedules:** independent rows per page. AI-04 handles logical stitching by `MARK` value continuity.
- **Internal debug page auth:** `require_role("owner", "admin")`.
- **Doc cleanup:** included as last task (covers AI-02b actuals + new AI-03b/AI-03c stubs in the roadmap).

## DB migration

`[backend/migrations/versions/017_extracted_schedule_columns_and_legend_variants.py](backend/migrations/versions/017_extracted_schedule_columns_and_legend_variants.py)` (down-revision `016_sheet_number`):

**`extracted_schedules` ALTER:**

- `description_column_index INT NULL`
- `quantity_column_index INT NULL`
- `dimension_column_indexes JSONB NULL` (array of ints)
- `material_column_index INT NULL`

**New table `extracted_legend_variants`:**

- `id UUID PK`
- `org_id UUID FK organizations` (RLS)
- `extracted_legend_id UUID FK extracted_legends ON DELETE CASCADE`
- `scale NUMERIC(3,2)` (e.g. `0.70`, `0.85`, `1.00`, `1.15`, `1.30`)
- `rotation INT` (0 / 90 / 180 / 270)
- `template_storage_path TEXT`
- `template_hash VARCHAR(64)`
- `created_at TIMESTAMP`
- Unique constraint on `(extracted_legend_id, scale, rotation)`
- Index on `(extracted_legend_id)` for AI-06 join
- RLS policy: same shape as `extracted_legends`

Mirror columns into `[backend/app/models/extracted_schedule.py](backend/app/models/extracted_schedule.py)`; new model `[backend/app/models/extracted_legend_variant.py](backend/app/models/extracted_legend_variant.py)`.

## Backend services

- `[backend/app/services/ai_sheet_filter.py](backend/app/services/ai_sheet_filter.py)` — shared SQL helpers `select_schedule_sheets(session, plan_id)` and `select_legend_sheets(session, plan_id)` returning `list[Sheet]` filtered by the keyword lists above. One module so the filter rules are documented in one place.
- `[backend/app/services/ai_schedule_extractor.py](backend/app/services/ai_schedule_extractor.py)` — orchestrator. Per page:
  1. Try `pdfplumber.find_tables({'vertical_strategy': 'lines_strict', 'horizontal_strategy': 'lines_strict'})` — exact prototype call.
  2. If empty or score-low: try `'lines'` strategy.
  3. If still empty: try `'text'` strategy.
  4. If still empty: render bbox region at 200 DPI, call `VisionModel.extract_structured` with `{columns, rows}` schema.
  5. Score each successful strategy by `variance(row_widths) / mean(row_widths)`; lowest variance wins.
  6. Apply 40pt bbox padding (matches prototype `padding = 40`).
  7. Call `extract_table()` to get `[[cell, ...], ...]`; coerce to `{headers: [...], rows: [[...]]}`.
- `[backend/app/services/ai_tag_column.py](backend/app/services/ai_tag_column.py)` — 4-feature deterministic scorer (header keyword 0.4 / cardinality 0.2 / length+alphanumeric 0.2 / position 0.2); LLM fallback gated by `top >= 0.7 AND second_best <= top - 0.1`. Same module handles description column (longer-text variant) and the optional `quantity_column_index`, `dimension_column_indexes`, `material_column_index`.
- `[backend/app/services/ai_legend_detector.py](backend/app/services/ai_legend_detector.py)` — **prototype core (verbatim port)**:
  - `_round_rects(rects, tolerance=2)` → `_group_by_xrange(rects)` → `_filter_most_common_size(group, min_size=16)` → `has_text_inside(rect, words)` reject → `get_adjacent_text(rect, words)` → `merge_rects(...)`.
  - **Additive layers (each individually toggleable via setting):**
    - `legend_label_directions: list[str]` (default `["right","below","above","left"]` — prototype uses `["right"]` only).
    - `legend_detect_circles: bool` (default `True`) — Hough on suspected legend strips.
    - `legend_detect_polygons: bool` (default `True`) — `fitz.get_drawings()` closed paths.
  - Confidence scorer: shape repetition (0.3) + label proximity (0.3) + label brevity (0.2) + layout regularity (0.2). Threshold 0.6.
- `[backend/app/services/ai_legend_extractor.py](backend/app/services/ai_legend_extractor.py)` — orchestrator: crops each detected symbol at 300 DPI, generates 5 scales × 4 rotations (20 variants per symbol), uploads to Supabase Storage, computes `template_hash`. Inserts one `extracted_legends` primary row + 19 `extracted_legend_variants` sibling rows per symbol. Label OCR: PyMuPDF text-layer first, Tesseract fallback at 2× DPI, LLM cleanup via `OpenAILLMModel.structured_output` only when OCR confidence is low (mirrors prototype's commented-out GPT cleanup pass at `[AI/controller/legends.py:135-144](AI/controller/legends.py)`).
- `[backend/app/utils/legend_storage.py](backend/app/utils/legend_storage.py)` — `legend_storage_path(org_id, plan_id, filename)`, `legend_filename(label, scale, rotation, template_hash)`, `slugify_label(...)`.

## Provider wiring

- `[backend/app/services/ai_models.py](backend/app/services/ai_models.py)`:
  - Implement `AnthropicVisionModel.extract_structured` (mirrors `classify_image` — lazy SDK import, `with_cost_tracking("anthropic_vision.extract_structured")`, base64 image, schema in system prompt, `_strip_code_fences` + `json.loads`).
  - Add `get_schedules_llm()` factory (defaults `openai` / `gpt-4o-mini`, honors new settings; same pattern as `get_title_block_llm`).

## Pipeline body

`[backend/app/tasks/ai_pipeline.py](backend/app/tasks/ai_pipeline.py)`:

- New `_stage_schedules_legends_body(session, run, plan)`:
  1. Call `ai_sheet_filter.select_schedule_sheets(session, plan.id)` → `schedule_sheets`.
  2. Call `ai_sheet_filter.select_legend_sheets(session, plan.id)` → `legend_sheets`. (Some overlap is fine — `'%legend%'` matches both filters; the schedule extractor will return `[]` on a page with only legend artwork, and vice versa.)
  3. Cache-check per sheet via `compute_sheet_content_hash` + per-stage cache keys.
  4. Download PDF once via `storage.download_bytes(storage.PLANS_BUCKET, plan.storage_path)`; open with `fitz` once; iterate pages.
  5. Run schedule extractor on `schedule_sheets`; legend extractor on `legend_sheets`.
  6. Bulk-insert `extracted_schedules`, `extracted_legends`, `extracted_legend_variants`; `cache_put` per sheet.
  7. `merge_summary_jsonb_sync` writes `{schedules_legends: {schedules_extracted, schedules_by_method, schedules_by_strategy, legend_symbols_extracted, legend_variants_extracted, tag_column_method_breakdown, legend_skipped_low_confidence, errors}}`.
  8. `update_summary_counters_sync` increments `stage_3_schedules`, `stage_3_legends`, `stage_3_legend_variants`, `stage_3_cache_hits`.
- Wire `stage_schedules_legends` task body to `_stage_schedules_legends_body` instead of `_noop_stage`.

## Settings

`[backend/app/config.py](backend/app/config.py)` adds:

- `ai_schedules_llm_provider: str = "openai"` / `ai_schedules_llm_model: str = "gpt-4o-mini"`
- `ai_schedule_vision_dpi: int = 200`
- `ai_schedule_bbox_padding_pts: float = 40.0` (matches prototype)
- `ai_legend_template_dpi: int = 300`
- `ai_legend_min_confidence: float = 0.6`
- `ai_legend_min_rect_size_pts: int = 16` (matches prototype `min_size`)
- `ai_legend_rect_tolerance_pts: int = 2` (matches prototype `tolerance`)
- `ai_legend_label_directions: str = "right,below,above,left"` (CSV; prototype is `"right"` only)
- `ai_legend_detect_circles: bool = True`
- `ai_legend_detect_polygons: bool = True`
- `ai_legend_template_scales: str = "0.70,0.85,1.00,1.15,1.30"` (CSV)
- `ai_legend_template_rotations: str = "0,90,180,270"` (CSV)
- `ai_tag_column_score_threshold: float = 0.7` / `ai_tag_column_score_margin: float = 0.1`

Documented in `[backend/.env.example](backend/.env.example)`.

## Internal debug surface

- `[backend/app/api/v1/internal_ai_extractions.py](backend/app/api/v1/internal_ai_extractions.py)` — `GET /internal/ai/runs/{ai_run_id}/extractions`, `require_role("owner", "admin")`. Returns extracted schedule tables + legend symbol thumbnails (signed URLs to primary variant only) + per-method counters.
- `[frontend/app/internal/ai/runs/[runId]/extractions/page.tsx](frontend/app/internal/ai/runs/[runId]/extractions/page.tsx)` — debug page rendering both. Owner+admin gated client-side too. Variant gallery shown on click.

Wire route into `[backend/app/api/router.py](backend/app/api/router.py)` (`protected.include_router(internal_ai_extractions.router)`).

## Tests (boundary-mocked, no live API calls)

- `backend/tests/unit/test_ai_sheet_filter.py` — keyword filter SQL produces correct sheet sets for fixture data.
- `backend/tests/unit/test_ai_schedule_extractor.py` — fixture PDFs for `lines_strict` (primary), `lines`, `text` strategies; row-width-variance scorer; vision-fallback escalation when all three pdfplumber paths fail (mocked vision call).
- `backend/tests/unit/test_ai_tag_column.py` — 4-feature scorer matrix; heuristic vs LLM fallback margin gating; description / quantity / dimension / material column ID; LLM cache hit (mocked OpenAI client).
- `backend/tests/unit/test_ai_legend_detector.py` — prototype-parity tests (rect clustering on synthetic page matching `[AI/controller/legends.py](AI/controller/legends.py)` output); multi-direction label search; circle/polygon detection; confidence score thresholds.
- `backend/tests/unit/test_ai_legend_extractor.py` — multi-scale variant generation (5×4 = 20 variants); storage upload mocked at `app.utils.storage.upload_bytes`; deterministic filename; `template_hash` computation; `extracted_legends` + `extracted_legend_variants` row insertion shape.
- Extend `backend/tests/unit/test_ai_pipeline_tasks.py` — `stage_schedules_legends` happy path; cache-hit path; partial-failure path (one sheet errors, others succeed); empty-sheets path (no schedule/legend keywords matched).
- Extend `backend/tests/unit/test_ai_models.py` — `AnthropicVisionModel.extract_structured` (mocked SDK).

## Documentation cleanup (final task)

- Update `[sprints/ai/roadmap.md](sprints/ai/roadmap.md)`:
  - "What shipped in AI-02b" — replace user-drawn-bbox spec with actual auto-name-sheets implementation.
  - Add "What shipped in AI-03" entry.
  - Add **AI-03b** stub (manual legend bbox override, modelled on AI-02b's auto-name pattern).
  - Add **AI-03c** stub (classifier improvement: replace vision-on-thumbnail with text-LLM-on-title).
- Update `[sprints/ai/sprint-ai-02b.md](sprints/ai/sprint-ai-02b.md)` Part B section to reflect auto-name-sheets reality.
- Update `[docs/architecture/ai-pipeline.md](docs/architecture/ai-pipeline.md)` with the new stage body description.

## Acceptance gates (before declaring sprint done)

- All migrations apply cleanly. New tests pass; AI-01/AI-02/AI-02b tests still green.
- Schedule extraction on the `[AI/data/d1](AI/data/d1)` test plan finds the same 9 schedule pages as `[AI/data/d1/schedules.json](AI/data/d1/schedules.json)` (prototype parity verification).
- Legend extraction on a page with the prototype's input produces the same merged-rects output as `[AI/controller/legends.py::find_rectangles_text](AI/controller/legends.py)` (prototype parity verification).
- Heuristic-only schedule extractions cost zero cents (verified via mocked cost wrapper).
- Re-running on the same plan with no changes yields a 100% cache hit on Stage 3a (verified via integration test).
- The internal debug page renders extracted tables and legend thumbnails for an arbitrary `ai_run_id`.

## Deferred to future sprints

- **AI-03b — Manual legend bbox override.** Async non-blocking "Set legend region" button; new POST endpoint stores bbox + triggers per-sheet re-extract Celery task. Modelled on AI-02b's `auto-name-sheets`.
- **AI-03c — Classifier improvement.** Replace AI-02's vision-on-thumbnail fallback with text-LLM-on-title (~$0.0001 per call, faster, more accurate). Strict JSON schema constrained to `ALL_DISCIPLINES` + `ALL_SHEET_TYPES`. Cache by `(sheet_name + sheet_number)` hash.
- **AI-05 / future UX work** — Per-sheet AI-extraction-counts indicator in sheet index (UX design needed before implementation; need to decide what density of information is right for the left rail).
- **Future UI polish** — Discipline + sheet-type pills in sheet-index row (currently commented out at `[frontend/components/plan-viewer/sheet-index.tsx:816-832](frontend/components/plan-viewer/sheet-index.tsx)`); needs visual design pass.
