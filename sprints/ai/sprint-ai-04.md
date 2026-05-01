# Sprint AI-04: Condition Resolver (Match -> Template -> Create)

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint AI-03

## Sprint Goal

Implement the Condition Resolver that turns extracted schedule rows and legend entries into actual Contruo `Conditions` -- reusing the firm's existing project conditions where possible, cloning org `ConditionTemplates` (with their assembly items) when there's a close match, and creating raw conditions only as a last resort. After this sprint, an estimator who runs auto-takeoff sees their existing conditions and templates fully utilized by the AI; new auto-created conditions follow the firm's unit system and naming conventions and arrive partially populated with assembly items where possible.

This is the architectural feature that turns Contruo's auto-takeoff from a "demo toy" into "an extension of our team's workflow."

---

## Tasks

### 1. Embedding Service Integration

- [ ] Implement `OpenAIEmbeddingModel` in `backend/app/services/ai_models.py` (interface from AI-01) using `text-embedding-3-small`
- [ ] Helpers in `backend/app/services/ai_embedding_cache.py`:
  - `embed_condition(condition)` -> 1536-dim vector
  - `embed_template(template)` -> 1536-dim vector
  - Batch helper: `embed_batch(texts)` for first-time backfill
- [ ] Postgres storage: add `embedding` column (`pgvector` type) on `conditions` and `condition_templates` tables
  - Migration: enable `pgvector` extension if not already enabled
  - Index: HNSW or IVFFlat on the embedding column for fast similarity queries
- [ ] Backfill task: one-time Celery job to embed all existing conditions and templates per org
- [ ] Triggers / hooks: re-embed on `Condition` or `ConditionTemplate` create/update (conditional on name or description change)

### 2. Match Stage (Existing Project Conditions)

- [ ] In `backend/app/services/ai_condition_resolver.py`:
  - `match_existing(detected_element, project_id, org_id)` returns top candidates by:
    - Cosine similarity on name embedding (threshold 0.85)
    - Exact match on `measurement_type`
    - Unit normalization (e.g., `SF` ≡ `SQ FT` ≡ `Sq Ft`)
  - Tie-breaker: prefer conditions already used on the current sheet, then conditions with most existing measurements project-wide
- [ ] Returns `Optional[ResolverMatch]` with `(condition_id, score, method='match_existing')`

### 3. Template Stage (Clone From Org Template Library)

- [ ] If no project match -> `match_template(detected_element, org_id)`:
  - Same fuzzy match against `condition_templates` with threshold 0.80
- [ ] If matched -> `clone_template_to_project(template, project_id, ai_run_id)`:
  - Insert new `Condition` row copying all template fields
  - Set `source = 'template_clone'`, `source_template_id = template.id`, `source_ai_run_id = ai_run_id`
  - Insert child `AssemblyItem` rows from the template's `assembly_items` JSONB
  - Embed the new condition (asynchronously) for future matches in this run
- [ ] Returns `ResolverMatch` with the cloned condition id and `method='template_clone'`

### 4. Create Stage (Raw Condition From Schedule/Legend)

