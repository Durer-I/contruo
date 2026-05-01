# Sprint AI-05: AI Layer UX

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint AI-04

## Sprint Goal

Build the AI Layer user experience -- the dedicated visual layer where AI-generated suggestions live until the estimator accepts, edits, or rejects them. After this sprint, the AI Layer infrastructure is fully working end-to-end with seed data, so when AI-06/07/08 ship real detections in subsequent sprints, the user-facing surface is already polished.

This sprint is heavy on frontend work but unlocks the critical "feel" of AI Auto-Takeoff: trustworthy, reviewable, and never destructive.

---

## Tasks

### 1. AI Layer Read API

- [ ] `GET /api/v1/projects/{project_id}/ai/layer-items?sheet_id=&status=&condition_id=`
  - Returns paginated `ai_layer_items` rows with their geometry, confidence, source stage, and resolved condition
  - Include lightweight `condition` join (name, color, measurement_type, unit) so the frontend can render without an extra request
- [ ] Aggregations: `GET /api/v1/projects/{project_id}/ai/layer-items/aggregates?ai_run_id=`
  - Returns per-sheet, per-condition, and per-confidence-tier counts (used by the run summary panel and per-sheet sidebar badges)

### 2. AI Layer Item Mutations

- [ ] `POST /api/v1/projects/{project_id}/ai/layer-items/{item_id}/accept`
  - Creates a real `Measurement` row from the AI Layer item (geometry, condition, sheet, etc.)
  - Sets `measurement.source = 'ai'`, `measurement.ai_run_id = item.ai_run_id`
  - Updates AI Layer item status to `accepted_user`
  - Logs to `event_log` with `actor=user`, `source=ai`
- [ ] `POST /api/v1/projects/{project_id}/ai/layer-items/{item_id}/reject`
  - Sets status to `rejected` (data preserved for re-run dedup and future retraining)
- [ ] `POST /api/v1/projects/{project_id}/ai/layer-items/{item_id}/edit`
  - Body: updated geometry. Triggers a server-side recompute of `measured_value` using the existing measurement service.
  - On save, status flips to `accepted_user` and a real measurement is created (same as accept)
- [ ] Bulk operations:
  - `POST /.../layer-items/bulk-accept` (body: `{item_ids: [...]}` or `{condition_id, sheet_id, min_confidence}`)
  - `POST /.../layer-items/bulk-reject`
- [ ] Optimistic locking: each item has a `version`; bulk operations are idempotent

### 3. Confidence-Tiered Auto-Accept

- [ ] During Stage 6 (write to AI Layer), high-confidence items are auto-accepted on insert:
  - `confidence >= auto_accept_threshold` (default 0.9 from project settings) -> insert AI Layer item with `status = 'accepted_auto'` AND insert real measurement in same transaction
  - `hide_threshold <= confidence < auto_accept_threshold` -> insert with `status = 'pending'`
  - `confidence < hide_threshold` -> insert with `status = 'pending'` BUT marked `hidden = true` (separate boolean column added in this sprint)
- [ ] Project settings: per-project thresholds (default 0.9 / 0.6) stored in a new JSONB column `projects.ai_settings`
- [ ] Settings UI: simple sliders in the project settings page for `auto_accept_threshold` and `hide_threshold`

### 4. AI Layer Canvas Rendering

- [ ] In `frontend/components/plan-viewer/`:
  - New `ai-layer-overlay.tsx` component renders pending AI Layer items at 50% opacity in the condition's color
  - Auto-accepted items render as normal measurements (with a small AI badge in the quantities panel)
  - Hidden (low-confidence) items don't render unless the user toggles "Show low-confidence items"
- [ ] Per-sheet on-demand rendering: only fetch `ai_layer_items` for the currently-viewed sheet; aggregate counts pre-fetched for the sheet sidebar
- [ ] Liveblocks: AI Layer item changes broadcast through the existing measurement-sync channel so collaborators see updates live

### 5. Review Panel UI

- [ ] New right-side panel `ai-review-panel.tsx`:
  - Header: "AI Review (47 pending on this sheet)"
  - Toggle: "Show low-confidence items" (default off; counts shown as `+ 23 low-confidence hidden`)
  - Grouped by Condition (collapsible groups)
  - Per-group bulk actions: "Accept all", "Reject all", "Accept above 0.8" (slider)
  - Per-item card: confidence chip, geometry preview thumbnail, action buttons (Accept / Reject / Edit / Locate)
  - Click "Locate" -> pans/zooms the canvas to the item
