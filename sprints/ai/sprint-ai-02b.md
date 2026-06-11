# Sprint AI-02b: Inline Sheet Rename + Auto-Name Sheets

> **Track:** AI / Auto-Takeoff
> **Duration:** 1 week
> **Status:** **Complete (2026-05).** Both Part A (inline sheet rename) and Part B (auto-name sheets, replacing the original manual-bbox redesign goal) are shipped.
> **Depends On:** Sprint AI-02 (Stage 2 sheet classification, OCR helpers, sheet-index UI).

## Sprint Goal

Two intentionally separate, independently shippable flows that together let
estimators correct bad sheet names without ever waiting on the next AI run:

1. **Inline sheet rename** in the sheet index → marks that sheet as
   `'manual'` → protected from any future re-extraction (AI run or
   auto-name task). **Shipped.**
2. **Auto-name sheets** (a "Auto-name sheets" button on the plan viewer) →
   non-blocking Celery task that re-extracts `sheet_name` + `sheet_number`
   from the title block of every sheet → never overwrites manual renames.
   **Shipped.** This replaced the original "manual title-block bbox"
   design after the first cut of that flow was withdrawn (drag-rect
   coordinate-system bugs + low extraction quality even with a correct
   bbox); auto-detect proved reliable enough on the bottom-right corner
   of every plan we tested that the manual-draw step was unnecessary.

Sprint AI-02's auto-detection + pause/resume confirm-dialog flow is fully
removed (see "What was reset" below). AI-02b is the single owner of
title-block work in the codebase.

---

## Status snapshot (2026-05)

| Area | Status | Notes |
|------|--------|-------|
| Inline sheet rename | **Shipped** | `PATCH /api/v1/sheets/{id}`, `sheet_name_source='manual'`, sheet-index UI. |
| Auto-name sheets API | **Shipped** | `POST /api/v1/projects/{pid}/plans/{plan_id}/auto-name-sheets` enqueues `ai_pipeline.reextract_plan_titles_task`. Acquires the per-plan AI lock. |
| Auto-name sheets worker | **Shipped** | `ai_title_block.reextract_titles_for_plan` runs heuristic (bottom-right corner text layer) → `ai_ocr` Tesseract fallback → `OpenAILLMModel.structured_output` cleanup pass. Manual rows (`sheet_name_source='manual'`) skipped via `_is_manual_safe`. |
| Sheet number column | **Shipped** | Migration `016` adds `sheets.sheet_number VARCHAR(40)`. Both `sheet_name` and `sheet_number` are guarded together by `sheet_name_source`. |
| Plan viewer button | **Shipped** | "Auto-name sheets" alongside "Run Auto-Takeoff" in the plan viewer header. Disabled by `AI_AUTO_NAME_ENABLED=false`. |
| Liveblocks broadcast | **Shipped** | `sheets.auto_named` event prompts the sheet index to refetch. |
| Stage 1 pipeline body | **N/A** | The AI pipeline no longer has a counted `title_block` stage; auto-name is a standalone task. The original `_stage_title_block_body` is gone. |
| Manual draw-bbox UI | **Not built** (decision: not needed) | The auto-name flow proved the bbox is reliably the bottom-right corner. A manual draw override is not justified by current evidence. |
| Auto-detection / pause / resume | **Removed** | Deleted in the AI-02 reset: `ConfirmTitleBlockRequest`, `confirm_title_block` endpoint, `pause_run_for_title_block_sync`, `resume_run_after_title_block`, `awaiting_title_block` status. |
| DB columns from migration `014` | **Kept (dormant)** | `plans.title_block_bbox`, `title_block_confidence`, `title_block_source` are not written by the auto-name flow; left in place for a future plan-level guided-bbox feature without an extra migration. |

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

## Part B — Auto-Name Sheets (shipped; replaces "Manual Title-Block Bbox v2")

### Why the design changed

The redesign target this sprint originally pointed at was a draw-rect
bbox flow. While speccing it, we tested the bottom-right-corner heuristic
that powers the underlying extractor on the real plan set we had on hand
and it was correct on every sample. That flipped the cost/benefit:

- The extractor (text layer → OCR → LLM cleanup) is the part that
  matters. The bbox UX exists only to feed it a region.
- If the extractor can find the region itself with enough reliability,
  the manual draw step is pure friction.
- A user-visible "Auto-name sheets" button delivers the same outcome
  (corrected sheet names + sheet numbers) faster, with no canvas-↔-pdf.js
  coordinate-system bugs to debug.

So Part B was rebuilt as a one-click "Auto-name sheets" task. The
draw-bbox flow is not dead — it's deferred to a future sprint *only* if
real-world data shows the heuristic missing the title block on enough
plans to justify the surface area.

### What shipped

