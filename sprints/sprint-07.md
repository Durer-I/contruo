# Sprint 07: Conditions System

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** Complete
> **Depends On:** Sprint 03 (org management), Sprint 06 (toolbar foundation)

## Sprint Goal

Build the conditions system -- the organizational backbone of every takeoff. At the end of this sprint, users can create, edit, and manage conditions with full styling properties, and select a condition before drawing measurements.

---

## Tasks

### 1. Condition CRUD
- [x] Create `conditions` table migration
- [x] Implement API endpoints:
  - `GET /api/v1/projects/:id/conditions` -- list conditions
  - `POST /api/v1/projects/:id/conditions` -- create condition
  - `PATCH /api/v1/conditions/:id` -- update condition
  - `DELETE /api/v1/conditions/:id` -- delete condition
- [x] RLS policies on conditions table

### 2. Condition Manager UI
- [x] Create condition manager panel (side panel or dialog, per screen-layouts.md)
- [x] Top section: list of all conditions with color dot, name, type, current total (0 initially)
- [x] Click a condition to select it for editing in the detail section
- [x] Bottom section: detail editor for the selected condition

### 3. Condition Properties Form
- [x] Required fields: name, measurement type (linear/area/count dropdown), unit (LF/SF/EA/etc.), color picker
- [x] Style fields: line style (solid/dashed/dotted), line width slider, fill opacity slider (for area), fill pattern (solid/hatch/crosshatch)
- [x] Custom properties section: add key-value pairs (e.g., height: 8, spacing: 16)
  - "Add Property" button
  - Property name input + value input + unit label + delete button
  - Properties stored as JSONB in the database
- [x] Optional fields: trade/CSI division, description, notes
- [x] Save and cancel buttons

### 4. Color Picker
- [x] Preset color palette using the 12 takeoff condition colors from the design system
- [x] Click to select a preset color
- [x] Optional: custom hex input for advanced users
- [x] Selected color previews on the condition list dot and the plan overlay

### 5. Condition Selector in Toolbar
- [x] Dropdown in the takeoff toolbar showing available conditions
- [x] Shows condition name + color swatch
- [x] Quick-switch keyboard shortcuts (1-9 for first 9 conditions)
- [x] Currently selected condition shown in the status bar

### 6. Condition Deletion
- [x] Confirmation dialog when deleting a condition
- [x] Warning if the condition has measurements attached: "This condition has X measurements. Deleting it will remove all associated measurements."
- [x] Cascade delete measurements when condition is deleted

---

## Acceptance Criteria

- [x] User can create a new condition with name, type, color, and style properties
- [x] User can add custom properties (height, spacing, depth, etc.) to a condition
- [x] User can edit any condition property and changes are saved
- [x] Condition list shows all conditions with color indicators and measurement type
- [x] User can select a condition from the toolbar dropdown for active use
- [x] Keyboard shortcuts (1-9) switch between conditions
- [x] Status bar shows the currently selected condition
- [x] Deleting a condition shows a confirmation with measurement count warning
- [x] All condition data persists across sessions

---

## Key References

- [Conditions & Assemblies Feature](../features/core/conditions-and-assemblies.md) -- properties, styling
- [Screen Layouts - Condition Manager](../docs/design/screen-layouts.md)
- [Design System - Takeoff Condition Colors](../docs/design/design-system.md)
