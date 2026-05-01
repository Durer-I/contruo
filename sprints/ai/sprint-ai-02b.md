# Sprint AI-02b: Title Block Manual Override + Inline Sheet Rename

> **Track:** AI / Auto-Takeoff
> **Duration:** 1 week
> **Status:** Partial — inline sheet rename **shipped (2026-04)**;
> manual title-block bbox flow **reset, redesign in progress**.
> **Depends On:** Sprint AI-02 (Stage 2 sheet classification, OCR helpers,
> sheet-index UI).

## Sprint Goal

Two intentionally separate, independently shippable flows that together let
estimators correct bad sheet names without ever waiting on AI:

1. **Inline sheet rename** in the sheet index → marks that sheet as
   `'manual'` → protected from any future re-extraction (AI run or manual
   re-extract task). **Shipped.**
2. **Manual title-block bbox on the live PDF** → persists per plan →
   re-extracts every sheet → never overwrites manual renames.
   **Reset for redesign.** The first cut shipped in 2026-04 was withdrawn
   after real-world use because:
   - The drag-rect → 4-point bbox round-trip across canvas ↔ pdf.js
     viewport had directional ambiguity (top/bottom + left/right
     occasionally flipped after rotation/heterogeneous page sizes).
   - Per-sheet re-extraction quality was too low even when the bbox was
     correct (text-layer empty on raster sheets, OCR fallback noisy on
     mixed-glyph plans).

Sprint AI-02's auto-detection + pause/resume confirm-dialog flow is fully
removed (see "What was reset" below). AI-02b is now the single owner of
title-block work in the codebase.

---

## Status snapshot (2026-04-30)

| Area | Status | Notes |
|------|--------|-------|
| Inline sheet rename | **Shipped** | `PATCH /api/v1/sheets/{id}`, `sheet_name_source='manual'`, sheet-index UI. |
| Manual title-block API + worker | **Reset** | Deleted: `plan_title_block.py` route, `set_manual_title_block` service, `reextract_plan_titles_task`, `extract_title_for_sheet`, `reextract_titles_for_plan`. |
| Stage 1 pipeline body | **No-op** | `stage_title_block` runs as `_noop_stage` — chain still walks 6 stages, contributes a zero-cost timing entry. |
| Auto-detection / pause / resume | **Removed** | Deleted: `ConfirmTitleBlockRequest`, `confirm_title_block` endpoint, `pause_run_for_title_block_sync`, `resume_run_after_title_block`, `awaiting_title_block` status, the `summary_jsonb.pause` payload. |
| DB columns from migration `014` | **Kept** | `plans.title_block_bbox`, `title_block_confidence`, `title_block_source` stay. The next attempt will reuse them; rolling back the column would just create a follow-up migration when AI-02b lands. |
| `sheets.sheet_name_source` (migration `015`) | **Kept** | Powers the manual-rename guard; future re-extraction will respect it. |

---

## Part A — Inline Sheet Rename (shipped)

The cheap, high-value half of AI-02b. Lets a user fix one wrong name in the
sheet index without paying for a re-extract.

### What shipped

| Area | Deliverable |
|------|-------------|
| **DB** | Migration `015` — `sheets.sheet_name_source VARCHAR(20) NULL` (`'auto'` \| `'manual'` \| `NULL`); model + `SheetSummary` + `SheetListItemResponse` + `SheetInfo` carry it through. |
| **API** | `PATCH /api/v1/sheets/{id}` → `sheet_service.rename_sheet(...)`. Trims, validates non-empty, sets `sheet_name = body.sheet_name` and `sheet_name_source = 'manual'`. Permission: `EDIT_MEASUREMENTS`. Empty/whitespace returns 422 with `SHEET_NAME_EMPTY`. |
| **UI** | `sheet-index.tsx`: pencil button + double-click → inline `<input>` (Enter saves, Esc cancels), optimistic update with revert-on-error, subtle dot indicator for `sheet_name_source === 'manual'`. New client `frontend/lib/sheets.ts::renameSheet`. |
| **Tests** | `test_sheet_rename_endpoint` (4 cases: happy path, empty rejected, whitespace-only rejected, permission denied). All green. |

### Manual-source contract

`sheet_name_source` is the source of truth and is **sacred** once set to
`'manual'`:

- A future title-block re-extractor (`allow_overwrite_auto=True` or
  `False`) MUST skip rows where `sheet_name_source = 'manual'`.
- A new auto write MUST set `sheet_name_source = 'auto'` (never `NULL`).
- `NULL` is treated as `'auto'` for safety: legacy rows from the upload
  pipeline are eligible for overwrite on the first re-extract.

