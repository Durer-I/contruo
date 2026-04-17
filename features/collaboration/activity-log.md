# Activity Log & Version History

> **Category:** Collaboration
> **Priority:** P1 - Post-Launch
> **Status:** Light Brainstorm (groundwork to be built in MVP architecture)

## Overview

Track all changes made to takeoffs, plans, and project settings with full attribution -- who made the change, when, and what was modified. At launch, this is a **view-only audit trail** (no rollback capability). The data model and event logging infrastructure should be built into the MVP so that every change is captured from day one, even though the UI for browsing the log ships post-launch. The architecture is designed to support **full state rollback** in a future release.

## User Stories

- As a project manager, I want to see a chronological log of all changes to a project so that I can understand what was done, by whom, and when.
- As an estimator, I want to see who last edited a specific measurement and what they changed so that I can understand why a number looks different from what I remember.
- As an admin, I want an audit trail of all user actions for accountability so that I can investigate if something goes wrong with a takeoff.
- As a team lead, I want to review today's activity across my team so that I can track progress without interrupting people.

## Key Requirements

### Event Logging (MVP Groundwork)
Even though the activity log UI ships post-launch, the backend should capture all change events from day one:

| Event Type | Data Captured |
|------------|---------------|
| Measurement created | User, timestamp, measurement ID, condition, sheet, initial value |
| Measurement edited | User, timestamp, measurement ID, what changed (vertices, override value, condition reassignment), old value, new value |
| Measurement deleted | User, timestamp, measurement ID, condition, final value |
| Condition created/edited/deleted | User, timestamp, condition ID, what changed |
| Assembly item added/edited/deleted | User, timestamp, assembly item ID, what changed |
| Plan uploaded/replaced | User, timestamp, plan file info, sheet count |
| Project settings changed | User, timestamp, setting name, old value, new value |
| User joined/left project | User, timestamp |
| Role changed | Acting user, target user, old role, new role, timestamp |

### Activity Log UI (Post-Launch)
- Chronological feed of all events, newest first
- Filterable by: user, event type, date range, sheet
- Each event shows: user avatar/name, action description, timestamp, and a link to the affected object
- Clicking an event navigates to the relevant measurement/sheet/setting
- Grouped by day for readability

### Per-Measurement History
- On any measurement, view its change history: created by, every edit with before/after, who and when
- Accessible from the measurement's context menu or properties panel

### View-Only (No Rollback at MVP)
- The activity log is read-only -- users can browse history but cannot undo or restore previous states
- No "revert to this point" functionality at launch
- The event log data structure supports future rollback by storing before/after snapshots for each change

## Nice-to-Have

- **Full state rollback**: click any point in history to restore the project to that exact state (future release, architecture ready)
- **Selective undo**: undo a specific change without reverting everything after it
- **Diff view**: visual comparison showing what changed between two points in time (measurements added/removed/modified)
- **Activity summary emails**: daily/weekly digest email of project activity
- **Export activity log**: download the audit trail as CSV/PDF for compliance or record-keeping
- **Real-time activity feed**: see changes as they happen in a live sidebar (useful during active collaboration sessions)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | No activity log or version history. Changes are permanent with no audit trail. Standard undo/redo only for the current session. |
| Bluebeam | Basic markup history in Studio sessions. Can review who added which markups. No full project version history or rollback. |
| On-Screen Takeoff | No activity log or version history. Session-level undo/redo only. |
| Togal.AI | Minimal change tracking. Focused on AI output versioning, not user activity logging. |

## Open Questions

- [ ] How long should event history be retained? (Indefinitely? 1 year? Based on subscription tier?)
- [ ] Should the event log be stored in the same database as the application data, or in a separate analytics/audit store?
- [ ] What granularity of vertex-level changes should be captured? (Every vertex move, or just the final state after an edit session?)
- [ ] Should the activity log be accessible to all roles or restricted to Admin/Owner?

## Technical Considerations

- **MVP Groundwork is critical**: implement an event/audit logging service from day one that captures all change events to a durable store. Even without the UI, this data is invaluable for debugging, customer support, and the future activity log feature.
- **Event sourcing consideration**: if the architecture uses event sourcing (storing every change as an immutable event), rollback becomes a natural capability -- replay events up to a point in time. This is the strongest foundation for future rollback but adds complexity to the MVP data layer.
- **Alternatively, snapshot-based**: store before/after snapshots with each change event. Simpler than full event sourcing but still enables future rollback by restoring a snapshot.
- **Storage volume**: in a busy project, hundreds of events per day is typical. Over months, this accumulates. Consider a separate table or store optimized for append-heavy, read-occasionally patterns (time-series DB, or partitioned table by date).
- **Real-time collaboration interaction**: in a multi-user session, every user's actions generate events. The logging system must handle the write throughput without impacting the real-time sync performance. Async/queued event writes are recommended.
- The event schema should include a `session_id` or `batch_id` field to group related changes (e.g., all vertex moves during a single edit session are one logical change, not 15 separate events).

## Notes

- Capturing events from day one -- even without a UI -- is a strategic decision that pays dividends. When the activity log UI ships, it will have full history going back to the project's creation. If event logging is deferred, you lose all that history.
- The view-only approach at launch is pragmatic. Full rollback requires careful handling of cascading effects (e.g., rolling back a condition deletion would need to restore all measurements and assembly items linked to it). Building the logging infrastructure now and the rollback logic later is the right sequencing.
- This feature is a strong selling point for larger organizations that need accountability and compliance. Construction projects are litigious, and having a clear audit trail of who estimated what, when, and what changed can be valuable in disputes.
- The audit log doubles as a powerful debugging tool during development and customer support -- being able to replay what a user did leading up to a bug report is invaluable.
