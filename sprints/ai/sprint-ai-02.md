# Sprint AI-02: Sheet Classification

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Complete (2026-04). _Title-block work was reset; see
> [Sprint AI-02b](sprint-ai-02b.md)._
> **Depends On:** Sprint AI-01

## Sprint Goal

Implement Stage 2 (Sheet Classification) of the AI Auto-Takeoff pipeline.
After this sprint, an estimator who runs auto-takeoff sees every sheet
tagged in the sheet index with discipline (Architectural / Structural /
MEP / etc.) and sheet type (Plan / Schedule / Legend / etc.).

> **Title block (Stage 1) was originally scoped here too** — auto-detect
> heuristic, low-confidence pause/resume, and a confirm dialog. The full
> flow (auto-detect AND the first-cut manual override that became AI-02b)
> was withdrawn after real-world use because:
>
> - Auto-detection's confidence proxies were too noisy (~50% pause rate
>   on the test set).
> - Both the auto-detect dialog and the inline draw mode had directional
>   ambiguity in the canvas-to-PDF coordinate transform.
> - Per-sheet extraction quality was too low even with the correct bbox.
>
> Stage 1 now runs as a no-op in the pipeline (`stage_title_block` →
> `_noop_stage`); see [Sprint AI-02b](sprint-ai-02b.md) for the redesign
> spec. Sheet Classification (Stage 2) shipped successfully and is
> unaffected.

---

## What shipped (summary)

| Area | Deliverable |
|------|-------------|
| **DB** | Migration `014`: `ai_runs.status` widened to `VARCHAR(40)` (left in place to leave headroom for a future `awaiting_*` pause); `plans.title_block_bbox`, `title_block_confidence`, `title_block_source` (kept; re-used by AI-02b). |
| **OCR / clip helpers** | `app/services/ai_ocr.py` (Tesseract via `AI_TESSERACT_CMD` or PATH); `app/utils/pdf.py` helpers for clip render + text-in-rect (no hardcoded binary path). _Reused by AI-02b's redesign._ |
| **Stage 2** | `ai_sheet_classifier.py`: lexical rules + batched vision fallback; skip vision for cover/index/spec at low confidence (D6); `bulk_upsert_classifications`. |
| **Vision** | `AnthropicVisionModel.classify_image` implemented (was stub in AI-01). |
| **API** | Sheet list includes classification fields. `PlanResponse` unchanged. |
| **UI** | `sheet-index.tsx` (badges, filters, low-confidence affordance). |
| **Tests** | `test_ai_sheet_classifier`, `test_ai_ocr`, `test_ai_models`, extended `test_ai_pipeline_tasks`. |
| **Docs** | `docs/architecture/ai-pipeline.md`, `backend/README.md`, `sprints/ai/roadmap.md`. |

---

## Implementation notes

- **Title column:** when AI-02b lands, titles will be written to
  `sheets.sheet_name` (not a separate `sheets.title` column); aligns with
  the live schema and with the inline-rename `sheet_name_source` contract
  shipped in AI-02b.
- **OCR location:** Tesseract lives in `app/services/ai_ocr.py`, not
  embedded as a one-off inside `pdf.py`. Wired through
  `AI_TESSERACT_CMD` so it's a config change, not a code change, to swap
  binary paths between Linux containers and Windows dev boxes.
- **Per-sheet parallelism:** when AI-02b lands, the per-sheet extractor
  will be invoked in a loop with one open PDF; chord-based parallelism is
  deferred to AI-06+.
- **Advisory lock:** plan-scoped (AI-01); held across the run until
  finalize/fail.
- **Liveblocks:** `ai_run.status_changed` with `ai_run_id`, `status`,
  `stage`, `stage_index`, `total_stages` (no bbox in payload). Granular
  per-sheet broadcasts are not part of AI-02.
- **Run summary UI:** `summary_jsonb` includes classification counters
  from the worker; the plan viewer pill shows stage names / completed
  count, not the full one-line "Stage 2 complete: N sheets…" narrative —
  that remains a polish item (e.g. AI-05).

---

## Tasks

### 1. Title Block (Stage 1) — Reset

The original AI-02 title-block scope (auto-detection + manual confirm
dialog) was implemented and then withdrawn. See
[Sprint AI-02b](sprint-ai-02b.md) for the full reset description and the
replacement design.