This contract is encoded once in the helper that the AI-02b redesign will
restore (`ai_title_block._is_manual_safe`). Any future writer goes through
that single guard.

---

## Part B — Manual Title-Block Bbox (reset)

### What was reset

Reset to a clean slate after AI-02 + the first AI-02b cut both failed
real-world use:

| Removed | Reason |
|---------|--------|
| `backend/app/services/ai_title_block.py` | Whole module — auto-detect heuristic + manual extractor + helper. |
| `backend/app/api/v1/plan_title_block.py` | Manual-bbox endpoint + the dependency on `set_manual_title_block`. |
| `backend/app/schemas/ai_title_block.py` (`TitleBlockBbox`, `ConfirmTitleBlockRequest`) | Used by the deleted endpoints. |
| `backend/app/schemas/plan_title_block.py` (`SetManualTitleBlockRequest/Response`) | Same. |
| `backend/app/api/v1/ai_runs.py::confirm_title_block` | Auto-detect pause-resume entrypoint. |
| `backend/app/services/ai_run_service.py::pause_run_for_title_block_sync`, `resume_run_after_title_block`, `PAUSE_STATUS_AWAITING_TITLE_BLOCK` | Pause/resume helpers. |
| `backend/app/services/plan_service.py::set_manual_title_block` | Persist + invalidate-cache helper. |
| `backend/app/tasks/ai_pipeline.py::_stage_title_block_body`, `per_sheet_extract_title_task`, `reextract_plan_titles_task`, `TITLE_BLOCK_DETECT_VERSION` | All Stage-1 work. |
| `frontend/lib/ai-title-block.ts` | `confirmTitleBlock` + `setManualTitleBlock`. |
| `frontend/components/plan-viewer/title-block-confirm-dialog.tsx` | Auto-detect confirmation modal. |
| `frontend/components/plan-viewer/run-auto-takeoff-button.tsx::onResumeFromPause` + `awaiting_title_block` pill | Pause-aware UI. |
| `plan-viewer-workspace.tsx` "Set title block" toolbar + draw-mode state + `aiPaused` / `samplePagePdf` / `titleBlockSampleThumb` | Inline draw flow. |
| `plan-pdf-canvas.tsx::titleBlockDrawMode` / `onTitleBlockPdfDrag` / `titleBlockDraftPdf` overlay | Draw-mode rendering. |
| `frontend/lib/ai-runs.ts::AiRunPausePayload`, `'awaiting_title_block'`, `TitleBlockBboxPdf`, `summary_jsonb.pause` field | Type surface for the pause flow. |
| Backend tests: `test_ai_title_block`, `test_ai_title_block_endpoint`, `test_ai_pause_resume`, `test_plan_title_block_endpoint`, the title-block sections of `test_ai_pipeline_tasks` | Tests for the deleted code. |
| Settings: `ai_title_block_confidence_threshold` | Auto-detect pause threshold. |
| Requirements: `numpy`, `opencv-python-headless`, `matplotlib` | Pulled in for an aborted prototype port; verified absent from `requirements.txt` after the reset. |

### What is preserved

| Kept | Reason |
|------|--------|
| `plans.title_block_bbox`, `title_block_confidence`, `title_block_source` (migration `014`) | The next attempt will reuse these columns. |
| `ai_runs.status VARCHAR(40)` (migration `014`) | Already deployed; widening leaves room for a future `awaiting_*` pause. |
| `app/services/ai_ocr.py` + `app/utils/pdf.py::extract_text_in_rect`, `render_clip_to_png` | OCR + clip helpers stay; AI-02b will reuse them as the per-sheet extractor. |
| `app/services/ai_cache.py::cache_invalidate` | Invalidation helper stays; future bbox save will use it. |
| The pipeline chain shape — `start → title_block (no-op) → classification → schedules_legends → element_detection → resolver_and_layer_write → finalize` | Six-stage walk preserved. AI-02b will swap a body in via `_run_stage` without touching the chain wiring. |

---

## Redesign target — Manual Title-Block Bbox v2

Concrete spec for the next attempt. **Not yet implemented.**

### Goals

1. User draws the title-block region **once per plan** on the live PDF.
   Bbox is captured in PDF user-space points (not canvas pixels).
2. Persist on `plans.title_block_bbox` with `title_block_source='manual'`,
   `title_block_confidence=1.0`.
3. Trigger a single Celery task that re-extracts every sheet's
   `sheet_name`, respecting the `sheet_name_source='manual'` guard.
4. Re-extract per sheet uses (a) PDF text-layer first, (b) OCR fallback
   only if the text layer is empty or not found.
5. AI runs that subsequently fire pick up the saved bbox automatically;
   Stage 1 stops being a no-op.

