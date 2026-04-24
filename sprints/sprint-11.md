# Sprint 11: Quantities Panel

> **Phase:** 4 - Data & Export
> **Duration:** 2 weeks
> **Status:** In Progress
> **Depends On:** Sprint 09 (all measurement types), Sprint 10 (assemblies & derived quantities)

## Sprint Goal

Build the quantities panel -- the structured data view of all takeoff work. At the end of this sprint, users can review all measurements in a grouped tree view with subtotals, bidirectional linking between the panel and the plan, manual quantity overrides, and expandable assembly item breakdowns.

---

## Tasks

### 1. Grouped Tree View
- [x] Replace the quantities panel placeholder (from Sprint 05) with the real implementation
- [x] Tree structure: Condition > Sheet > Measurement > Assembly Items
- [x] Collapsible/expandable nodes at every level
- [x] Condition rows: show name, color dot, grand total, unit
- [x] Sheet rows: show sheet name, subtotal
- [x] Measurement rows: show label or auto-generated name, quantity value, unit
- [x] Assembly item rows: show item name, calculated quantity, unit

### 2. Subtotals & Aggregation
- [x] Condition-level grand total (sum of all measurements across all sheets)
- [x] Sheet-level subtotal per condition
- [x] Assembly item totals aggregated at condition level
- [x] Subtotals update in real-time as measurements are added, edited, or deleted
- [x] Grand total row at the bottom (optional) — footer shows measurement count (mixed units make a single sum misleading)

### 3. Bidirectional Linking
- [x] **Panel to Plan**: click a measurement row -> highlight the measurement on the plan
  - Auto-pan/zoom to show the measurement if it's off-screen
  - Switch to the correct sheet if the measurement is on a different sheet
- [x] **Plan to Panel**: click a measurement on the plan -> highlight and scroll-to the row in the panel
- [x] Multi-select: select multiple rows to highlight multiple measurements (and vice versa)
- [x] Active sheet auto-expands the corresponding sheet group in the panel

### 4. Manual Quantity Override
- [x] Double-click a quantity value in the panel to enter edit mode
- [x] Type a new value to override the measured quantity
- [x] Visual indicator (icon or color change) on overridden values
- [x] Overridden values used by assembly formula calculations
- [x] "Reset to measured" option (right-click or button) to revert override
- [x] Original measured value always preserved in the data model
- [x] Implement `PATCH /api/v1/measurements/:id` with `override_value` field (already implemented; wired from panel)

### 5. Assembly Item Display
- [x] Expand/collapse toggle on each measurement row to show assembly items
- [x] Assembly items are read-only in the panel (edit via condition manager)
- [x] Assembly items recalculate when measurement or condition properties change
- [x] Show calculation in a tooltip on hover (e.g., "100 LF x 8' height x 2 / 32 = 50 sheets")

### 6. Row Actions
- [x] Right-click context menu per measurement row:
  - Navigate to (pan/zoom to measurement on plan)
  - Change Condition (reassign)
  - Override Value
  - Delete (with confirmation)
- [x] Delete from panel removes the measurement from both panel and plan
- [x] Keyboard: Delete key removes selected measurement

### 7. Performance
- [x] Virtualized rendering for large projects (react-window or tanstack-virtual)
- [x] Lazy expansion: assembly items calculated on expand, not pre-loaded for all rows
- [x] Smooth scrolling with hundreds of rows

---

## Acceptance Criteria

- [x] Quantities panel shows a grouped tree: Condition > Sheet > Measurement > Assembly Items
- [x] Subtotals are correct at condition and sheet levels
- [x] Clicking a row highlights the measurement on the plan and auto-navigates to it
- [x] Clicking a measurement on the plan highlights the row and scrolls to it
- [x] User can double-click a value to override it, with a visual indicator
- [x] Overridden values propagate to assembly formula calculations
- [x] "Reset to measured" reverts an override
- [x] Assembly items expand under each measurement with correct calculated values
- [x] Context menu provides quick actions (navigate, change condition, delete)
- [x] Panel performs well with 200+ measurements (virtualized)

---

## Key References

- [Quantity Management Feature](../features/core/quantity-management.md)
- [Screen Layouts - Plan Viewer Workspace](../docs/design/screen-layouts.md)
