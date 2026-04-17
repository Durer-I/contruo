# Sprint 10: Formula Engine & Assemblies

> **Phase:** 3 - Takeoff Tools
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 07 (conditions), Sprint 09 (all measurement types working)

## Sprint Goal

Build the formula engine and assembly items system. At the end of this sprint, users can define assembly items with formulas on conditions, and every measurement automatically calculates derived quantities (e.g., 100 LF of wall -> 50 drywall sheets, 76 studs, 2,400 screws).

---

## Tasks

### 1. Formula Engine
- [ ] Create `formula_engine.py` module (shared service)
- [ ] Implement expression parser supporting:
  - Arithmetic operators: `+`, `-`, `*`, `/`, `^`, `()`
  - Functions: `round()`, `ceil()`, `floor()`, `min()`, `max()`, `abs()`
  - Variable resolution from a provided context dictionary
- [ ] Evaluate library options: `py_expression_eval`, `simpleeval`, or custom tokenizer
- [ ] Variable injection: `length`, `area`, `count`, `perimeter` + custom condition properties
- [ ] Comprehensive error handling: syntax errors, missing variables, division by zero
- [ ] Unit tests for the formula engine (edge cases, complex expressions)

### 2. Assembly Items CRUD
- [ ] Create `assembly_items` table migration (with `parent_id` for future nesting)
- [ ] Implement API endpoints:
  - `POST /api/v1/conditions/:id/assembly-items` -- add assembly item
  - `PATCH /api/v1/assembly-items/:id` -- update assembly item
  - `DELETE /api/v1/assembly-items/:id` -- delete assembly item
  - `GET /api/v1/conditions/:id/assembly-items` -- list assembly items
- [ ] RLS policies on assembly_items table

### 3. Assembly Items UI (Condition Manager)
- [ ] Add assembly items section to the condition manager detail view
- [ ] Assembly items table: item name | unit | formula | (calculated preview)
- [ ] "Add Item" button to add a new row
- [ ] Inline editing for item name, unit, and formula
- [ ] Delete button per row
- [ ] Drag to reorder items (sort_order)

### 4. Formula Editor
- [ ] Text input field for formulas with syntax highlighting
- [ ] Autocomplete dropdown for available variables:
  - Measurement variable (`length`, `area`, `count` depending on condition type)
  - `perimeter` (for area conditions)
  - Custom properties from the condition (e.g., `height`, `spacing`, `depth`)
- [ ] Live preview: show calculated result using a sample measurement value
- [ ] Validation feedback: show error message inline if formula is invalid
- [ ] Variables panel: small reference showing available variables and their current values

### 5. Derived Quantity Calculation
- [ ] When a measurement is created or edited, evaluate all assembly item formulas
- [ ] Store derived quantities as computed values (not persisted -- recalculated on demand)
- [ ] When a condition property changes, recalculate all derived quantities for measurements using that condition
- [ ] API endpoint returns measurements with their derived quantities included
- [ ] Handle formula errors gracefully: show "Error" instead of crashing

### 6. Condition Templates (Org Library)
- [ ] Create `condition_templates` table migration
- [ ] Implement API endpoints:
  - `GET /api/v1/org/templates` -- list templates
  - `POST /api/v1/org/templates` -- create template (from existing condition or from scratch)
  - `DELETE /api/v1/org/templates/:id` -- delete template
  - `POST /api/v1/projects/:id/conditions/import` -- import template into project (deep copy)
- [ ] "Save as Template" action on any project condition
- [ ] "Import from Templates" button in the condition manager
- [ ] Template browser: list of org templates with name, type, assembly item count
- [ ] Import creates an independent copy (no linking)

### 7. Condition Reassignment
- [ ] Select a measurement -> "Change Condition" in context menu or properties panel
- [ ] Dropdown showing compatible conditions (same measurement type only)
- [ ] On reassignment: re-style the measurement, recalculate all assembly quantities
- [ ] Log event: `measurement.edited` with condition change details

---

## Acceptance Criteria

- [ ] Formula engine correctly evaluates expressions with variables and functions
- [ ] Users can add assembly items to conditions with name, unit, and formula
- [ ] Formula editor provides autocomplete for available variables
- [ ] Live preview shows the calculated result for a sample value
- [ ] Invalid formulas show clear error messages
- [ ] When a measurement is created, all assembly item quantities are calculated
- [ ] When a condition property changes, derived quantities update for all affected measurements
- [ ] Users can save a condition as an org template
- [ ] Users can import a template into a project (creates an independent copy)
- [ ] Users can reassign a measurement to a different condition of the same type

---

## Key References

- [Conditions & Assemblies Feature](../features/core/conditions-and-assemblies.md) -- assemblies, formulas, templates
- [Backend Architecture - Formula Engine](../docs/architecture/backend.md)
- [Screen Layouts - Condition Manager](../docs/design/screen-layouts.md)
