# Sprint 08: Linear Takeoff

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 06 (plan viewer + scale), Sprint 07 (conditions)

## Sprint Goal

Build the linear takeoff tool -- the first functional measurement tool. At the end of this sprint, users can draw linear measurements on calibrated plans using click-to-click mode, see running totals, view styled measurement lines, and edit vertices after drawing.

---

## Tasks

### 1. Measurement Data Model
- [ ] Create `measurements` table migration
- [ ] Geometry stored as JSONB: array of vertices `[{x, y}, ...]` with segment type metadata
- [ ] Implement API endpoints:
  - `POST /api/v1/projects/:id/measurements` -- create measurement
  - `PATCH /api/v1/measurements/:id` -- update measurement (geometry, override)
  - `DELETE /api/v1/measurements/:id` -- delete measurement
  - `GET /api/v1/projects/:id/measurements` -- list measurements (with filtering)
- [ ] RLS policies on measurements table

### 2. Click-to-Click Drawing
- [ ] Activate linear tool via toolbar button or `L` shortcut
- [ ] Click to place first vertex
- [ ] Click to place subsequent vertices (creating line segments)
- [ ] Double-click or press Enter to complete the measurement
- [ ] Press Escape to cancel the current drawing
- [ ] Live preview line from last vertex to cursor position

### 3. Real-Time Measurement Display
- [ ] Calculate segment lengths using the calibrated scale
- [ ] Show individual segment length on each segment as it's drawn
- [ ] Show running total that updates with each click
- [ ] Display cursor distance from last point before clicking
- [ ] All lengths in the sheet's calibrated unit (LF, meters, etc.)

### 4. Measurement Rendering
- [ ] Render completed measurements with condition styling:
  - Line color from condition
  - Line thickness from condition
  - Dash pattern from condition (solid, dashed, dotted)
- [ ] Optional inline measurement label (e.g., "47.5 LF")
- [ ] Labels scale appropriately with zoom level
- [ ] Measurements render on a layer above the plan but are semi-transparent enough to see the plan underneath

### 5. Vertex Editing
- [ ] Click a completed measurement to enter edit mode (Select tool or click while in Select mode)
- [ ] Show vertex handles (draggable circles) at each vertex
- [ ] Drag a vertex to reposition it -- measurement recalculates in real-time
- [ ] Click on a segment midpoint to add a new vertex
- [ ] Select a vertex and press Delete to remove it
- [ ] Show updated total as vertices are moved

### 6. Undo / Redo
- [ ] Undo last vertex while drawing (Ctrl+Z removes last placed vertex)
- [ ] Undo/redo for completed actions: create measurement, edit vertex, delete measurement
- [ ] Undo/redo stack per session

### 7. Measurement Persistence
- [ ] Save measurements to the database on completion (not on every vertex click)
- [ ] Save vertex edits on deselect (batch the edit, don't save every drag frame)
- [ ] Load and render all existing measurements when opening a project/sheet
- [ ] Log events: `measurement.created`, `measurement.edited`, `measurement.deleted`

---

## Acceptance Criteria

- [ ] User can select the Linear tool and draw multi-segment lines on a calibrated plan
- [ ] Running total updates in real-time as vertices are placed
- [ ] Individual segment lengths are shown on the plan
- [ ] Completed measurements render with the correct condition color, thickness, and dash pattern
- [ ] User can click a measurement to select it and drag vertices to adjust
- [ ] User can add midpoint vertices and delete existing vertices
- [ ] Undo/redo works for all drawing and editing actions
- [ ] Measurements persist to the database and reload on page refresh
- [ ] Measurements only appear on calibrated sheets (warning on uncalibrated)

---

## Key References

- [Linear Takeoff Feature](../features/core/linear-takeoff.md) -- drawing modes, segments, vertex editing
- [Conditions & Assemblies Feature](../features/core/conditions-and-assemblies.md) -- styling
- [Backend Architecture - Measurements Schema](../docs/architecture/backend.md)
