# Sprint AI-03: Schedule + Legend Extraction

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint AI-02

## Sprint Goal

Implement Stage 3a (Schedule + Legend Extraction) of the AI Auto-Takeoff pipeline. After this sprint, every sheet classified as a schedule has its tables extracted and tag column identified, and every sheet with a legend has its symbols cropped as templates and stored in Supabase Storage. Schedules and legends drive both the condition resolver (AI-04) and the symbol detector (AI-06), so this sprint is the data-supply pipeline for everything downstream.

---

## Tasks

### 1. Multi-Strategy Schedule Extraction

- [ ] In `backend/app/services/ai_schedule_extractor.py`:
  - For each sheet classified as `sheet_type = schedule`, run pdfplumber `find_tables` with three strategies in order: `lines`, `lines_strict`, `text`
  - Score each result by row-width consistency (low variance = good table)
  - Pick the highest-scoring strategy per table
- [ ] Persist each table to `extracted_schedules` with `bbox_pdf`, `extracted_table_jsonb`, `extraction_method`

### 2. Vision Fallback for Lineless Schedules

- [ ] When all three pdfplumber strategies score poorly, render the schedule region at 200 DPI and call `VisionModel.extract_structured` with a JSON schema for `{columns: [...], rows: [[...]]}`
- [ ] Cache by `(sheet_id, schedule_bbox_hash, model_version)`
- [ ] Mark `extraction_method = vision` in `extracted_schedules`

### 3. Heuristic-First Tag Column Identification

- [ ] In `backend/app/services/ai_tag_column.py`:
  - For each `extracted_schedules` row, score each column on:
    - Header keyword match against `{MARK, TAG, NO., NUMBER, ID, KEY, TYPE, SYMBOL}` (weight 0.4)
    - Value cardinality close to row count (weight 0.2)
    - Average value length <= 6 chars and alphanumeric (weight 0.2)
    - Position (leftmost non-empty preferred) (weight 0.2)
  - Return ranked candidates with combined scores
- [ ] If top candidate score >= 0.7 and second-best is at least 0.1 lower -> use top candidate, no LLM call
- [ ] Otherwise fall back to LLM:
  - Send the table header + first 5 rows to `LLMModel.structured_output` with schema `{tag_column_index: int, confidence: float, reasoning: str}`
  - Cache by `(table_hash, model_version)`
- [ ] Persist `tag_column_index` on `extracted_schedules`

### 4. Schedule Description Column Identification

- [ ] Same heuristic + LLM fallback for the description column (longer text, often labeled "Description", "Type", or located adjacent to tag column)
- [ ] Persist `description_column_index` on `extracted_schedules`
- [ ] Also identify (when present): `quantity_column_index`, `dimension_column_indexes`, `material_column_index` -- all optional, used by AI-04 (condition resolver)

### 5. Legend Auto-Detection

- [ ] In `backend/app/services/ai_legend_detector.py`:
  - For each sheet classified as `sheet_type = legend` (or any sheet with detected legend regions), find clusters of small repeated shapes adjacent to short text labels
  - Detect shape primitives: rectangles (existing prototype logic), circles (Hough), polygons (vector path closure detection)
  - Allow text labels above, below, left, or right of the symbol (the prototype only checked right -- this fixes that)
  - Score each cluster on: shape repetition, label proximity, label brevity, layout regularity
  - Cluster -> legend region candidate

### 6. Legend Manual Fallback UI

- [ ] When auto-detection confidence < 0.6 on a sheet that the user (or classifier) marked as having a legend, the run pauses with status `awaiting_legend_box_confirmation`
- [ ] Frontend modal: shows the sheet with detected legend region (if any) and lets the user draw/correct the box
- [ ] API: `POST /api/v1/projects/{project_id}/ai/runs/{ai_run_id}/legend-box` -> accepts confirmed bbox and resumes the run

### 7. Legend Symbol Template Extraction

- [ ] For each legend region, crop each detected symbol at 300 DPI
- [ ] Store as PNG in Supabase Storage at `{org_id}/legends/{plan_id}/{legend_label}.png`
- [ ] Compute `template_hash` (SHA-256 of PNG bytes) for cache invalidation
- [ ] Persist to `extracted_legends` table: `(sheet_id, bbox_pdf, label, template_storage_path, template_hash, extraction_method)`
- [ ] Multi-scale template variants: pre-compute templates at scales 0.7x, 0.85x, 1.0x, 1.15x, 1.3x and rotations 0/90/180/270 -- store all variants under the same `legend_label`. Used by symbol detector in AI-06 for fast matching.

### 8. Legend Label OCR

- [ ] For each detected symbol, OCR the adjacent label text
- [ ] Hybrid: PyMuPDF text first, Tesseract fallback at 2x DPI when needed
- [ ] Clean up: strip punctuation noise, normalize whitespace
- [ ] LLM cleanup pass when OCR confidence is low: send candidate labels to `LLMModel.structured_output` with schema `{cleaned_label: str, confidence: float}` to remove gibberish

### 9. Run Summary Updates

- [ ] After Stage 3a completes, `ai_runs.summary_jsonb` includes:
  - `schedules_extracted` count, with per-method breakdown
  - `legend_symbols_extracted` count, per sheet
  - `tag_column_method_breakdown` (`heuristic` vs `llm_fallback`)
- [ ] UI status pill shows: "Stage 3 complete: 12 schedules, 47 legend symbols extracted"

### 10. Internal Inspection UI (debug)

- [ ] Internal-only page (`/internal/ai/runs/{ai_run_id}/extractions`) for the Contruo team to inspect extracted schedules and legends, useful for debugging detection quality across customer plans
- [ ] Shows extracted table grids and legend symbol thumbnails
- [ ] RBAC: only Contruo staff (not exposed to customer roles)

---

## Acceptance Criteria

- [ ] On a clean architectural plan set with door, equipment, and finish schedules, all schedule tables are extracted with the correct tag column identified by heuristic alone (no LLM fallback).
- [ ] On a lineless plumbing schedule, the vision fallback succeeds and the table is correctly extracted.
- [ ] Legend symbols are detected, cropped, and stored in Supabase Storage with multi-scale variants pre-computed.
- [ ] When legend auto-detection confidence is low, the user gets the manual-confirm modal and can correct the bbox in <60s.
- [ ] Run summary shows the per-method breakdown for tag-column identification (most should be heuristic).
- [ ] Re-running on the same plan hits the cache for unchanged schedules and legends; cost is near zero.
- [ ] Cost telemetry: heuristic-only schedules cost zero cents; vision/LLM-fallback schedules show non-zero `tokens_used`.
- [ ] All previous tests pass; new tests cover schedule extraction (with all three pdfplumber strategies and vision fallback), heuristic tag column scoring, and legend symbol cropping.

---

## Out of Scope

- Mapping schedule rows to Conditions -> AI-04
- Locating legend symbols on plan sheets -> AI-06
- AI Layer overlays for extracted data -> AI-05

---

## Key References

- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) -- Stage 3a (Schedule + Legend Extraction)
- [features/ai/ai-element-recognition.md](../../features/ai/ai-element-recognition.md) -- Hatch / Finish Region Detection (legend swatches)
- Existing prototypes (informational only, replaced by this sprint):
  - `AI/controller/find_tables.py`
  - `AI/controller/image_select.py`
  - `AI/controller/tables.py`
  - `AI/controller/legends.py`