- [ ] If no project or template match -> `create_raw_condition(detected_element, project, ai_run_id)`:
  - **Name:** call `LLMModel.summarize` with the schedule description (or legend label) to produce a short consistent name (e.g., "6'-0" Single Door"). Cache by description hash.
  - **Description:** preserve full schedule description / legend label
  - **Measurement type:** from element type (wall -> linear, room/hatch -> area, symbol/balloon -> count)
  - **Unit:** project's unit system (imperial -> SF/LF/EA; metric -> m2/m/EA)
  - **Styling:** preset color from a palette per measurement_type, default `line_width = 2.0`, `fill_opacity = 0.3`, `fill_pattern = solid`
  - **Source tagging:** `source = 'ai_created'`, `source_ai_run_id = ai_run_id`
- [ ] Returns `ResolverMatch` with the new condition id and `method='create_raw'`

### 5. Assembly Item Suggestions for Raw Conditions

- [ ] Element-type starter assemblies in a constants file (`backend/app/services/ai_assembly_starters.py`):
  - Linear conditions: placeholder `material` and `labor` items with `unit = condition.unit` and empty cost
  - Area conditions: same structure
  - Count conditions: `material` and `install_labor` items
- [ ] Description-driven suggestions: built-in dictionary mapping common materials (`carpet`, `VCT`, `epoxy`, `drywall`, `paint`, `tile`) to relevant assembly items
- [ ] Optional LLM enrichment: call `LLMModel.structured_output` with the description and ask for 2-4 typical assembly items (capped per run for cost control)
- [ ] All suggested assembly items tagged `source = 'ai_suggested'` in the existing `assembly_items.source` column (add this column in this sprint)

### 6. AssemblyItem Provenance Migration

- [ ] Migration: add `source` column to `assembly_items` (default `'user'`, values `'user'` | `'template_clone'` | `'ai_suggested'`)
- [ ] Update existing template-clone code path (Sprint 07/10) to mark cloned items with `source = 'template_clone'` -- minor backfill considered

### 7. Resolver as a Pure Function (Testable)

- [ ] `resolve_condition(detected_element_metadata, project_conditions, org_templates, project_units, ai_run_id)` returns `(condition_id, source, suggested_items)`
- [ ] Wired into the AI pipeline at Stage 6 (called per `ai_layer_items` write)
- [ ] Unit tests cover all three paths (match, template, create) plus edge cases (empty templates, no project conditions, multiple equally-good matches)

### 8. "Save to Library?" Nudge UI

- [ ] When a condition has `source = 'ai_created'` and the user opens the condition manager panel, show a small inline prompt: "This condition was created by AI. Save to your team library?"
- [ ] Click "Save" -> creates a `ConditionTemplate` from the condition (with current assembly items) at org level. Updates `condition.source = 'imported'` and clears the prompt.
- [ ] Click "Dismiss" -> hides for that condition (per-user preference stored locally; condition remains `ai_created`)
- [ ] Subtle UX: nudge appears only on first view per condition per user; not a blocking modal

### 9. Condition Source Filters in UI

- [ ] Condition manager panel: add a filter for "Source" (User / Template / AI)
- [ ] Each condition card displays a small badge for its source (User: hidden / Template: tag icon / AI: sparkle icon)
- [ ] Quantities panel measurement rows already get the AI badge from Sprint AI-01 column changes; verify it renders correctly post-resolver

### 10. Run Summary Updates

- [ ] After resolver runs across the AI Layer items for the run:
  - `ai_runs.summary_jsonb.conditions_resolved` includes `{matched_existing, template_cloned, ai_created}` counts
  - "Run Summary" UI: "AI created 4 new conditions, cloned 7 from your template library, reused 12 existing conditions."

---

## Acceptance Criteria

- [ ] An estimator with an existing "Interior Wall - 8' Drywall" project condition runs auto-takeoff, and AI-detected interior walls are mapped to that existing condition (no new condition created).
- [ ] An estimator with a "Carpet - VCT Tile" org template (no matching project condition yet) runs auto-takeoff on a sheet with a VCT hatch -> a new project condition is created from the template, including its assembly items.
- [ ] On a project with no matching project conditions or templates, AI creates raw conditions with sensible names and unit-system-appropriate units.
- [ ] All AI-created conditions show the "Save to library?" nudge on first view; clicking "Save" creates an org template; "Dismiss" hides it.
- [ ] The condition manager filters by source correctly.
- [ ] Re-running auto-takeoff after a user has manually edited an AI-created condition does not overwrite the manual edits.
- [ ] Embedding cache works: re-running with no template changes incurs zero embedding API calls.
- [ ] Cost telemetry: condition resolver costs are dominated by embedding calls (cheap) and occasional LLM-summarize calls; both should be heavily cached.
- [ ] All previous tests pass; new tests cover the three resolver paths, the embedding cache, the assembly suggestion logic, and the nudge state machine.

---

## Out of Scope

- AI Layer overlays / review panel UI -> AI-05
- Symbol / wall / room / hatch detection -> AI-06, AI-07, AI-08
- Cost values for AI-suggested assembly items (depends on AI Cost Estimation feature, P2)

---

## Key References

- [features/ai/ai-quantity-suggestions.md](../../features/ai/ai-quantity-suggestions.md) -- Match -> Template -> Create resolver, embedding cache, "Save to library?" nudge
- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) -- Stage 6 (Condition Resolution and AI Layer Write)
- [backend/app/models/condition.py](../../backend/app/models/condition.py) -- existing condition schema
- [backend/app/models/condition_template.py](../../backend/app/models/condition_template.py) -- existing template schema
- [backend/app/models/assembly_item.py](../../backend/app/models/assembly_item.py) -- existing assembly item schema (where new `source` column lands)
