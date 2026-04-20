# Sprint 08: Linear Takeoff

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** In Progress
> **Depends On:** Sprint 06 (plan viewer + scale), Sprint 07 (conditions)

## Sprint Goal

Build the linear takeoff tool -- the first functional measurement tool. At the end of this sprint, users can draw linear measurements on calibrated plans using click-to-click mode, see running totals, view styled measurement lines, and edit vertices after drawing.

---

## Tasks

### 1. Measurement Data Model
- [x] Create `measurements` table migration (Sprint 07 migration `005_conditions_and_measurements`)
- [x] Geometry stored as JSONB: array of vertices `[{x, y}, ...]` with segment type metadata
- [x] Implement API endpoints:
  - `POST /api/v1/projects/:id/measurements` -- create measurement
  - `PATCH /api/v1/measurements/:id` -- update measurement (geometry, override)
  - `DELETE /api/v1/measurements/:id` -- delete measurement
  - `GET /api/v1/projects/:id/measurements` -- list measurements (with filtering)
- [x] RLS policies on measurements table

### 2. Click-to-Click Drawing
- [x] Activate linear tool via toolbar button or `L` shortcut
- [x] Click to place first vertex
- [x] Click to place subsequent vertices (creating line segments)
- [x] Double-click or press Enter to complete the measurement
- [x] Press Escape to cancel the current drawing
- [x] Live preview line from last vertex to cursor position

### 3. Real-Time Measurement Display
- [x] Calculate segment lengths using the calibrated scale
- [ ] Show individual segment length on each segment as it's drawn
- [x] Show running total that updates with each click (status bar draft total)
- [ ] Display cursor distance from last point before clicking
- [x] All lengths in the sheet's calibrated unit (LF, meters, etc.)

### 4. Measurement Rendering
- [x] Render completed measurements with condition styling:
  - Line color from condition
  - Line thickness from condition
  - Dash pattern from condition (solid, dashed, dotted)
- [ ] Optional inline measurement label (e.g., "47.5 LF")
- [ ] Labels scale appropriately with zoom level
- [x] Measurements render on a layer above the plan but are semi-transparent enough to see the plan underneath

### 5. Vertex Editing
- [x] Click a completed measurement to enter edit mode (Select tool or click while in Select mode) — selection + highlight only
- [ ] Show vertex handles (draggable circles) at each vertex
- [ ] Drag a vertex to reposition it -- measurement recalculates in real-time
- [ ] Click on a segment midpoint to add a new vertex
- [ ] Select a vertex and press Delete to remove it
- [ ] Show updated total as vertices are moved

### 6. Undo / Redo
- [x] Undo last vertex while drawing (Ctrl+Z removes last placed vertex)
- [ ] Undo/redo for completed actions: create measurement, edit vertex, delete measurement — **partial:** Ctrl+Z deletes last created measurement in session stack (LIFO); no redo
- [x] Undo/redo stack per session — **partial:** per-sheet undo stack for created measurements

### 7. Measurement Persistence
- [x] Save measurements to the database on completion (not on every vertex click)
- [ ] Save vertex edits on deselect (batch the edit, don't save every drag frame)
- [x] Load and render all existing measurements when opening a project/sheet
- [x] Log events: `measurement.created`, `measurement.edited`, `measurement.deleted`

---

## Acceptance Criteria

- [x] User can select the Linear tool and draw multi-segment lines on a calibrated plan
- [x] Running total updates in real-time as vertices are placed
- [ ] Individual segment lengths are shown on the plan
- [x] Completed measurements render with the correct condition color, thickness, and dash pattern
- [ ] User can click a measurement to select it and drag vertices to adjust — **partial:** select + highlight only
- [ ] User can add midpoint vertices and delete existing vertices
- [ ] Undo/redo works for all drawing and editing actions — **partial:** see task 6 above
- [x] Measurements persist to the database and reload on page refresh
- [x] Measurements only appear on calibrated sheets (warning on uncalibrated)

---

## Key References

- [Linear Takeoff Feature](../features/core/linear-takeoff.md) -- drawing modes, segments, vertex editing
- [Conditions & Assemblies Feature](../features/core/conditions-and-assemblies.md) -- styling
- [Backend Architecture - Measurements Schema](../docs/architecture/backend.md)
