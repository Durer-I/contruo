# Sprint 09: Area & Count Takeoff

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** Partial (core shipped; see Deferred below)
> **Depends On:** Sprint 08

## Sprint Goal

Build the area and count takeoff tools. At the end of this sprint, users can draw polygon/rectangle/circle area measurements with cutouts and automatic perimeter calculation, and place rapid-click count markers. All three measurement types (linear, area, count) are functional.

---

## Tasks

### 1. Area Takeoff -- Shape Tools
- [x] **Polygon tool**: click to place vertices, double-click/Enter to close the polygon
- [x] **Rectangle tool**: click-drag to define a rectangle
- [x] **Circle/Ellipse tool**: click-drag to define circular or elliptical areas
- [x] Tool sub-selection: when Area (A) is active, secondary toolbar shows Polygon/Rect/Circle options
- [x] Live preview of the shape being drawn with fill preview

### 2. Area Calculation & Display
- [x] Calculate area from polygon vertices using the shoelace formula
- [x] Calculate perimeter from polygon edges
- [x] Render completed areas with condition styling: fill color, fill opacity, border color, fill pattern
- [x] Area label shown inside the shape (e.g., "1,250 SF")
- [x] Perimeter value available alongside area in measurement data

### 3. Cutouts / Voids
- [ ] **Boolean subtraction**: draw a second shape overlapping the area -> "Subtract" action in context menu
- [x] **Inner boundary**: while defining a polygon, keyboard shortcut **H** switches to "hole mode" for interior boundaries; **Enter** commits a hole
- [x] Cutout areas visually distinct (even-odd fill + hole stroke in draft)
- [x] Net area = gross area - void areas
- [x] Gross, void, and net area all stored in measurement data

### 4. Area Vertex Editing
- [ ] Click a completed area to enter edit mode
- [ ] Drag vertices to reshape boundary
- [ ] Add midpoints on edges, delete vertices
- [ ] Edit cutout boundaries independently
- [ ] Area, perimeter, and net values recalculate in real-time during editing

### 5. Count Takeoff
- [x] Activate count tool via toolbar or `C` shortcut
- [x] **Rapid-click mode**: each click places a count marker, stay in count mode
- [x] Colored dot marker at each click point (styled by condition color)
- [x] Dots sized to be visible but not obscure plan details
- [x] Running count displayed in status/footer (sheet + project aggregates)
- [x] Press **Escape** to exit count mode (returns to select)

### 6. Count Editing
- [x] Click a marker to select it, **Delete** to remove (bulk delete when multi-selected)
- [x] Drag a marker to reposition (PATCH geometry)
- [x] Ctrl+click for multi-select
- [ ] Box select or Shift+click range select
- [x] Bulk delete selected markers

### 7. Count Aggregation
- [x] Per-sheet count for each condition
- [x] Project-wide total aggregating across all sheets
- [x] Implement aggregation query in `GET /api/v1/projects/:id/measurements` (`include_aggregates=true`)

### 8. Measurement Type Routing
- [x] The active tool determines the measurement type in the `measurements` table
- [x] Geometry JSONB stores different structures per type:
  - Linear: `{type: "linear", vertices: [...]}`
  - Area: `{type: "area", outer: [...], holes: [[...]], shape: "polygon|rectangle|ellipse", ...}`
  - Count: `{type: "count", position: {x, y}}`

---

## Deferred (follow-on)

| Item | Notes |
|------|--------|
| Area vertex editing | Same pattern as linear Phase 2; PATCH + handles on canvas |
| Boolean subtract from overlapping shape | Needs UI affordance + backend merge or second measurement |
| Box / shift range select for counts | Pointer marquee on canvas |
| Perimeter on canvas label | Quantities panel / API already expose metrics |

---

## Acceptance Criteria

- [x] User can draw polygon, rectangle, and circle area measurements
- [x] Area and perimeter are calculated and displayed correctly
- [x] Cutouts work via inner boundary (hole mode); boolean overlap subtract **deferred**
- [x] Net area (gross - voids) is calculated and displayed
- [ ] Area vertex editing works with real-time recalculation — **deferred**
- [x] User can rapidly click to place count markers without re-selecting the tool
- [x] Count markers appear as colored dots matching the condition
- [x] Running count updates with each click
- [x] Count markers can be selected, moved, and deleted
- [x] Per-sheet and project-wide count aggregation works
- [x] All three measurement types persist and reload correctly

---

## Key References

- [Area Takeoff Feature](../features/core/area-takeoff.md) -- shapes, cutouts, perimeter
- [Count Takeoff Feature](../features/core/count-takeoff.md) -- rapid-click, markers, aggregation
