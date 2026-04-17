# Conditions & Assemblies

> **Category:** Core Takeoff
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Conditions and assemblies are the organizational backbone of every takeoff in Contruo. A **condition** is a named, styled category that a measurement belongs to (e.g., "Interior Wall - 8' Drywall on Metal Studs"). An **assembly** is a list of material/labor items attached to a condition, where each item has a formula that derives a quantity from the measurement (e.g., from 500 LF of wall, auto-calculate 250 drywall sheets, 375 studs, 12,000 screws).

Conditions live at the project level and can be imported from an **organization template library** for reuse across projects. Assemblies at MVP support a flat list of items per condition, with the data model architected to support nested sub-assemblies in a future release.

## User Stories

- As an estimator, I want to create a condition with a name, color, line style, and measurement type so that I can categorize and visually distinguish my measurements on the plan.
- As an estimator, I want to define assembly items on a condition with formulas so that a single measurement auto-calculates all related material and labor quantities.
- As an estimator, I want to write formulas like `length * height * 2 / 32` with autocomplete for available variables so that I can express any quantity relationship.
- As an estimator, I want to define custom properties on a condition (e.g., wall height, stud spacing, thickness) so that my formulas can reference them as variables.
- As an estimator, I want to reassign a completed measurement to a different condition so that it re-styles on the plan and recalculates all assembly quantities without redrawing.
- As an estimator, I want to import conditions from my organization's template library into a project so that I don't have to recreate them every time.
- As a team lead, I want to maintain a shared template library of conditions and assemblies for my organization so that my team uses consistent takeoff categories.
- As an estimator, I want to optionally assign a trade/CSI division, description, and notes to a condition so that my takeoff is well-organized for reporting.

## Key Requirements

### Condition Properties

| Property | Required? | Description |
|----------|-----------|-------------|
| Name | Required | Descriptive name (e.g., "Interior Wall - 8' Drywall on Metal Studs") |
| Color | Required | Display color for measurements on the plan |
| Line Style / Fill Pattern | Required | Line thickness, dash pattern (linear), fill color/opacity/pattern (area), dot style (count) |
| Measurement Type | Required | Linear, Area, or Count -- determines which takeoff tool uses this condition |
| Unit of Measure | Required | LF, SF, EA, CF, etc. -- the primary unit for the measured quantity |
| Custom Properties | Optional | User-defined variables (height, depth, spacing, thickness, etc.) used in assembly formulas |
| Trade / CSI Division | Optional | Organizational grouping (e.g., "03 - Concrete," "09 - Finishes") |
| Description | Optional | Longer description of what this condition measures |
| Notes | Optional | Freeform notes for the estimator's reference |

### Assembly Items (Flat List per Condition)

Each condition can have zero or more assembly items. Each assembly item defines:

- **Item Name** -- what is being calculated (e.g., "Drywall Sheets (4x8)")
- **Unit of Measure** -- the unit for this derived quantity (e.g., sheets, EA, LF, SF)
- **Formula** -- an expression that computes the quantity from the measurement and condition properties
- **Description** (optional) -- notes about the formula or item

