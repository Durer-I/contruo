# Quantity Management

> **Category:** Core Takeoff
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

The Quantity Management panel is the structured data view of all takeoff work. It sits to the right of the Plan Viewer in a vertical split layout and presents all measurements in a **grouped tree view** -- measurements nested under their conditions, with subtotals per condition and per sheet. It provides bidirectional linking with the plan (click a row to highlight the measurement, click a measurement to highlight the row), manual quantity overrides, and expandable assembly item breakdowns beneath each measurement.

## User Stories

- As an estimator, I want to see all my takeoff measurements organized in a tree grouped by condition so that I can quickly review totals and drill into individual measurements.
- As an estimator, I want to see subtotals per condition and per sheet so that I can verify quantities floor-by-floor or area-by-area.
- As an estimator, I want to click a row in the quantities panel and have the corresponding measurement highlighted on the plan so that I can visually verify what was measured.
- As an estimator, I want to click a measurement on the plan and have the corresponding row highlighted and scrolled-to in the quantities panel so that I can see its details.
- As an estimator, I want to manually override a measured quantity when I know the actual value differs from what was drawn so that my final numbers are accurate.
- As an estimator, I want to see a visual indicator when a quantity has been manually overridden so that I know which values are drawn vs. adjusted.
- As an estimator, I want to expand a measurement row to see the assembly item breakdown (drywall sheets, studs, screws, etc.) so that I can verify derived quantities.
- As an estimator, I want to delete a measurement from the quantities panel and have it removed from the plan so that I can clean up mistakes.

## Key Requirements

### Grouped Tree View

The panel displays a collapsible tree structure:

```
▼ Interior Wall - 8' Drywall          Total: 1,250 LF
    ▼ Sheet A1.01 - First Floor         Subtotal: 500 LF
        ├── Measurement 1                320 LF
        │   ▼ Assembly Items
        │       ├── Drywall Sheets       250 sheets
        │       ├── Metal Studs          376 EA
        │       └── Screws               12,000 EA
        └── Measurement 2                180 LF
            ▼ Assembly Items
                ├── ...
    ▼ Sheet A1.02 - Second Floor        Subtotal: 750 LF
        ├── Measurement 3                410 LF
        └── Measurement 4                340 LF

▼ Exterior Wall - Brick Veneer         Total: 890 LF
    ▼ Sheet A1.01 - First Floor         Subtotal: 520 LF
        ├── ...
```

- **Level 1**: Conditions (collapsible, shows grand total)
- **Level 2**: Sheets within each condition (collapsible, shows sheet subtotal)
- **Level 3**: Individual measurements (shows measured quantity)
- **Level 4**: Assembly items (expandable under each measurement, shows derived quantities)

### Subtotals

- Condition-level grand total aggregating all measurements across all sheets
- Sheet-level subtotal for each condition showing per-sheet quantities
- Subtotals update in real-time as measurements are added, edited, or deleted
- Assembly item totals also aggregate at the condition level (total drywall sheets across all measurements of that condition)

### Bidirectional Plan Linking

- **Panel to Plan**: Click/select a row in the panel -- the corresponding measurement highlights on the plan, and the viewport auto-pans/zooms to show it if it's off-screen
- **Plan to Panel**: Click/select a measurement on the plan -- the corresponding row highlights in the panel and auto-scrolls into view
- Multi-select supported: select multiple rows to highlight multiple measurements, or box-select on the plan to highlight multiple rows
- Active sheet in the viewer automatically expands/focuses the corresponding sheet group in the panel

### Manual Quantity Override

- Double-click a quantity value to enter edit mode
- Type a new value to override the measured quantity
- A visual indicator (e.g., icon, color change, or badge) marks overridden values so they're distinguishable from drawn measurements
- Overridden quantities still participate in assembly formula calculations (formulas use the override value)
- "Reset to measured" option to revert an override back to the drawn value
- Override history tracked (original measured value always preserved)

### Assembly Item Display

- Each measurement row has an expand/collapse toggle to show its assembly item breakdown
- Assembly items show: item name, calculated quantity, and unit of measure
- Assembly items are read-only in the quantities panel (edit formulas via the condition/assembly settings)
- Assembly items recalculate in real-time when the measurement or condition properties change

### Row Actions

