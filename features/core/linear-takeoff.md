# Linear Takeoff

> **Category:** Core Takeoff
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Measure linear elements on construction plans -- walls, pipes, conduit, curbs, fencing, ductwork, and any other element measured in linear footage or meters. Users draw measurements using click-to-click, freehand tracing, or snap-to-geometry modes. Supports straight segments and arcs, with real-time running totals, full vertex editing, and condition-based styling. Linear measurements feed into custom formulas to derive area, volume, and other quantities automatically.

## User Stories

- As an estimator, I want to click along a wall on the plan to measure its total linear footage so that I can calculate material quantities.
- As an estimator, I want to see a running total update in real-time as I draw each segment so that I can track progress without finishing the measurement.
- As an estimator, I want to draw curved/arc segments for rounded walls and curbs so that my measurements are accurate, not just straight-line approximations.
- As an estimator, I want my measurement lines to snap to the PDF vector geometry so that I can trace elements quickly and precisely.
- As an estimator, I want to freehand-trace a line along an irregular path so that I can measure elements that don't follow clean straight segments.
- As an estimator, I want to see both individual segment lengths and the combined total so that I can verify my work at any level of detail.
- As an estimator, I want to edit individual vertices after completing a measurement (move, add, delete points) so that I can correct mistakes without redrawing.
- As an estimator, I want to deduct openings (doors, windows) from a wall measurement so that my net linear footage is accurate.
- As an estimator, I want each measurement to be styled with the condition's color, thickness, and dash pattern so that I can visually distinguish different element types on the plan.
- As an estimator, I want to define formulas on a condition (e.g., length x height x thickness) so that a single linear measurement auto-calculates area, volume, and other derived quantities.

## Key Requirements

### Drawing Modes
- **Click-to-click**: Click to place vertices, double-click or press Enter to complete the path
- **Freehand tracing**: Hold mouse button and trace along an element; system simplifies the path into segments
- **Snap-to-geometry**: Auto-detect and snap to PDF vector lines/arcs when the cursor is near them
- Users can switch between modes mid-measurement or use them in combination

### Segment Types
- Straight line segments between vertices
- Arc/curve segments for rounded elements (user defines arc by 3-point click or tangent method)
- Mixed paths with both straight and arc segments in a single measurement

### Real-Time Feedback
- Running total displayed as the user draws (updates after each click/segment)
- Individual segment length shown on each segment as it's drawn
- Current cursor distance from last point shown before clicking
- Angle/direction indicator for precision drawing

### Measurement Display
- Lines rendered with condition-defined styling: color, line thickness, dash pattern
- Optional inline measurement labels (e.g., "47.5 LF") that scale appropriately with zoom
- Hover/select a measurement to see its full details (total length, segment count, condition, derived quantities)

### Vertex Editing (Post-Draw)
- Click a completed measurement to enter edit mode
- Drag individual vertices to reposition them
- Add new midpoints by clicking on a segment
- Delete vertices by selecting and pressing Delete
- Extend or shorten endpoints
- All edits recalculate the measurement total in real-time

### Deductions / Backouts
- After drawing a linear measurement, user can mark deduction segments (e.g., a 3'-0" door opening in a wall)
- Deductions subtract from the gross total to produce a net measurement
- Deductions are visually distinct on the plan (different style or cross-hatch)
- Net and gross totals both visible in the quantities panel

### Formula-Based Derived Quantities
- Each condition can define custom formulas using the measured length as an input
- Common examples: length x wall height = wall area, length x width x depth = volume
- Formula variables can reference user-defined condition properties (height, depth, thickness, etc.)
- Derived quantities auto-update when the measurement or formula variables change

## Nice-to-Have

- Measurement snapping to other measurements (connect endpoints)
- Copy/mirror a linear measurement to another location on the plan
- Auto-trace: AI-assisted tracing that follows a line/wall automatically after the user starts it
- Dimension line display mode (architectural style with tick marks and text)
- Measurement grouping: combine multiple linear measurements into a single subtotal group
- Right-click context menu for quick actions (delete, edit, duplicate, assign condition)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Click-to-click linear tool with straight segments. Arc tool available separately. Running total shown. Styled by condition color. Vertex editing supported. Backouts via separate deduction tool. Desktop-only. |
| Bluebeam | Full measurement toolkit with length, perimeter, and polylength tools. Snap to PDF geometry. Styled markup appearance. Not takeoff-focused -- measurements live as markup annotations, not connected to a quantities database. |
| On-Screen Takeoff | Click-to-click linear tool, similar to PlanSwift. Condition-based styling. Running totals. Deductions supported. Segment and total display. Desktop-only. Vertex editing is limited. |
| Togal.AI | AI does the linear measurement automatically. Limited manual linear drawing tools. Focus is on automated detection rather than manual measurement precision. |

## Open Questions

- [ ] How should snap-to-geometry behave when multiple vector lines overlap or are very close together?
- [ ] Should freehand tracing auto-smooth the path, and if so, what tolerance should be configurable?
- [ ] How do we handle measurements that span across sheet boundaries (e.g., a pipe that continues on the next sheet)?
- [ ] What's the UX for defining arc segments -- 3-point arc, tangent arc, or center-radius?
- [ ] Should deductions be their own measurement objects or sub-items of the parent measurement?

## Technical Considerations

- Snap-to-geometry requires parsing the PDF vector content and building a spatial index for fast nearest-line queries
- Real-time running totals and vertex editing need efficient geometric recalculation (especially for arcs)
- Formula engine needs to be lightweight but flexible enough for custom expressions (consider a simple math expression parser)
- All measurement data needs to be structured for real-time collaboration sync (vertices, segments, deductions as discrete operations)
- Arc calculations need proper geodesic math for accurate curved-length computation
- Rendering performance: hundreds of styled measurement lines on a single sheet needs efficient canvas/WebGL rendering

## Notes

- The three drawing modes (click-to-click, freehand, snap-to-geometry) working together seamlessly is a major UX differentiator. Most competitors only offer click-to-click.
- Snap-to-geometry on vector PDFs is a significant advantage over competitors that only support raster plans -- this is one of the strongest reasons to start with vector PDF support.
- The formula-based derived quantities tie directly into the Conditions & Assemblies feature -- they share the formula engine.
