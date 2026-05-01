# Sprint AI-06: Symbol + Callout Detection

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint AI-05

## Sprint Goal

Implement Stage 3b (symbol detection) and Stage 4 (tag-to-drawing mapping) of the AI Auto-Takeoff pipeline. After this sprint, an estimator can run auto-takeoff on a plan with door, equipment, and fixture schedules and see **real count measurements** auto-created (or pending in the AI Layer) at the correct positions on plan sheets, mapped to the right conditions.

This is the first sprint where AI Auto-Takeoff produces real, end-to-end value to the estimator. Doors, windows, electrical fixtures, plumbing fixtures, and equipment counts -- the most common takeoff items in construction estimating -- become automated.

---

## Tasks

### 1. Symbol Detection via Multi-Scale Template Matching

- [ ] In `backend/app/services/ai_symbol_detector.py`:
  - For each `extracted_legends` entry from AI-03, load all pre-computed multi-scale + rotation template variants
  - For each candidate plan sheet (filtered to `sheet_type = plan` from AI-02), run `cv2.matchTemplate` with normalized cross-correlation (NCC) for every template variant
  - Aggregate response maps across variants per legend label
  - Threshold at NCC >= 0.75 (configurable per legend)
- [ ] Non-maximum suppression to dedupe overlapping detections (suppress within 1.5x template size)
- [ ] Output: `(symbol_id, position_pdf, bbox_pdf, matched_legend_label, confidence)` per detection

### 2. Sheet Filtering (Skip Schedules and Legends)

- [ ] Symbol detection runs ONLY on sheets where `sheet_type = plan`
- [ ] Skip `schedule`, `legend`, `cover`, `index`, `spec` sheets entirely (this fixes the prototype's double-counting bug from `AI/controller/search.py`)

### 3. Vision Fallback for Unmatched Regions

- [ ] After template matching completes, identify "symbol-like density" regions on each plan sheet that have no template match (using a quick connected-components pass on small black/dark shapes)
- [ ] For high-density unmatched regions, send the cropped region + the available legend templates to `VisionModel.analyze_region` asking: "Which legend symbol (if any) does this match?"
- [ ] Cap calls per run for cost control
- [ ] Cache by `(region_hash, model_version)`

### 4. Callout Balloon Detection

- [ ] In `backend/app/services/ai_callout_detector.py`:
  - Vector path: scan `page.get_drawings()` for closed paths (circles, hexagons, clouds) with bounding box < 1 inch in world units AND containing exactly one short text string (using `page.get_text("words")`)
  - Raster fallback (only for image-only plans): Hough circle/contour detection + Tesseract OCR for tag text
- [ ] Output: `(balloon_id, position_pdf, tag_value, confidence)`

### 5. Tag-to-Schedule Mapping

- [ ] In `backend/app/services/ai_tag_mapper.py`:
  - For every detected balloon and matched symbol with a tag-like label, look up the schedule(s) that contain that tag value (from `extracted_schedules` populated in AI-03)
  - Match priority: exact tag value first, then case-insensitive, then fuzzy (Levenshtein distance <= 1)
  - Returns `(detection, schedule_id, schedule_row_index, mapped_condition_id)` -- the condition is resolved via the AI-04 resolver
- [ ] When no schedule contains the tag value: detection is still useful (it's a count); confidence dropped 20%; mapped to a generic condition for that legend label (still via the resolver)

### 6. Spatial Disambiguation (Reduce False Positives)

- [ ] Tags inside callout balloons score 1.5x higher than free-floating string matches (balloons are intentional callouts)
- [ ] Tags adjacent to leader lines (short line ending at a symbol) score 1.3x higher
- [ ] Tags inside title block, legend region, or revision block bbox -> filtered out entirely
- [ ] Tags that overlap a known room-name location (using simple text-pattern heuristics) are filtered

### 7. Coordinate Conversion

- [ ] All detection coordinates returned in PDF user space points (per AI-01 contract)
- [ ] Per-detection `position_pdf` (`{x, y}`) and optional `bbox_pdf` for symbols
- [ ] Sheet calibration check: if sheet has no scale calibration, the detection still happens (count measurements don't strictly need scale) but is marked with a warning -- estimator is prompted to calibrate before quantities accrue

### 8. AI Layer Write (Stage 6)

- [ ] For each detection passing thresholds:
  - Resolve condition via the AI-04 resolver (`resolve_condition(detected_element_metadata, ...)`)
  - Insert `ai_layer_items` row with `measurement_type = 'count'`, geometry `{type: 'count', position: {x, y}}`, confidence, source_stage = `symbol_detection` or `callout_detection`
  - High-confidence items (>= project's `auto_accept_threshold`) auto-accept and create real `Measurement` rows immediately (per AI-05 logic)

### 9. Run Summary Updates

- [ ] After Stage 4 completes, the run summary includes:
  - Per-legend detection counts: "47 doors, 89 outlets, 34 sprinklers"
  - Per-method breakdown: template-match vs vision-fallback
  - Per-confidence-tier counts
- [ ] UI: "AI detected 184 elements across 12 sheets. 142 auto-accepted, 31 to review, 11 low-confidence hidden."

### 10. Internal QC View (Debug)

- [ ] Internal page (`/internal/ai/runs/{ai_run_id}/symbols`) showing per-sheet detections with template thumbnails and confidence scores -- helps the Contruo team tune thresholds across customer plans

---

## Acceptance Criteria

- [ ] On a clean architectural plan set with door and equipment schedules, AI auto-takeoff produces correct count measurements for all doors, equipment items, and fixtures with > 90% precision and > 80% recall (measured on a labeled test plan set).
- [ ] Detections happen on plan sheets only -- never on schedule, legend, cover, or spec sheets (no double-counting).
- [ ] Detections inside title blocks, legends, or revision blocks are filtered out.
- [ ] Callout balloon detection works on both vector and image-only PDFs.
- [ ] Tag-to-schedule mapping correctly links detections to their schedule rows.
- [ ] Conditions are resolved correctly via the AI-04 resolver (matching project conditions / template clones / raw creates).
- [ ] AI Layer items appear in the review panel from AI-05 with correct geometry, confidence, and condition assignment.
- [ ] Auto-accepted measurements (high confidence) appear directly in the quantities panel with the AI badge.
- [ ] Re-runs deduplicate against rejected items per the AI-05 dedup rules.
- [ ] Cost telemetry: most pages process via OpenCV alone (no model calls); vision fallback only fires on the few sheets with unmatched candidates.
- [ ] All previous tests pass; new tests cover template matching, NMS, callout detection, tag-mapping, spatial filters, and the end-to-end count-measurement creation path.

---

## Out of Scope

- Wall detection -> AI-07
- Room and hatch detection -> AI-08

---

## Key References

- [features/ai/ai-element-recognition.md](../../features/ai/ai-element-recognition.md) -- Symbol Detection, Callout Balloon Detection
- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) -- Stage 3b, Stage 4
- Existing prototype (replaced by this sprint): `AI/controller/search.py` (its naive `search_for` approach is exactly the bug this sprint fixes)
