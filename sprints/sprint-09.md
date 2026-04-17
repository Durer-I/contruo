# Sprint 09: Area & Count Takeoff

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 08

## Sprint Goal

Build the area and count takeoff tools. At the end of this sprint, users can draw polygon/rectangle/circle area measurements with cutouts and automatic perimeter calculation, and place rapid-click count markers. All three measurement types (linear, area, count) are functional.

---

## Tasks

### 1. Area Takeoff -- Shape Tools
- [ ] **Polygon tool**: click to place vertices, double-click/Enter to close the polygon
- [ ] **Rectangle tool**: click-drag to define a rectangle
- [ ] **Circle/Ellipse tool**: click-drag to define circular or elliptical areas
- [ ] Tool sub-selection: when Area (A) is active, secondary toolbar shows Polygon/Rect/Circle options
- [ ] Live preview of the shape being drawn with fill preview

### 2. Area Calculation & Display
- [ ] Calculate area from polygon vertices using the shoelace formula
- [ ] Calculate perimeter from polygon edges
- [ ] Render completed areas with condition styling: fill color, fill opacity, border color, fill pattern
- [ ] Area label shown inside the shape (e.g., "1,250 SF")
- [ ] Perimeter value available alongside area in measurement data

### 3. Cutouts / Voids
- [ ] **Boolean subtraction**: draw a second shape overlapping the area -> "Subtract" action in context menu
- [ ] **Inner boundary**: while defining a polygon, keyboard shortcut to switch to "hole mode" for drawing interior boundaries
- [ ] Cutout areas visually distinct (transparent/hatched within the filled area)
- [ ] Net area = gross area - void areas
- [ ] Gross, void, and net area all stored in measurement data

### 4. Area Vertex Editing
- [ ] Click a completed area to enter edit mode
- [ ] Drag vertices to reshape boundary
- [ ] Add midpoints on edges, delete vertices
- [ ] Edit cutout boundaries independently
- [ ] Area, perimeter, and net values recalculate in real-time during editing

### 5. Count Takeoff
- [ ] Activate count tool via toolbar or `C` shortcut
- [ ] **Rapid-click mode**: each click places a count marker, stay in count mode
- [ ] Colored dot marker at each click point (styled by condition color)
- [ ] Dots sized to be visible but not obscure plan details
- [ ] Running count displayed: "Outlets: 47"
- [ ] Press Escape to exit count mode

### 6. Count Editing
- [ ] Click a marker to select it, press Delete to remove
- [ ] Drag a marker to reposition
- [ ] Box select or Ctrl+click for multi-select
- [ ] Bulk delete selected markers

### 7. Count Aggregation
- [ ] Per-sheet count for each condition
- [ ] Project-wide total aggregating across all sheets
- [ ] Implement aggregation query in `GET /api/v1/projects/:id/measurements`

### 8. Measurement Type Routing
- [ ] The active tool determines the measurement type in the `measurements` table
- [ ] Geometry JSONB stores different structures per type:
  - Linear: `{type: "linear", vertices: [...], segments: [...]}`
  - Area: `{type: "area", outer: [...], holes: [[...], [...]], shape: "polygon|rect|circle"}`
  - Count: `{type: "count", position: {x, y}}`

---

## Acceptance Criteria

- [ ] User can draw polygon, rectangle, and circle area measurements
- [ ] Area and perimeter are calculated and displayed correctly
- [ ] Cutouts work via both boolean subtraction and inner boundary methods
- [ ] Net area (gross - voids) is calculated and displayed
- [ ] Area vertex editing works with real-time recalculation
- [ ] User can rapidly click to place count markers without re-selecting the tool
- [ ] Count markers appear as colored dots matching the condition
- [ ] Running count updates with each click
- [ ] Count markers can be selected, moved, and deleted
- [ ] Per-sheet and project-wide count aggregation works
- [ ] All three measurement types persist and reload correctly

---

## Key References

- [Area Takeoff Feature](../features/core/area-takeoff.md) -- shapes, cutouts, perimeter
- [Count Takeoff Feature](../features/core/count-takeoff.md) -- rapid-click, markers, aggregation