### Non-goals

- **No** auto-detection on re-introduction. Manual is the only path until
  re-extract quality is measurably above the noise floor (~90% correct on
  a 50-sheet test set across 3 disciplines).
- **No** pause/resume / `awaiting_title_block` status. AI runs require the
  bbox to be pre-set; without it Stage 1 stays a no-op (sheets keep their
  upload-time names; classification still runs).
- **No** numpy / opencv / matplotlib. OCR goes through `pytesseract` +
  `app/utils/pdf.py::render_clip_to_png` (existing helper).

### Coordinate system contract

Two prior attempts failed because the canvas → PDF transform was
ambiguous. The redesign locks one direction down up front:

- The drawing UI uses **pdf.js's** `viewport.convertToPdfPoint(cssX, cssY)`
  (origin top-left, y grows down, points are 1/72 inch). NEVER use canvas
  pixel coords for storage; always map to PDF points before submit.
- Backend assumes the same convention everywhere
  (`fitz.Rect(x0, y0, x1, y1)` with `y1 > y0`). Validate `x1 > x0` and
  `y1 > y0` at the schema layer; reject empty/inverted rects with a
  `VALIDATION_ERROR`.
- For plans with **heterogeneous page sizes** (rare: title-block sheet is
  8.5×11, plan sheets are 24×36), capture `source_sheet_id` alongside the
  bbox and re-project proportionally per sheet:
  `fx = bbox.x / source_sheet.width_pts`, then
  `target_x = fx * target_sheet.width_pts`. Same for y.

### Per-sheet extraction policy

```
for each sheet in plan (ordered by page_number):
    if sheet.sheet_name_source == 'manual':
        skipped_manual += 1; continue
    text = pdf.get_text("text", clip=bbox_for_this_sheet)
    if text.strip():
        sheet.sheet_name = clean(text); method = "text_layer"
    else:
        png = render_clip_to_png(page, bbox)
        text = ai_ocr.ocr_image_bytes(png)
        if text.strip():
            sheet.sheet_name = clean(text); method = "ocr"
        else:
            method = "empty"
    sheet.sheet_name_source = 'auto'
    written += 1
```

`clean()` collapses internal whitespace runs to single spaces, strips
leading/trailing whitespace, and truncates to 250 chars (the existing
`MAX_TITLE_CHARS` bound).

### Surface area to land

| Layer | What | Where it goes |
|-------|------|---------------|
| **Schema** | `TitleBlockBbox(x0, y0, x1, y1: float)` with `x1>x0` / `y1>y0` validation. `SetManualTitleBlockRequest{bbox_pdf, source_sheet_id?}`. `SetManualTitleBlockResponse{plan_id, bbox_pdf, source, task_id}`. | New `app/schemas/plan_title_block.py`. |
| **Service** | `plan_service.set_manual_title_block(...)` — persists bbox + sets `title_block_source='manual'` + `title_block_confidence=1.0`. | New code in `plan_service.py` (regression-safe: was previously there). |
| **Service** | `ai_title_block.extract_title_for_sheet(session, sheet, bbox, *, ocr_fallback=True)` returning `TitleExtractionResult(sheet_id, title, method)`. `reextract_titles_for_plan(session, plan, bbox, *, allow_overwrite_auto, reference_sheet_id)` returning `ReextractCounters`. `_is_manual_safe(sheet, allow_overwrite_auto)` guard. | New `app/services/ai_title_block.py`. |
| **API** | `POST /api/v1/projects/{pid}/plans/{plan_id}/title-block` — 202 with the bbox + queued task id. Validates `plan.status == 'ready'`. | New `app/api/v1/plan_title_block.py`. Wire into `app/api/router.py`. |
| **Worker** | `reextract_plan_titles_task(plan_id, bbox, source_sheet_id?)` — acquires per-plan advisory lock (retry on busy), calls helper with `allow_overwrite_auto=True`. | New code in `app/tasks/ai_pipeline.py`. |
| **Pipeline** | Replace `stage_title_block` no-op body with `_stage_title_block_body` that requires `plan.title_block_bbox` (or stays a no-op if missing) and calls the helper with `allow_overwrite_auto=False` (COALESCE on AI re-runs). Restore `TITLE_BLOCK_DETECT_VERSION` for cache key. | `app/tasks/ai_pipeline.py`. |
| **Cache** | On manual-bbox save, `ai_cache.cache_invalidate(plan, stage='title_block', model_version=*)`. After re-extract, `cache_put` keyed on PDF-bytes hash + bbox so a later AI run with the same bbox is a cache hit. | Existing `ai_cache` helpers. |
| **Frontend lib** | `frontend/lib/ai-title-block.ts::setManualTitleBlock(projectId, planId, body)` returning `SetManualTitleBlockResponse`. | New file. |
| **Frontend UI** | "Set title block" toolbar action in the plan viewer that opens a **modal** (NOT inline canvas mode — the prior inline rect was directionally ambiguous). The modal renders the active sheet's PDF page via pdf.js, captures a single drag, converts to PDF points via `viewport.convertToPdfPoint`, and POSTs. | New `frontend/components/plan-viewer/set-title-block-dialog.tsx`. |
| **Frontend wire** | Add `set-title-block-dialog` open state + a toolbar button gated to `EDIT_MEASUREMENTS`. On 202 → toast + `onSheetsRefresh()` after a short delay (re-extract is single-pass per plan, sub-second on 50-sheet plans). | `plan-viewer-workspace.tsx`. |
| **Types** | Re-add `TitleBlockBboxPdf {x0, y0, x1, y1}` somewhere (probably back in `lib/ai-title-block.ts`, NOT `lib/ai-runs.ts`). `PlanInfo` already exposes `title_block_bbox` / `title_block_source` in `frontend/types/project.ts`. | Existing types. |

