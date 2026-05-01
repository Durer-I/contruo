# Sprint AI-08: Room + Hatch Detection

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint AI-07

## Sprint Goal

Implement room and hatch detection (the room/finish half of Stage 5). After this sprint, an estimator who runs auto-takeoff on architectural plans sees:

- Rooms automatically detected as area polygons (not bboxes), each labeled by interior text
- Hatch / finish regions automatically detected and matched to legend swatches, becoming area measurements assigned to finish conditions

This is the final detection sprint and completes the v1 element coverage promised in [AI Element Recognition](../../features/ai/ai-element-recognition.md). At the end, all the user-facing capabilities of AI Auto-Takeoff are live: walls, rooms, finishes, doors, fixtures, equipment, all detected and reviewable.

---

## Tasks

### 1. Room Detection via Planar-Graph Faces

- [ ] In `backend/app/services/ai_room_detector.py`:
  - Take the wall centerline graph from AI-07
  - Close door and window openings (room-detection pass only) so faces are properly enclosed
  - Run Shapely `polygonize` on the closed graph
  - Each enclosed face = a candidate room polygon
- [ ] Face filtering:
  - Drop faces below minimum room area (default 25 sq ft, configurable)
  - Drop the page-bounding outer face
  - Drop faces with implausible aspect ratios (e.g., > 30:1) -- usually noise from open boundaries

### 2. Room Labeling

- [ ] For each face, find text strings from `page.get_text("words")` whose centroid falls inside the polygon
- [ ] Choose the longest matching string (or highest-priority by font size) as the room label
- [ ] Store on the room polygon as `label`
- [ ] Faces without interior text get `confidence -= 0.2` (probably correct geometry but unverifiable)

### 3. Raster Flood-Fill Room Fallback

- [ ] When the planar-graph approach yields fewer rooms than expected for the plan size (heuristic threshold) OR when wall detection went down the raster path:
  - Render walls as a binary mask (black = wall, white = empty)
  - Invert + run `cv2.connectedComponentsWithStats`
  - Filter by size (drop tiny noise; drop the page-background component)
  - Vectorize each component contour with `cv2.findContours` + `approxPolyDP`
  - Back-map pixel coords to PDF user space
- [ ] Same labeling logic applied to flood-fill polygons

### 4. Vector Hatch Detection

- [ ] In `backend/app/services/ai_hatch_detector.py`:
  - Use `page.get_drawings()` to extract all paths grouped by `(stroke, fill, dash, line_width)` style
  - Adjacent paths with the same style cluster into hatch region candidates (using KDTree spatial proximity)
  - Each cluster -> candidate hatch region polygon (outer boundary via Shapely `unary_union` then `convex_hull` or `concave_hull`)
- [ ] Filter clusters with too few elements (< 3) or too small total area as noise

### 5. Raster Hatch Detection (Fallback for Image Plans)

- [ ] For sheets with sparse vector content:
  - For each `extracted_legends` swatch from AI-03, slide-match against the page raster using `cv2.matchTemplate` at multiple scales (0.7x - 1.3x in 0.1x increments) and rotations (0°/90°/180°/270°)
  - Threshold the response map per swatch
  - Connected-components on the binary response map to identify regions
  - Vectorize each region's contour, back-map to PDF user space
- [ ] Multi-scale + rotation tolerance is the key requirement (per the locked decision)

### 6. Hatch-to-Legend Matching

- [ ] For vector-detected hatch regions, match by extracting the dominant pattern signature (line spacing, angle, density) and comparing to legend swatches' computed signatures
- [ ] For raster-detected hatch regions, the legend label is already known from which swatch matched
- [ ] Output per region: `(matched_legend_label, confidence)`

### 7. Outer-Polygon-Only Geometry

- [ ] Hatch and room polygons are stored with `outer` only (no holes/cutouts in v1, per locked decision)
- [ ] Geometry payload conforms to existing area-measurement contract:
  ```json
  {
    "type": "area",
    "shape": "polygon",
    "outer": [...],
    "holes": [],
    "metrics": {...}     // computed by existing area_geometry helpers
  }
  ```

### 8. Overlap Resolution (Split, Don't Stack)

