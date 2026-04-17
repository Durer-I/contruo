# Sprint 07: Conditions System

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 03 (org management), Sprint 06 (toolbar foundation)

## Sprint Goal

Build the conditions system -- the organizational backbone of every takeoff. At the end of this sprint, users can create, edit, and manage conditions with full styling properties, and select a condition before drawing measurements.

---

## Tasks

### 1. Condition CRUD
- [ ] Create `conditions` table migration
- [ ] Implement API endpoints:
  - `GET /api/v1/projects/:id/conditions` -- list conditions
  - `POST /api/v1/projects/:id/conditions` -- create condition
  - `PATCH /api/v1/conditions/:id` -- update condition
  - `DELETE /api/v1/conditions/:id` -- delete condition
- [ ] RLS policies on conditions table

### 2. Condition Manager UI
- [ ] Create condition manager panel (side panel or dialog, per screen-layouts.md)
- [ ] Top section: list of all conditions with color dot, name, type, current total (0 initially)
- [ ] Click a condition to select it for editing in the detail section
- [ ] Bottom section: detail editor for the selected condition

### 3. Condition Properties Form
- [ ] Required fields: name, measurement type (linear/area/count dropdown), unit (LF/SF/EA/etc.), color picker
- [ ] Style fields: line style (solid/dashed/dotted), line width slider, fill opacity slider (for area), fill pattern (solid/hatch/crosshatch)
- [ ] Custom properties section: add key-value pairs (e.g., height: 8, spacing: 16)
  - "Add Property" button
  - Property name input + value input + unit label + delete button
  - Properties stored as JSONB in the database
- [ ] Optional fields: trade/CSI division, description, notes
- [ ] Save and cancel buttons

### 4. Color Picker
- [ ] Preset color palette using the 12 takeoff condition colors from the design system
- [ ] Click to select a preset color
- [ ] Optional: custom hex input for advanced users
- [ ] Selected color previews on the condition list dot and the plan overlay

### 5. Condition Selector in Toolbar
- [ ] Dropdown in the takeoff toolbar showing available conditions
- [ ] Shows condition name + color swatch
- [ ] Quick-switch keyboard shortcuts (1-9 for first 9 conditions)
- [ ] Currently selected condition shown in the status bar

### 6. Condition Deletion
- [ ] Confirmation dialog when deleting a condition
- [ ] Warning if the condition has measurements attached: "This condition has X measurements. Deleting it will remove all associated measurements."
- [ ] Cascade delete measurements when condition is deleted

---

## Acceptance Criteria

- [ ] User can create a new condition with name, type, color, and style properties
- [ ] User can add custom properties (height, spacing, depth, etc.) to a condition
- [ ] User can edit any condition property and changes are saved
- [ ] Condition list shows all conditions with color indicators and measurement type
- [ ] User can select a condition from the toolbar dropdown for active use
- [ ] Keyboard shortcuts (1-9) switch between conditions
- [ ] Status bar shows the currently selected condition
- [ ] Deleting a condition shows a confirmation with measurement count warning
- [ ] All condition data persists across sessions

---

## Key References

- [Conditions & Assemblies Feature](../features/core/conditions-and-assemblies.md) -- properties, styling
- [Screen Layouts - Condition Manager](../docs/design/screen-layouts.md)
- [Design System - Takeoff Condition Colors](../docs/design/design-system.md)
