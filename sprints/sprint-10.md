# Sprint 10: Formula Engine & Assemblies

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** Partial (core shipped; polish deferred)
> **Depends On:** Sprint 07 (conditions), Sprint 09 (all measurement types working)

## Sprint Goal

Build the formula engine and assembly items system. At the end of this sprint, users can define assembly items with formulas on conditions, and every measurement automatically calculates derived quantities (e.g., 100 LF of wall -> 50 drywall sheets, 76 studs, 2,400 screws).

---

## Tasks

### 1. Formula Engine
- [x] Create `formula_engine.py` module (shared service) — `app/services/formula_engine.py`
- [x] Implement expression parser supporting:
  - Arithmetic operators: `+`, `-`, `*`, `/`, `^`, `()`
  - Functions: `round()`, `ceil()`, `floor()`, `min()`, `max()`, `abs()`
  - Variable resolution from a provided context dictionary
- [x] Evaluate via restricted **AST** (no third-party eval dependency)
- [x] Variable injection: `length`, `area`, `count`, `perimeter` + custom condition properties (sanitized names)
- [x] Comprehensive error handling: syntax errors, missing variables, division by zero
- [x] Unit tests for the formula engine (`tests/unit/test_formula_engine.py`)

### 2. Assembly Items CRUD
- [x] Create `assembly_items` table migration (with `parent_id` for future nesting) — Alembic `006`
- [x] Implement API endpoints:
  - `POST /api/v1/conditions/:id/assembly-items`
  - `PATCH /api/v1/assembly-items/:id`
  - `DELETE /api/v1/assembly-items/:id`
  - `GET /api/v1/conditions/:id/assembly-items`
  - `POST /api/v1/conditions/:id/assembly-formula-preview` (live preview)
- [x] RLS policies on `assembly_items` table (migration)

### 3. Assembly Items UI (Condition Manager)
- [x] Add assembly items section to the condition manager detail view
- [x] Assembly items table: item name | unit | formula | preview
- [x] "Add Item" button to add a new row
- [x] Inline editing for item name, unit, and formula (save on blur)
- [x] Delete button per row
- [ ] Drag to reorder items (`sort_order`) — **deferred** (PATCH `sort_order` supported)

### 4. Formula Editor
- [x] Text input field for formulas
- [ ] Syntax highlighting — **deferred**
- [x] Variables reference (inline help + preview API uses saved condition properties)
- [x] Live preview: `assembly-formula-preview` with sample primary (and perimeter for area)
- [x] Validation feedback: preview shows error string from engine
- [x] Variables panel: short reference in assembly section

### 5. Derived Quantity Calculation
- [x] When a measurement is created or edited, evaluate all assembly item formulas (on read)
- [x] Store derived quantities as computed values (not persisted — recalculated on demand)
- [x] When a condition property changes, next measurement fetch recalculates derived quantities
- [x] API returns measurements with `derived_quantities` on each `MeasurementResponse`
- [x] Handle formula errors gracefully: `error` string per item instead of crashing

### 6. Condition Templates (Org Library)
- [x] Create `condition_templates` table migration
- [x] Implement API endpoints:
  - `GET /api/v1/org/condition-templates`
  - `POST /api/v1/org/conditions/:id/save-as-template`
  - `DELETE /api/v1/org/condition-templates/:id`
  - `POST /api/v1/projects/:id/conditions/import-from-template`
- [x] "Save as Template" on project condition
- [x] "Import from Templates" in condition manager (dialog)
- [x] Template list shows name, type, assembly item count
- [x] Import creates an independent copy (condition + assembly rows)

### 7. Condition Reassignment
- [x] Select a measurement (select tool) → "Change condition" strip above footer
- [x] Dropdown showing compatible conditions (same measurement type only)
- [x] On reassignment: `PATCH` with `condition_id`, recompute `measured_value`, restyle via refetch
- [x] Log event: `measurement.edited` with fields including `condition_id`

---

## Acceptance Criteria

- [x] Formula engine correctly evaluates expressions with variables and functions
- [x] Users can add assembly items to conditions with name, unit, and formula
- [ ] Formula editor autocomplete — **deferred** (help text + preview only)
- [x] Live preview shows the calculated result for a sample value
- [x] Invalid formulas show clear error messages (preview + derived list)
- [x] When a measurement is created, all assembly item quantities are calculated on response
- [x] When a condition property changes, derived quantities update on next load
- [x] Users can save a condition as an org template
- [x] Users can import a template into a project (independent copy)
- [x] Users can reassign a measurement to a different condition of the same type

---

## Key References

- [Conditions & Assemblies Feature](../features/core/conditions-and-assemblies.md) -- assemblies, formulas, templates
- [Backend Architecture - Formula Engine](../docs/architecture/backend.md)
- [Screen Layouts - Condition Manager](../docs/design/screen-layouts.md)