Example assembly for "Interior Wall - 8' Drywall on Metal Studs" (height = 8', spacing = 16"):

| Item Name | Unit | Formula | Result (for 500 LF) |
|-----------|------|---------|---------------------|
| Drywall Sheets (4x8) | sheets | (length * height * 2) / 32 | 250 |
| Metal Studs (3-5/8") | EA | length / (spacing / 12) + 1 | 376 |
| Drywall Screws | EA | length * height * 2 * 1.5 | 12,000 |
| Joint Tape | LF | length * 4 | 2,000 |
| Joint Compound | gal | (length * height * 2) / 100 | 80 |

### Formula Editor

- Text-based formula editor with syntax highlighting
- Autocomplete for available variables: measurement value (`length`, `area`, `count`), custom properties (`height`, `depth`, `spacing`, etc.), and constants
- Support for standard math operators: `+`, `-`, `*`, `/`, `()`, `^`
- Support for common functions: `round()`, `ceil()`, `floor()`, `min()`, `max()`, `abs()`
- Live preview showing the calculated result based on a sample measurement value
- Validation with clear error messages for invalid formulas
- Variables panel showing all available variables and their current values

### Condition Reassignment

- Select any completed measurement on the plan
- Choose "Change Condition" from the context menu or properties panel
- Pick a new condition (must be the same measurement type -- can't switch a linear measurement to an area condition)
- The measurement re-styles to the new condition's visual properties
- All assembly quantities recalculate using the new condition's formulas and properties

### Organization Template Library

- Organization admins can create and manage a shared library of condition templates
- Templates include the full condition definition: properties, styling, assembly items, and formulas
- Import into a project as a **copy** -- the imported condition is independent and changes don't sync back to the template
- Templates can be organized by trade or category
- Import individually or in bulk (e.g., "import all Framing conditions")

### Data Model: Future-Proofed for Nested Assemblies

At MVP, assemblies are a flat list of items. However, the data model should be structured to support nesting in a future release:

- Each assembly item has an optional `parent_id` field (null at MVP, used later for sub-assembly grouping)
- Each assembly item has a `sort_order` field for display ordering
- This allows a future upgrade to nested assemblies (e.g., "Interior Wall" > "Framing" sub-assembly > individual framing items) without a data migration

## Nice-to-Have

- **Nested sub-assemblies** -- an assembly contains sub-assemblies, each with their own item list (future release, data model ready)
- **Contruo-provided starter templates** for common trades (framing, drywall, concrete, electrical, plumbing, etc.)
- **Assembly duplication** -- duplicate a condition and its assembly to create a variant quickly
- **Formula templates** -- pre-built formula patterns for common calculations (area from linear + height, stud count from length + spacing, etc.)
- **Condition color auto-assignment** -- suggest distinct colors to avoid visual conflicts on the plan
- **Bulk condition creation** -- import conditions from a CSV or spreadsheet
- **Assembly cost linking** -- link assembly items to the Cost Database for automatic cost calculations (planned for P1 Cost & Estimation features)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Strong condition system with "Items" that act as assemblies. Each item has properties and formulas. Template library called "Item Templates." Desktop-only. Formulas use a custom expression syntax. Supports nested assemblies. |
| Bluebeam | No condition/assembly system -- it's a PDF markup tool, not a takeoff system. Measurements are standalone annotations without material linkage. |
| On-Screen Takeoff | "Conditions" with properties and derived quantities. "Condition Templates" for reuse. Formula-based derived quantities. Similar concept to PlanSwift but less flexible formula system. Desktop-only. |
| Togal.AI | Minimal condition system -- AI auto-assigns categories. Limited manual condition configuration. Assemblies not a core feature; focused on area/linear detection. |

## Open Questions

- [ ] Should the formula editor support conditional logic (IF/THEN) or keep it to pure math expressions at MVP?
- [ ] How should formula errors be handled when a required variable is missing (e.g., height not set)? Show zero, show warning, or block?
- [ ] Should condition templates be versioned in the org library (so teams can see what changed)?
- [ ] What's the maximum practical number of assembly items per condition before the UX becomes unwieldy?
- [ ] Should there be a "preview" mode that shows what an assembly would produce for a hypothetical measurement before actually drawing?

## Technical Considerations

- The formula engine is a shared component used by Linear, Area, Count, and Volume takeoff -- it should be built as an independent, well-tested module
- Formula parsing needs a lightweight expression evaluator (not a full scripting language) -- consider math.js, expr-eval, or a custom parser
- Condition reassignment must trigger a cascading recalculation of all assembly items for that measurement -- needs to be performant for bulk reassignments
- Template import creates deep copies of the condition + all assembly items -- need to handle ID remapping correctly
- The `parent_id` field for future nesting should be in the schema from day one to avoid migrations
- Conditions and their assemblies need to sync in real-time for collaboration -- when one user changes a condition's properties, all collaborators see updated assembly calculations immediately
- Formula validation should happen client-side in real-time (as the user types) and server-side on save

## Notes

- This feature is the **intellectual core** of Contruo. The Plan Viewer is the canvas and the takeoff tools are the brushes, but conditions and assemblies are where the estimator's expertise lives. A well-configured condition library is what makes an estimator productive.
- The decision to keep assemblies as a flat list at MVP while future-proofing the data model for nesting is a strong balance of scope vs. ambition. Most estimators' assembly needs are flat (5-15 items per condition), and nesting is a power-user feature.
- Import-as-copy for templates is the right MVP call. Linked templates add significant complexity (change propagation, conflict resolution, versioning) and most teams prefer the predictability of independent copies.
- The formula editor with autocomplete is a differentiator. PlanSwift has formulas but with poor discoverability. Making formulas approachable with autocomplete and live preview will reduce the learning curve significantly.