| Layer | Deliverable |
|-------|-------------|
| **DB** | Migration `016` — `sheets.sheet_number VARCHAR(40) NULL`. Both `sheet_name` and `sheet_number` are guarded together by `sheet_name_source` (one rename pins both fields). |
| **Service** | `app/services/ai_title_block.py` — four-stage `extract_title_for_sheet(page, ...)` (text layer → right-strip text layer → OCR → heuristic parser → LLM cleanup) and plan-level `reextract_titles_for_plan(session, plan, *, pdf_bytes, overwrite_manual=False, llm_fallback=True)` returning `ReextractCounters`. |
| **Service** | `app/services/ai_models.py::get_title_block_llm()` factory returning an `OpenAILLMModel` with strict JSON-schema `structured_output(...)`. Used by `llm_extract(text)` in `ai_title_block`. Provider configurable via `AI_TITLE_BLOCK_LLM_PROVIDER`. |
| **API** | `POST /api/v1/projects/{pid}/plans/{plan_id}/auto-name-sheets` (in `app/api/v1/plan_title_block.py`). Body: `AutoNameSheetsRequest{overwrite_manual: bool = false}`. Returns 202 `AutoNameSheetsResponse{plan_id, task_id, queued_at}`. Errors: 404 `PLAN_NOT_FOUND`, 409 `PLAN_NOT_READY`, 503 `AUTO_NAME_DISABLED` (when `AI_AUTO_NAME_ENABLED=false`). |
| **Worker** | `app/tasks/ai_pipeline.py::reextract_plan_titles_task(plan_id, overwrite_manual=False)` — acquires the per-plan advisory lock, fetches PDF bytes from storage, calls the helper, broadcasts `sheets.auto_named` into the project's Liveblocks room with per-method counters on completion. |
| **Pre-pipeline hook** | The same worker also runs (best-effort) at the start of `ai_pipeline` (between `start` and the counted stages), so an AI Auto-Takeoff run also auto-names sheets first. Failures are logged and do NOT fail the run. |
| **Frontend lib** | `frontend/lib/sheets.ts::autoNameSheets(projectId, planId, options?)` posting `{overwrite_manual}`. |
| **Frontend UI** | "Auto-name sheets" button in the plan viewer header (alongside "Run Auto-Takeoff"). `sheet-index.tsx` listens for the `sheets.auto_named` Liveblocks broadcast and refetches; a short polling backstop covers connection drops. |
| **Tests** | `test_ai_title_block` (heuristic / OCR / LLM branches, manual-safe guard, COALESCE writes), `test_auto_name_sheets_endpoint` (happy path 202, disabled flag 503, plan-not-ready 409), `test_reextract_plan_titles_task` (broadcast on success, lock-busy retry, LLM-failed counter, manual-rows-untouched). All green. |

### What was intentionally NOT built

- The draw-rect title-block bbox UI. Decision: ship the user value
  without the UX surface; revisit only if real-world data shows the
  bottom-right corner heuristic missing.
- A "Force re-name over manual edits" toggle. Inline sheet rename
  remains the documented escape hatch.
- Per-sheet progress broadcast. The Liveblocks `sheets.auto_named`
  event triggers a single refetch on completion; a 50-sheet plan is
  sub-second so granular progress is overkill.

### Manual-source contract (unchanged from Part A)

Auto-name does not weaken Part A's guarantee:

- The worker filters out `sheet_name_source = 'manual'` rows via
  `_sheet_eligible_for_auto_name(sheet, *, overwrite_manual)` — a single
  chokepoint in `ai_title_block.py`. Both `sheet_name` and `sheet_number`
  are guarded together; manually renaming a sheet pins both fields.
- The worker writes `sheet_name_source = 'auto'` on every successful
  write so the next run can overwrite it again.
- COALESCE writes: if the extractor returns name-only or number-only,
  the missing field is preserved (never wiped to NULL).
- The API supports `overwrite_manual: true` in the request body for
  programmatic re-extracts, but the frontend "Auto-name sheets" button
  does not currently surface that affordance.

---

## Out of scope (intentionally)

- **No** real-time progress broadcast for individual sheets — one
  `sheets.auto_named` event after the worker finishes is sufficient.
- **No** bulk "force re-name over manual edits" — inline rename is the
  documented fix for one-off wrong names; auto-name strictly respects
  the manual flag.
- **No** numpy / opencv / matplotlib. Auto-name uses `pdfminer` for the
  text layer, `pytesseract` for OCR fallback, and `OpenAILLMModel` for
  cleanup.
- **No** drawing the title-block region by hand. Deferred until evidence
  shows the auto-detect missing on real plans.

---

## Key references

- Sheet-rename endpoint: `backend/app/api/v1/sheets.py::rename_sheet`
- Sheet-rename service: `backend/app/services/sheet_service.py::rename_sheet`
- Sheet-rename UI: `frontend/components/plan-viewer/sheet-index.tsx`
- Sheet-rename client: `frontend/lib/sheets.ts::renameSheet`
- Auto-name endpoint: `backend/app/api/v1/plan_title_block.py::auto_name_sheets`
- Auto-name worker: `backend/app/tasks/ai_pipeline.py::reextract_plan_titles_task`
- Auto-name helper: `backend/app/services/ai_title_block.py::reextract_titles_for_plan`
- Per-sheet extractor: `backend/app/services/ai_title_block.py::extract_title_for_sheet`
- Heuristic parser: `backend/app/services/ai_title_block.py::parse_title_block_heuristic`
- LLM cleanup factory: `backend/app/services/ai_models.py::get_title_block_llm` (returns `OpenAILLMModel`)
- Manual-safe guard: `backend/app/services/ai_title_block.py::_sheet_eligible_for_auto_name`
- `sheet_name_source` / `sheet_number` model fields: `backend/app/models/sheet.py`
- Frontend client: `frontend/lib/sheets.ts::autoNameSheets`
- Existing helpers the worker reuses:
  - `backend/app/services/ai_ocr.py` — Tesseract wrapper (with `title_block` preprocessor).
  - `backend/app/utils/pdf.py::extract_text_in_rect`, `render_clip_to_png`.
- Liveblocks broadcast: `sheets.auto_named` (consumed by `frontend/components/plan-viewer/sheet-index.tsx`).
