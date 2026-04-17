# Sprint 15: Polish & QA

> **Phase:** 6 - Launch Prep
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 12, Sprint 13, Sprint 14

## Sprint Goal

Polish the product -- implement advanced drawing features (snap-to-geometry, freehand tracing, arc segments), finalize keyboard shortcuts, fix edge cases, and conduct thorough QA testing. At the end of this sprint, all MVP features are complete and bug-free.

---

## Tasks

### 1. Advanced Drawing Features
- [ ] **Snap-to-geometry**: detect PDF vector lines near the cursor and snap measurement vertices to them
  - Parse vector paths from the PDF (PyMuPDF path extraction)
  - Build spatial index for fast nearest-line queries
  - Visual snap indicator when cursor is near a snappable line
- [ ] **Freehand tracing**: hold mouse button and trace along an element
  - Path simplification algorithm (Douglas-Peucker or similar)
  - Configurable smoothing tolerance
- [ ] **Arc segments**: support curved segments for rounded walls, curbs, piping
  - 3-point arc drawing method (click start, click midpoint on arc, click end)
  - Accurate arc length calculation
- [ ] **Snap-to-room** (area takeoff): click inside an enclosed space to auto-detect the room boundary from PDF vectors

### 2. Deductions / Backouts (Linear)
- [ ] Implement deduction mode for linear measurements
- [ ] After completing a linear measurement, option to mark deduction segments
- [ ] Deductions subtract from gross total to produce net measurement
- [ ] Visually distinct deduction rendering (different line style)
- [ ] Net and gross totals shown in quantities panel

### 3. Keyboard Shortcuts
- [ ] Implement all shortcuts from the design system:
  - Tool selection: V, L, A, C, S
  - Condition switching: 1-9
  - Undo/Redo: Ctrl+Z, Ctrl+Shift+Z
  - Export: Ctrl+E
  - Search: Ctrl+F
  - Sheet navigation: [, ]
  - Delete, Escape, Enter
- [ ] Keyboard shortcut help dialog (? key to open)
- [ ] Ensure shortcuts don't conflict with browser defaults

### 4. Edge Cases & Bug Fixes
- [ ] Handle zero-length measurements (accidentally clicking twice in the same spot)
- [ ] Handle self-intersecting polygons in area takeoff
- [ ] Handle very small/very large measurements (zoom-dependent rendering)
- [ ] Handle measurement labels overlapping at certain zoom levels
- [ ] Test with various PDF sizes and complexities (small plans, large plans, 200+ pages)
- [ ] Test bidirectional linking with measurements on different sheets
- [ ] Test manual overrides persisting through condition reassignment
- [ ] Cross-browser testing: Chrome, Firefox, Edge

### 5. UI Polish
- [ ] Loading states for all async operations
- [ ] Error states with clear messages and retry options
- [ ] Empty states (no projects, no measurements, no conditions)
- [ ] Toast notifications for actions (measurement deleted, condition saved, export ready)
- [ ] Confirmation dialogs for destructive actions
- [ ] Consistent focus management and tab order
- [ ] Tooltip content review (all toolbar buttons, action buttons)

### 6. Collaboration Edge Cases
- [ ] Test 5 simultaneous users on the same sheet
- [ ] Test lock-on-select with rapid switching between users
- [ ] Test measurement sync under poor network conditions
- [ ] Test reconnection after WiFi drop
- [ ] Test concurrent condition editing
- [ ] Verify quantities panel updates correctly for all users

### 7. Mobile/Responsive Guard
- [ ] Implement "Please use a desktop browser" message for screens < 1024px
- [ ] Ensure the app doesn't crash on mobile (even though it's not supported)

---

## Acceptance Criteria

- [ ] Snap-to-geometry works for linear and area measurements on vector PDFs
- [ ] Freehand tracing produces clean, simplified paths
- [ ] Arc segments can be drawn and calculate accurate curved lengths
- [ ] Deductions/backouts work on linear measurements with net/gross display
- [ ] All keyboard shortcuts work correctly
- [ ] No known bugs in core measurement, collaboration, or billing flows
- [ ] UI has proper loading, error, and empty states throughout
- [ ] Product works reliably in Chrome, Firefox, and Edge
- [ ] 5 simultaneous users can collaborate without issues

---

## Key References

- [Linear Takeoff Feature](../features/core/linear-takeoff.md) -- snap, freehand, arcs, deductions
- [Area Takeoff Feature](../features/core/area-takeoff.md) -- snap-to-room
- [Screen Layouts](../docs/design/screen-layouts.md) -- keyboard shortcuts
