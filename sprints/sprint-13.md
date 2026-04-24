# Sprint 13: Real-Time Collaboration

> **Phase:** 5 - Collaboration & Billing
> **Duration:** 2 weeks
> **Status:** Partial (MVP slice shipped; see notes below)
> **Depends On:** Sprint 08 (measurement tools working)

## Sprint Goal

Integrate Liveblocks for real-time collaboration. At the end of this sprint, multiple users can work on the same project and sheet simultaneously, see each other's live cursors, and measurements sync instantly. Lock-on-select prevents editing conflicts.

### Implementation summary (April 2026)

Shipped: backend `POST /api/v1/liveblocks/auth`, room id `contruo:{org_id}:{project_id}`, `@liveblocks/react` + client, `ProjectCollaborationRoom` wrapping the plan workspace, presence (name, color, active sheet, page, cursor, lock fields), top-bar avatars + connection status, PDF-space cursors (~15 Hz throttle, same-sheet, idle fade, light smoothing), custom events for measurement and condition changes (broadcast after successful API writes + listener refetches sheet/project measurements and conditions), lock-on-select via presence with colored outline on locked measurements and blocked selection / delete / quantities pick. Viewers get `room:read` + `room:presence:write`; editors get `room:write`.

Deferred / follow-on: Liveblocks project setup remains an **ops** step (dashboard account + secret in env). No **comment schema** migration yet. **Extended offline UX** (queued edits, “connection lost” banner, disable editing) is minimal today (status pill only). Lock **tooltip** (“Being edited by …”) on canvas shapes not added (outline only). **Server-authoritative** locks beyond presence + 2 min stale client rule not implemented. Confirm **event_log** coverage for every measurement/condition mutation if not already complete elsewhere.

---

## Tasks

### 1. Liveblocks Setup
- [ ] Create Liveblocks account and configure project *(dashboard / ops — not code)*
- [x] Install Liveblocks React SDK (`@liveblocks/react`, `@liveblocks/client`)
- [x] Create Liveblocks auth endpoint: `POST /api/v1/liveblocks/auth`
  - Validate Supabase JWT
  - Return Liveblocks token scoped to the correct room with user identity
- [x] Configure room structure: `contruo:{org_id}:{project_id}`
- [x] Set up Liveblocks provider in the Next.js app (wrapping the project workspace)

### 2. Presence & Avatar Bar
- [x] Implement presence broadcasting: user ID, name, avatar, active sheet, cursor position *(avatar = initials + color; no photo URL yet)*
- [x] Avatar bar in the top bar: show all online users in the project
- [x] Each user gets a distinct color (assigned on join, persists for session)
- [x] Show which sheet each user is viewing (tooltip or label)
- [x] Handle user join/leave: avatars appear/disappear smoothly *(via Liveblocks others list)*

### 3. Live Cursors
- [x] Broadcast cursor position on mouse move (throttled to ~15Hz)
- [x] Transform cursor coordinates to plan-space (independent of zoom/pan)
- [x] Render other users' cursors as colored arrows with name labels
- [x] Client-side interpolation for smooth cursor movement *(light lerp per update)*
- [x] Cursors only visible when users are on the same sheet
- [x] Cursors fade out after idle timeout (e.g., 5 seconds of no movement)

### 4. Measurement Sync
- [x] When a user creates a measurement, broadcast to all clients via Liveblocks
- [x] Other clients render the new measurement immediately *(refetch after event; typically under 1s on LAN)*
- [x] When a user edits a measurement (vertex move, override, condition reassign), broadcast the change
- [x] When a user deletes a measurement, broadcast the deletion
- [x] Quantities panel updates in real-time for all users
- [x] Ensure database persistence and Liveblocks broadcast happen together *(API first, then broadcast)*

### 5. Lock-on-Select
- [x] When a user selects a measurement, broadcast lock state: `{lockedMeasurementId, lockedBy}` *(via presence + `lockedAt`; locker identified by color / others’ presence)*
- [x] Other clients see a visual indicator on locked measurements:
  - Colored outline matching the locking user's color
  - Tooltip: "Being edited by Sarah" *(outline done; per-shape tooltip deferred)*
- [x] Locked measurements cannot be selected, edited, or deleted by others
- [x] Lock releases when user deselects, switches tools, or leaves
- [ ] Server-side timeout: release stale locks after 2 minutes of inactivity *(client ignores stale remote locks ~2 min + presence heartbeat; no separate server lock service)*

### 6. Condition Sync
- [x] When a user creates, edits, or deletes a condition, broadcast to all clients
- [x] Condition style changes update all rendered measurements in real-time for all users
- [x] Condition property changes trigger assembly recalculation for all users *(via refetch paths on condition event)*

### 7. Connection Handling
- [x] "Connected" / "Reconnecting" / "Disconnected" status indicator *(compact pill in top bar)*
- [ ] Brief disconnection (< 30s): queue local changes, sync on reconnect
- [ ] Extended disconnection: show "Connection lost" banner, disable editing
- [ ] On reconnect: sync queued changes, pull latest state *(partial: refetch on events; no explicit offline queue UI)*

### 8. Comments & Activity Log Groundwork
- [ ] Add comment-related fields to the database schema (tables, foreign keys) -- no UI yet
- [ ] Ensure all measurement/condition changes are logged to `event_log` table *(verify / complete in a follow-on if gaps remain)*
- [ ] These are data-layer preparations for post-MVP features

---

## Acceptance Criteria

- [x] Two users can open the same project and see each other's avatar in the top bar
- [x] Live cursors appear on the plan when two users are on the same sheet
- [x] Cursors move smoothly with name labels and distinct colors
- [x] When one user creates a measurement, it appears on the other user's screen within 1 second *(after refetch; typical on good network)*
- [x] When one user selects a measurement, others see "Being edited by [name]" and cannot select it *(cannot select + lock ring; explicit name tooltip on canvas deferred)*
- [x] Lock releases when the editing user deselects or leaves
- [x] Condition changes sync in real-time to all connected users
- [x] Quantities panel updates in real-time for all users
- [ ] Disconnection and reconnection are handled gracefully *(status + refetch; full offline queue / banner deferred)*

---

## Key References

- [Real-Time Editing Feature](../features/collaboration/real-time-editing.md)
- [Comments & Markup Feature](../features/collaboration/comments-and-markup.md) -- groundwork only
- [Activity Log Feature](../features/collaboration/activity-log.md) -- groundwork only
- [Backend Architecture - Liveblocks Integration](../docs/architecture/backend.md)
