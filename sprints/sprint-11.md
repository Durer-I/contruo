# Sprint 11: Quantities Panel

> **Phase:** 4 - Data & Export
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 09 (all measurement types), Sprint 10 (assemblies & derived quantities)

## Sprint Goal

Build the quantities panel -- the structured data view of all takeoff work. At the end of this sprint, users can review all measurements in a grouped tree view with subtotals, bidirectional linking between the panel and the plan, manual quantity overrides, and expandable assembly item breakdowns.

---

## Tasks

### 1. Grouped Tree View
- [ ] Replace the quantities panel placeholder (from Sprint 05) with the real implementation
- [ ] Tree structure: Condition > Sheet > Measurement > Assembly Items
- [ ] Collapsible/expandable nodes at every level
- [ ] Condition rows: show name, color dot, grand total, unit
- [ ] Sheet rows: show sheet name, subtotal
- [ ] Measurement rows: show label or auto-generated name, quantity value, unit
- [ ] Assembly item rows: show item name, calculated quantity, unit

### 2. Subtotals & Aggregation
- [ ] Condition-level grand total (sum of all measurements across all sheets)
- [ ] Sheet-level subtotal per condition
- [ ] Assembly item totals aggregated at condition level
- [ ] Subtotals update in real-time as measurements are added, edited, or deleted
- [ ] Grand total row at the bottom (optional)

### 3. Bidirectional Linking
- [ ] **Panel to Plan**: click a measurement row -> highlight the measurement on the plan
  - Auto-pan/zoom to show the measurement if it's off-screen
  - Switch to the correct sheet if the measurement is on a different sheet
- [ ] **Plan to Panel**: click a measurement on the plan -> highlight and scroll-to the row in the panel
- [ ] Multi-select: select multiple rows to highlight multiple measurements (and vice versa)
- [ ] Active sheet auto-expands the corresponding sheet group in the panel

### 4. Manual Quantity Override
- [ ] Double-click a quantity value in the panel to enter edit mode
- [ ] Type a new value to override the measured quantity
- [ ] Visual indicator (icon or color change) on overridden values
- [ ] Overridden values used by assembly formula calculations
- [ ] "Reset to measured" option (right-click or button) to revert override
- [ ] Original measured value always preserved in the data model
- [ ] Implement `PATCH /api/v1/measurements/:id` with `override_value` field

### 5. Assembly Item Display
- [ ] Expand/collapse toggle on each measurement row to show assembly items
- [ ] Assembly items are read-only in the panel (edit via condition manager)
- [ ] Assembly items recalculate when measurement or condition properties change
- [ ] Show calculation in a tooltip on hover (e.g., "100 LF x 8' height x 2 / 32 = 50 sheets")

### 6. Row Actions
- [ ] Right-click context menu per measurement row:
  - Navigate to (pan/zoom to measurement on plan)
  - Change Condition (reassign)
  - Override Value
  - Delete (with confirmation)
- [ ] Delete from panel removes the measurement from both panel and plan
- [ ] Keyboard: Delete key removes selected measurement

### 7. Performance
- [ ] Virtualized rendering for large projects (react-window or tanstack-virtual)
- [ ] Lazy expansion: assembly items calculated on expand, not pre-loaded for all rows
- [ ] Smooth scrolling with hundreds of rows

---

## Acceptance Criteria

- [ ] Quantities panel shows a grouped tree: Condition > Sheet > Measurement > Assembly Items
- [ ] Subtotals are correct at condition and sheet levels
- [ ] Clicking a row highlights the measurement on the plan and auto-navigates to it
- [ ] Clicking a measurement on the plan highlights the row and scrolls to it
- [ ] User can double-click a value to override it, with a visual indicator
- [ ] Overridden values propagate to assembly formula calculations
- [ ] "Reset to measured" reverts an override
- [ ] Assembly items expand under each measurement with correct calculated values
- [ ] Context menu provides quick actions (navigate, change condition, delete)
- [ ] Panel performs well with 200+ measurements (virtualized)

---

## Key References

- [Quantity Management Feature](../features/core/quantity-management.md)
- [Screen Layouts - Plan Viewer Workspace](../docs/design/screen-layouts.md)
