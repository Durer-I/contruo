# Sprint AI-07: Wall Detection

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint AI-06

## Sprint Goal

Implement wall detection (the wall half of Stage 5). After this sprint, an estimator who runs auto-takeoff on architectural floor plans sees walls automatically detected as linear measurements with correct centerline geometry, wall thickness metadata, and the ability to display centerline / outer / inner edges via a viewer toggle. This sprint is also where the prototype's flawed wall approach (`AI/controller/walls_rooms.py`) is fully replaced by a vector-first algorithm with a raster fallback for scanned plans.

---

## Tasks

### 1. Vector Wall Extraction (Primary)

- [ ] In `backend/app/services/ai_wall_detector.py`:
  - Use PyMuPDF `page.get_drawings()` to extract all line and curve segments with stroke style
  - Direction bucketing: snap each segment angle to nearest 5°, group into direction buckets
  - Within each direction bucket, find pairs of near-parallel segments that:
    - Are roughly the same length (±20%)
    - Are separated by a perpendicular distance in the wall-thickness range (4-16 inches in world units; configurable)
    - Overlap along their shared direction (>50% overlap)
- [ ] Centerline construction: midline of each pair = wall centerline; record the perpendicular distance as `wall_thickness_pdf`
- [ ] Use `scipy.spatial.KDTree` for endpoint snapping (within 6" world units) to build a clean wall graph -- never the O(N²) approach from `AI/controller/walls_rooms.py`

### 2. Opening Detection

- [ ] Door swings: vector arcs near wall endpoints with arc radius in typical door range (24-48 inches in world units) mark openings
- [ ] Window break-marks: pairs of short ticks across a wall mark window openings
- [ ] Openings split walls in the graph (so room detection in AI-08 doesn't leak through them)
- [ ] Each detected wall carries opening metadata: `openings: [{type: 'door'|'window', position, width}]`

### 3. Wall Validation Heuristics

- [ ] A wall candidate is kept only if it has at least one of:
  - An orthogonal connection (corner / T-intersection) with another wall candidate
  - A door swing or window opening nearby
  - Length > 2 feet in world units (to filter short pair noise)
- [ ] Isolated short pairs are filtered as noise

### 4. Raster Fallback (Scanned Plans)

- [ ] When `page.get_drawings()` yields fewer than a configurable threshold of segments per sheet (e.g., < 200), trigger raster fallback
- [ ] Render at adaptive DPI (200, max 300) via PyMuPDF `page.get_pixmap()`
- [ ] Run a lightweight wall segmentation (start with classical morphological edge detection + skeletonization; if quality is poor, escalate to a self-hosted model like SAM2 in a follow-on)
- [ ] Vectorize the wall mask with `cv2.findContours` + `approxPolyDP` to get polylines
- [ ] Back-map pixel coordinates to PDF user space using the pixmap scale
- [ ] Skip door-swing and window-break-mark detection in the raster path (vector-only features)

### 5. Single-Row Wall Geometry Storage

- [ ] Wall geometry payload (per the spec):
  ```json
  {
    "type": "linear",
    "vertices": [...],
    "wall_thickness_pdf": 6.0,
    "alt_paths": {              // optional, only for non-derivable
      "outer": [...],
      "inner": [...]
    }
  }
  ```
- [ ] Straight wall segments: `alt_paths` is omitted; outer/inner derived on demand from centerline + thickness
- [ ] Curved walls or non-uniform thickness: `alt_paths.outer` and `alt_paths.inner` stored explicitly
- [ ] Helpers in `backend/app/utils/wall_geometry.py`:
  - `derive_offset_polyline(centerline, offset)` -> offsets the centerline by `offset` along its perpendicular
  - `derive_outer(geometry)` / `derive_inner(geometry)` -> returns the requested polyline (using `alt_paths` if present, otherwise computed)

### 6. Viewer Display Toggle (Centerline / Outer / Inner)

- [ ] Frontend: per-project preference `wall_display_mode` (`centerline` default | `outer` | `inner`)
- [ ] Setting persisted in `projects.ai_settings` JSONB
- [ ] In `plan-viewer-workspace.tsx` (or equivalent), wall measurements render the requested polyline
- [ ] Tooltip on a wall measurement shows all three lengths so the user can verify
- [ ] Settings UI: dropdown in project settings page

### 7. Wall Condition Resolution

- [ ] For each detected wall, the AI-04 resolver picks a Condition:
  - Match: existing project conditions like "Interior Wall - 8' Drywall"
  - Template: clone closest org template
  - Create raw: e.g., "Interior Wall - {thickness} {default_height}'" with starter assembly items
- [ ] Wall thickness drives the resolver's name suggestion when creating raw conditions

### 8. AI Layer Write

- [ ] Insert `ai_layer_items` rows with `measurement_type = 'linear'`, the wall geometry payload, confidence, source_stage = `wall_detection`
- [ ] High-confidence walls auto-accept and create real `Measurement` rows immediately (per AI-05 logic)

### 9. Run Summary Updates

- [ ] After wall detection completes:
  - Per-sheet wall counts
  - Total linear footage detected
  - Method breakdown (vector vs raster fallback)
  - Per-condition counts
- [ ] UI: "AI detected 47 walls (1,340 LF) on 8 sheets. 42 auto-accepted, 5 to review."

### 10. Internal QC View (Debug)

- [ ] Internal page rendering each detected wall on top of the sheet thumbnail with centerline / outer / inner overlays for visual QC during development

---

## Acceptance Criteria

- [ ] On a clean vector floor plan, walls are detected as parallel-pair clusters and rendered as centerline polylines with correct `wall_thickness_pdf`.
- [ ] Door swings and window break-marks correctly mark openings; walls split at openings.
- [ ] On a scanned (image-only) floor plan, the raster fallback path produces wall polylines (lower quality acceptable).
- [ ] The viewer's display-mode toggle (centerline / outer / inner) renders the correct polyline for each wall, computed on demand for straight walls.
- [ ] Curved walls (arcs) store explicit `alt_paths` and the toggle still works.
- [ ] Wall measurement tooltips show all three lengths.
- [ ] AI-04 resolver picks sensible conditions (matches firm's "Interior Wall - 8'" if it exists, etc.).
- [ ] AI Layer integration works end-to-end: high-confidence walls become real measurements immediately; medium-confidence walls appear in the review panel.
- [ ] Re-runs preserve user-edited wall measurements per AI-05 rules.
- [ ] Performance: wall detection on a 200-sheet plan set completes in < 5 minutes (parallelism per sheet).
- [ ] Cost telemetry: pure-vector wall detection costs zero cents; raster fallback may use a self-hosted model with no per-call cost.
- [ ] All previous tests pass; new tests cover parallel-pair clustering, opening detection, wall-graph snapping, raster fallback vectorization, and the offset-polyline derivation helpers.

---

## Out of Scope

- Room polygon detection -> AI-08
- Hatch / finish detection -> AI-08
- True learned wall segmentation model -> reserved for a post-track enhancement; AI-07 raster fallback uses morphological methods first

---

## Key References

- [features/ai/ai-element-recognition.md](../../features/ai/ai-element-recognition.md) -- Wall Detection (Vector), Raster Fallback
- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) -- Stage 5 (Walls), Wall Geometry Storage
- Existing prototype (informational; replaced by this sprint): `AI/controller/walls_rooms.py`
- [backend/app/utils/measurement_quantity.py](../../backend/app/utils/measurement_quantity.py) -- existing linear length math the new geometry plugs into