### Tests to land alongside the redesign

1. `test_ai_title_block.py` — `extract_title_for_sheet` happy path (text-layer hit, OCR hit, empty); `_is_manual_safe` matrix; `reextract_titles_for_plan` (manual-safe guard, COALESCE pipeline mode, empty plan, mismatched page sizes via `source_sheet_id` → re-projection).
2. `test_plan_title_block_endpoint.py` — happy path → 202 with task id; `PLAN_NOT_READY` 409; `PLAN_PROJECT_MISMATCH` 400; bbox validation 422.
3. `test_ai_pipeline_tasks.py` — Stage 1 with bbox set → calls helper with `allow_overwrite_auto=False`; Stage 1 with bbox missing → stays no-op; `reextract_plan_titles_task` happy path → calls helper with `allow_overwrite_auto=True`; `reextract_plan_titles_task` lock-busy → retries; lock-released-on-error.
4. Frontend: at minimum an integration test for the bbox → PDF-points conversion math (`viewport.convertToPdfPoint` round-trip on a known fixture).

### Acceptance criteria

- [ ] User can draw a title-block bbox once per plan; the bbox persists on
      reload.
- [ ] After saving, every sheet's `sheet_name` is refreshed within 5s on a
      50-sheet plan; manual-rename rows are untouched.
- [ ] Running AI Auto-Takeoff after the bbox is saved performs Stage 1 as
      a cache hit (no double extraction).
- [ ] If the bbox is **not** set, AI Auto-Takeoff still completes
      successfully — Stage 1 is a no-op, classification still runs on
      whatever sheet names exist (upload-time defaults, manual edits, or
      the rare empty case).
- [ ] OCR is used only when the text layer is empty for a given sheet
      (instrumented via the `method` counter in `summary_jsonb`).
- [ ] No `numpy` / `opencv` / `matplotlib` in `requirements.txt`.

---

## Out of scope (intentionally)

- **No** auto-detection of the title-block region. The 3-sample heuristic
  shipped in AI-02 was unreliable enough that the manual flow always wins
  in practice. Revisit only if the manual flow's measured success rate
  exceeds 95% on a representative set and there's a clear signal that the
  heuristic adds enough lift to justify the extra surface area.
- **No** label-anchored parser (`Name:` / `Number:` regex inside the
  bbox). Easy follow-on inside `extract_title_for_sheet` once the bbox
  capture is solid.
- **No** real-time progress broadcast for the re-extract task; the client
  refetches the sheet list shortly after the 202.
- **No** bulk "force re-extract over manual edits" — inline rename is the
  documented fix for one-off wrong names.

---

## Key references

- Sheet-rename endpoint: `backend/app/api/v1/sheets.py::rename_sheet`
- Sheet-rename service: `backend/app/services/sheet_service.py::rename_sheet`
- Sheet-rename UI: `frontend/components/plan-viewer/sheet-index.tsx`
- Sheet-rename client: `frontend/lib/sheets.ts::renameSheet`
- Existing helpers the redesign reuses:
  - `backend/app/services/ai_ocr.py` — Tesseract wrapper.
  - `backend/app/utils/pdf.py::extract_text_in_rect`,
    `render_clip_to_png`, `render_thumbnail_for_classification`.
  - `backend/app/services/ai_cache.py` — content-hash cache + invalidation.
- Pipeline chain: `backend/app/tasks/ai_pipeline.py::build_pipeline_chain`
- `sheet_name_source` model field: `backend/app/models/sheet.py`