- [ ] Empty state: "Nothing to review on this sheet."
- [ ] Persistent across sheet navigation (panel stays open)

### 6. Run Health Summary Banner

- [ ] After a run completes, show a top-of-canvas banner summarizing the run:
  - "AI Run completed: 47 auto-accepted, 12 to review, 23 low-confidence hidden. Median confidence: 0.84."
  - "View Summary" -> opens a modal with per-stage breakdown, per-condition counts, divergence list
- [ ] If low-confidence count exceeds 30% of total detections, the banner shows a warning variant with likely causes:
  - "Calibrate scale on this sheet to improve detection accuracy"
  - "Some legends were not matched -- review the legend extraction"
  - "Many sheets were classified by vision fallback -- consider reviewing classifications"
- [ ] One-click "Show all low-confidence items" expands them in the review panel

### 7. Keyboard Shortcuts

- [ ] When the review panel is focused:
  - `A` -> accept current item
  - `R` -> reject current item
  - `E` -> edit current item (opens vertex/polygon editor)
  - `L` -> locate (pan/zoom to item)
  - `Tab` -> next item
  - `Shift+Tab` -> previous item
  - `Esc` -> close panel
- [ ] Surface shortcut hints in the panel UI
- [ ] Document in `docs/design/screen-layouts.md` keyboard reference table

### 8. Re-Run Rules Enforcement

- [ ] Re-runs replace `pending` AI Layer items for the same `(plan_id, sheet_id)` only:
  - Items with status `accepted_auto`, `accepted_user`, or `rejected` are preserved
  - New run dedups against rejected items by spatial proximity (within configurable threshold) + condition (so a previously-rejected suggestion is not re-suggested)
- [ ] Divergence detection: when a re-run produces a different geometry for a previously-accepted measurement, log it in `ai_runs.summary_jsonb.divergences` and surface in the run-summary modal -- never silently change accepted measurements
- [ ] AI lock from AI-01 prevents concurrent runs on the same plan/sheet

### 9. Provenance Filters in Quantities Panel

- [ ] Quantities panel: add a filter for "Source" with options: All, User, AI (auto-accepted), AI (user-accepted)
- [ ] Each measurement row shows a small AI badge if `source = 'ai'`; tooltip: "Created by AI Run #7" (links to run summary)
- [ ] Bulk action: "Delete all measurements from this run" (Owner/Admin only)

### 10. Sheet-Index AI Indicators

- [ ] In the sheet index left rail, each sheet shows a small AI badge with pending count: "12 to review"
- [ ] Click the badge -> navigates to that sheet and opens the review panel pre-filtered to that sheet

---

## Acceptance Criteria

- [ ] An estimator can run auto-takeoff (with seed AI Layer data) and see a clean review panel grouped by condition.
- [ ] Bulk-accept across a condition group creates real measurements in a single transaction.
- [ ] High-confidence items (>= 0.9) appear directly as real measurements without entering the review queue.
- [ ] Low-confidence items (< 0.6) are hidden by default; toggling "Show low-confidence" expands them.
- [ ] Run health banner shows accurate counts and surfaces warnings when low-confidence exceeds 30%.
- [ ] Keyboard shortcuts work in the review panel; review feels fast and Figma-like.
- [ ] Re-runs do not destroy accepted or user-edited measurements; divergences are logged not applied.
- [ ] Provenance filters and AI badges work in the quantities panel; bulk-delete by run works for admins.
- [ ] Liveblocks broadcasts AI Layer mutations so collaborators see live updates.
- [ ] All previous tests pass; new tests cover layer-item APIs, confidence-tiered insertion logic, re-run dedup, and divergence detection.

---

## Out of Scope

- Real detections (this sprint uses seed/test data; real detections come in AI-06, AI-07, AI-08)
- Review queue mode (Gmail-style linear walkthrough) -- listed as Nice-to-Have for later

---

## Key References

- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) -- AI Layer and Review UX, Re-Run Behavior, Provenance and Bulk Operations
- [backend/app/services/measurement_service.py](../../backend/app/services/measurement_service.py) -- existing measurement creation logic to reuse on accept
- [backend/app/services/event_service.py](../../backend/app/services/event_service.py) -- event_log writes for accepts/rejects