- [x] Stage 1 body removed from the pipeline; `stage_title_block` runs as
      `_noop_stage` (timing entry, no work).
- [x] Auto-detection / pause / resume code removed from the codebase.
- [x] Migration `014` columns kept (`title_block_bbox`,
      `title_block_confidence`, `title_block_source`) so AI-02b can drop
      straight in.
- [ ] _AI-02b will land the manual-bbox flow + the per-sheet extractor._

### 2. Lexical Sheet Classifier (Stage 2 primary)

- [x] Classifier in `backend/app/services/ai_sheet_classifier.py`:
      discipline prefixes + sheet-type keywords + confidence tiers.
- [x] Confidence from rule matrix (high when prefix + keyword align;
      decays when signals weak).

### 3. Vision Sheet Classifier (Stage 2 fallback)

- [x] When `needs_vision_fallback` (low lexical confidence and
      "interesting" sheet type), thumbnails batched to
      `VisionModel.classify_image` with a JSON schema response.
- [x] Cache: `ai_stage_cache` keyed by
      `(org_id, sheet content hash, stage='classification', model_version)`.
- [x] Batch size configurable (`AI_VISION_CLASSIFY_BATCH_SIZE`,
      default 6).

### 4. Sheet Classification Persistence

- [x] Updates `discipline`, `sheet_type`, `classification_confidence`,
      `classification_method` (`lexical` | `vision`).
- [x] `bulk_upsert_classifications` for efficient writes.

### 5. Sheet Index UI Updates

- [x] Discipline color dot + sheet-type pill in `sheet-index.tsx`.
- [x] Filter by discipline and/or sheet type; search includes
      classification fields.
- [x] Low-confidence treatment (threshold aligned with backend classifier
      settings).

### 6. Run Summary Updates

- [x] After Stage 2, `ai_runs.summary_jsonb` includes classification
      aggregates and stage counters (see `merge_summary_jsonb_sync` /
      `ClassificationCounters`).
- [ ] Run-summary **panel** copy: "Stage 2 complete: N sheets (A lexical,
      B vision). C low-confidence." — **not** built as a dedicated UI
      line this sprint; data is available on the run for a future panel
      (AI-05 polish).

### 7. Liveblocks Progress Broadcast

- [x] `ai_run.status_changed` on stage transitions (same event type as
      AI-01).
- [ ] Per-sheet fraction progress (e.g. "Stage 2: 87/142") in the
      broadcast payload — **deferred**; would require extra worker events
      and payload design.

---

## Acceptance Criteria

- [x] After Stage 2, sheets have `discipline`, `sheet_type`,
      `classification_method`, and `classification_confidence` populated
      (from lexical and/or vision).
- [x] Sheet index shows discipline/type affordances and supports
      filtering and search.
- [x] Re-run on unchanged sheets hits `ai_stage_cache` for classification
      where hashes match (no redundant vision for cached rows).
- [x] Cost: lexical-only path adds no model cost; vision path uses
      `with_cost_tracking` (unit tests mock Anthropic at the boundary).
- [x] AI-focused unit tests added/extended; AI-01 tests remain green.
      _(Broader legacy endpoint tests on `main` may still need
      subscription-guard mocks — outside this sprint.)_
- [x] **Title block:** Stage 1 is a registered no-op; the pipeline still
      walks all six stages and finalizes cleanly. The full title-block
      experience moves to AI-02b.

---

## Out of Scope

- Title block extraction → [AI-02b](sprint-ai-02b.md)
- Schedule extraction → AI-03
- Legend extraction → AI-03
- Element detection → AI-06, AI-07, AI-08
- Granular Liveblocks per-sheet progress (task 7 optional line)
- Dedicated run-summary narrative UI (task 6 optional line)

---

## Key References

- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) — Stage 2 (Sheet Classification)
- [features/ai/ai-element-recognition.md](../../features/ai/ai-element-recognition.md) — Element types and detection overview
- Architecture: [docs/architecture/ai-pipeline.md](../../docs/architecture/ai-pipeline.md) — pipeline shape, cache keys, broadcast payload
- Sheet index: `frontend/components/plan-viewer/sheet-index.tsx`
- Stage 1 redesign: [sprints/ai/sprint-ai-02b.md](sprint-ai-02b.md)