- [ ] When two different hatch patterns claim overlapping regions:
  - Compute the geometric intersection (Shapely)
  - Split into three regions: `A only`, `B only`, `intersection`
  - Each region becomes a separate `ai_layer_items` row, assigned to the appropriate condition
- [ ] This matches the locked decision: never overlay; split into separate regions

### 9. Condition Resolution + AI Layer Write

- [ ] For each detected room, the AI-04 resolver picks a Condition (e.g., "Room - Office", "Room - Corridor") -- match existing if possible, else clone template, else create raw
- [ ] For each detected hatch region, the resolver picks a Condition based on the matched legend label (e.g., "Carpet - Corridor", "VCT Tile")
- [ ] Insert `ai_layer_items` rows with `measurement_type = 'area'`, the polygon geometry, confidence, source_stage = `room_detection` or `hatch_detection`
- [ ] High-confidence items auto-accept and create real `Measurement` rows immediately

### 10. Run Summary Updates

- [ ] After Stage 5 completes:
  - Per-sheet room counts and total area
  - Per-condition area totals (e.g., "Carpet: 4,200 SF; VCT: 1,150 SF")
  - Method breakdown (vector vs raster)
- [ ] UI: "AI detected 47 rooms (12,400 SF) and 89 finish regions (18,300 SF) on 8 sheets."

### 11. End-to-End Test on a Reference Plan Set

- [ ] Run the full AI Auto-Takeoff pipeline on at least 3 representative plan sets (provided by the team) and measure:
  - Wall detection precision/recall vs hand-traced ground truth
  - Room detection precision/recall vs hand-traced ground truth
  - Hatch matching accuracy vs hand-labeled legend
  - Total processing time
  - Total cost per plan set
- [ ] Document results in `docs/ai/auto-takeoff-quality-report.md` for ongoing tuning

### 12. Internal QC View (Debug)

- [ ] Internal page rendering each detected room and hatch region on the sheet thumbnail with confidence overlays for visual QC

---

## Acceptance Criteria

- [ ] On a clean vector floor plan with walls detected by AI-07, rooms are detected as polygons (not bboxes) and labeled by interior text strings.
- [ ] On a scanned floor plan, the raster flood-fill fallback produces room polygons (lower quality acceptable).
- [ ] On a plan with carpet/VCT/concrete hatch fills, hatch regions are detected and matched to legend swatches with > 80% precision and > 70% recall (measured on a labeled test plan set).
- [ ] Overlapping hatch regions are split into separate measurements per the locked policy (never stacked).
- [ ] Hatch regions are stored with outer polygon only (no holes); area metrics compute correctly via existing helpers.
- [ ] Conditions are resolved correctly: rooms -> "Room - {Type}"; hatches -> finish-specific conditions cloned from templates or matched to existing.
- [ ] AI Layer integration works end-to-end: high-confidence rooms and hatches become real area measurements; medium-confidence ones appear in the review panel.
- [ ] Re-runs preserve user-edited room and hatch measurements per AI-05 rules.
- [ ] Performance: room and hatch detection on a 200-sheet plan set completes in < 10 minutes (parallelism per sheet).
- [ ] Quality report on the reference plan sets shows the detection meets the precision/recall thresholds above; identified failure modes documented for follow-up tuning.
- [ ] All previous tests pass; new tests cover planar-graph face derivation, room labeling, vector hatch clustering, raster hatch matching, overlap split logic, and end-to-end pipeline integration.

---

## Out of Scope

- Hole/cutout detection in hatch polygons (deferred to a post-track enhancement)
- Slope-aware area adjustment (deferred to post-track enhancement; ties into Volume Takeoff feature)
- Custom symbol training per project (post-track)

---

## Key References

- [features/ai/ai-element-recognition.md](../../features/ai/ai-element-recognition.md) -- Room Detection, Hatch / Finish Region Detection
- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) -- Stage 5 (Walls, Rooms, and Hatch Detection)
- [backend/app/utils/area_geometry.py](../../backend/app/utils/area_geometry.py) -- existing area metric computations the new polygons plug into
- Existing prototype (informational; replaced by this sprint): `AI/controller/walls_rooms.py` (its room flood-fill informed the raster fallback path)
