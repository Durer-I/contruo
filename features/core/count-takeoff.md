# Count Takeoff

> **Category:** Core Takeoff
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Count discrete items on construction plans -- doors, windows, fixtures, outlets, equipment, light fixtures, fire sprinklers, plumbing fixtures, and any element that needs to be tallied. Users enter a rapid-click mode where each click places a count marker on the plan. Markers are styled as colored dots per condition, with counts aggregated per-sheet and across the entire project. Each variation of an item gets its own condition (e.g., "Door - Single," "Door - Double").

## User Stories

- As an estimator, I want to enter a count mode and rapidly click to place markers on each item I'm counting so that I can tally items quickly without re-selecting the tool each time.
- As an estimator, I want each count marker to appear as a colored dot matching my condition so that I can visually see what I've already counted on the plan.
- As an estimator, I want to see both the per-sheet count and the project-wide total for each condition so that I can verify counts at any level.
- As an estimator, I want to create separate conditions for each item variation (e.g., "3'-0\" Single Door," "6'-0\" Double Door") so that my quantity breakdown is specific enough for accurate pricing.
- As an estimator, I want to delete a misplaced count marker by clicking on it so that I can correct mistakes quickly.
- As an estimator, I want to move a count marker if I placed it in the wrong spot so that the visual record on the plan is accurate.
- As an estimator, I want the system to show me the running count as I click so that I know how many I've placed so far.

## Key Requirements

### Placement
- **Rapid-click mode**: Select a count condition, then click repeatedly to place markers -- each click adds one count. Stay in count mode until the user switches tools or presses Escape.
- Single-click precision placement at the cursor location
- Running count displayed in real-time (e.g., "Outlets: 47" updating with each click)

### Marker Display
- Colored dot/circle at each click point, styled by the condition's assigned color
- Dots sized appropriately to be visible but not obscure plan details
- Dots scale with zoom level (maintain readable size)
- Optional: show a small sequential number on or near each dot for verification

### Count Aggregation
- Per-sheet count for each condition
- Project-wide total aggregating across all sheets
- Both shown in the quantities panel
- Quantities panel breaks down: Condition Name | Sheet | Count | Project Total

### Condition-Based Organization
- Each item variation is a separate condition (no sub-groups needed)
- Conditions define: name, color, and any custom properties (size, type, material, etc.)
- Common pattern: trade prefix + item description (e.g., "Elec - Duplex Outlet," "Plmb - Floor Drain")

### Editing
- Click a marker to select it; press Delete to remove
- Drag a marker to reposition it
- Undo/redo support for placement and deletion
- Select multiple markers (box select or Ctrl+click) for bulk delete or reassign to a different condition

### Derived Quantities
- Count can be used in the formula engine as an input variable
- Example: count x unit weight = total weight, count x install labor hours = total labor

## Nice-to-Have

- Multi-count placement: click once and enter a number (e.g., "4 outlets behind this wall") for items not individually visible on the plan
- Custom symbols/icons per condition instead of dots (door icon, outlet icon, etc.)
- AI-assisted counting: auto-detect and count matching symbols across the sheet
- Count verification mode: highlight all markers for a condition and show the total, let user confirm
- Import counts from a schedule/table on the plan sheets (e.g., door schedule, fixture schedule)
- Heat map or density visualization showing count concentration areas

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Click-to-place count markers. Condition-styled colored markers. Running total. Can drag to reposition. Supports multi-count entry. Desktop-only. |
| Bluebeam | Count measurement tool places numbered markers. Not integrated with a takeoff database. Markers are annotations. No condition system. |
| On-Screen Takeoff | Count tool with rapid-click mode. Condition-based colored markers. Per-sheet and total aggregation. Limited editing after placement. Desktop-only. |
| Togal.AI | AI auto-counts identified elements. Manual count tool available as backup. Focus is on automated detection rather than manual placement. |

## Open Questions

- [ ] Should count markers have a minimum/maximum display size, or scale freely with zoom?
- [ ] How do we handle count markers that are very close together (overlapping dots)?
- [ ] Should there be a "count audit" view that lists every marker with its sheet and location for verification?
- [ ] How do we represent counts in the collaboration sync? (Each marker as an individual operation, or batch?)

## Technical Considerations

- Count markers are the simplest geometry (point + condition reference) -- lightweight to store and sync
- Rapid-click mode needs responsive feedback with no delay between click and marker appearance
- Cross-sheet aggregation requires a real-time query across all sheets in the project -- should be efficient with proper indexing
- Rendering hundreds of dot markers on a single sheet needs efficient instanced rendering (same shape, different positions/colors)
- Marker hit-testing for selection/deletion needs spatial indexing for fast lookups near the click point
- Collaboration: each marker placement is a discrete operation, easy to merge without conflicts

## Notes

- Count takeoff is the simplest measurement type but also one of the most frequently used. The rapid-click UX must feel absolutely instant and frictionless.
- Keeping the marker as a simple dot (rather than custom icons) is the right MVP call -- it's fast to render, easy to understand, and doesn't require an icon library. Custom symbols can be a compelling post-MVP enhancement.
- The decision to use separate conditions for each variation rather than sub-groups keeps the data model simpler and aligns with how most estimators already think about their quantity breakdowns.