- **Delete**: Remove a measurement from both the panel and the plan
- **Reassign Condition**: Change the condition of a measurement (triggers re-style and recalculation)
- **Navigate to**: Pan/zoom the plan to center on the measurement
- **Override**: Enter manual override mode for the quantity value
- Right-click context menu or action buttons per row

### Column Layout (Fixed)

| Column | Description |
|--------|-------------|
| Name / Label | Condition name (level 1), sheet name (level 2), measurement label (level 3), assembly item name (level 4) |
| Quantity | Measured or overridden value |
| Unit | Unit of measure (LF, SF, EA, etc.) |
| Override Indicator | Visual marker if quantity was manually overridden |

## Nice-to-Have

- **Search and filter** -- filter by condition name, measurement type, sheet, trade (planned for post-MVP)
- **Flexible grouping** -- let users choose grouping order: condition > sheet, sheet > condition, trade > condition > sheet (planned for post-MVP)
- **Custom columns** -- user-defined columns for additional data (notes, phase, location, status)
- **Formula columns** -- custom columns that calculate values (e.g., quantity x waste factor)
- **Separate assembly summary view** -- a project-wide tab that aggregates all assembly items across all conditions (e.g., total drywall sheets for the entire project)
- **Drag-and-drop reordering** of conditions and measurements
- **Bulk editing** -- select multiple measurements and change properties in batch
- **Print / export** the quantities panel directly as a report
- **Condition color indicators** in the tree view to match the plan visualization
- **Collapse/expand all** toggle for quick overview vs. detail views

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | "Takeoff" tab with a tree view grouped by page/item. Supports inline editing of quantities. Assembly items shown as sub-items. Bidirectional linking with plan. Desktop-only. Full-featured but complex UI. |
| Bluebeam | "Markups" list showing all annotations. Not a takeoff-oriented quantities panel. No assembly concept. Can sort/filter markups but lacks the structured tree view estimators need. |
| On-Screen Takeoff | Conditions panel with tree grouping. Per-sheet and total quantities. Bidirectional linking with plan. Limited assembly display. Manual override supported. Desktop-only. |
| Togal.AI | Quantities table showing AI-detected areas/lengths. Simpler flat table. Limited grouping. No assembly item breakdown. Focused on the AI output rather than detailed quantity management. |

## Open Questions

- [ ] How should the panel handle very large projects with hundreds of conditions and thousands of measurements? (virtualized scrolling, lazy loading?)
- [ ] Should assembly item totals be aggregated at the condition level (total studs across all walls) or only shown per-measurement?
- [ ] When a user overrides a quantity, should the override propagate to assembly items or should assembly items always calculate from the original measurement?
- [ ] Should the panel support keyboard navigation (arrow keys to move between rows, Enter to expand/collapse)?
- [ ] How do we handle the panel in collaboration mode? (real-time updates as other users add measurements, scroll position preservation)

## Technical Considerations

- The tree view needs **virtualized rendering** for large projects -- can't render thousands of DOM nodes. Libraries like react-window or tanstack-virtual can handle this.
- Bidirectional linking requires a fast lookup map between measurement IDs and their panel row positions, plus viewport math for auto-panning on the plan side.
- Manual overrides need a clear data model: each measurement stores both `measured_value` (computed from geometry) and `override_value` (user-entered, nullable). Display logic: `override_value ?? measured_value`.
- Real-time subtotal aggregation should use incremental updates rather than recalculating the full tree on every change -- important for collaboration sync performance.
- The panel is a **collaboration-aware** component: when User A adds a measurement, User B's panel should update in real-time with smooth insertion (not a jarring full re-render).
- Assembly item expansion state (which rows are expanded) is local UI state, not synced across collaborators.

## Notes

- The quantities panel is where estimators spend roughly half their time -- the other half is on the plan itself. It must be fast, responsive, and feel like a native spreadsheet. Any lag in scrolling, expanding, or updating will frustrate power users.
- Bidirectional linking between the plan and the panel is one of the most satisfying UX features in takeoff software. When it works well, it creates a feeling of everything being connected and verifiable. When it's missing (like in Bluebeam), estimators constantly lose track of which measurement they're looking at.
- Starting with fixed columns is the right MVP call. Custom columns add significant UI complexity (column management, resizing, reordering) and most estimators' immediate needs are served by the fixed layout. Search/filter and flexible grouping are the highest-value post-MVP enhancements.
- Manual override with a visual indicator is critical for professional estimators who need to adjust AI or drawn values but also need an audit trail of what was measured vs. what was submitted.
