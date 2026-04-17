# Sprint 13: Real-Time Collaboration

> **Phase:** 5 - Collaboration & Billing
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 08 (measurement tools working)

## Sprint Goal

Integrate Liveblocks for real-time collaboration. At the end of this sprint, multiple users can work on the same project and sheet simultaneously, see each other's live cursors, and measurements sync instantly. Lock-on-select prevents editing conflicts.

---

## Tasks

### 1. Liveblocks Setup
- [ ] Create Liveblocks account and configure project
- [ ] Install Liveblocks React SDK (`@liveblocks/react`, `@liveblocks/client`)
- [ ] Create Liveblocks auth endpoint: `POST /api/v1/liveblocks/auth`
  - Validate Supabase JWT
  - Return Liveblocks token scoped to the correct room with user identity
- [ ] Configure room structure: `contruo:{org_id}:{project_id}`
- [ ] Set up Liveblocks provider in the Next.js app (wrapping the project workspace)

### 2. Presence & Avatar Bar
- [ ] Implement presence broadcasting: user ID, name, avatar, active sheet, cursor position
- [ ] Avatar bar in the top bar: show all online users in the project
- [ ] Each user gets a distinct color (assigned on join, persists for session)
- [ ] Show which sheet each user is viewing (tooltip or label)
- [ ] Handle user join/leave: avatars appear/disappear smoothly

### 3. Live Cursors
- [ ] Broadcast cursor position on mouse move (throttled to ~15Hz)
- [ ] Transform cursor coordinates to plan-space (independent of zoom/pan)
- [ ] Render other users' cursors as colored arrows with name labels
- [ ] Client-side interpolation for smooth cursor movement
- [ ] Cursors only visible when users are on the same sheet
- [ ] Cursors fade out after idle timeout (e.g., 5 seconds of no movement)

### 4. Measurement Sync
- [ ] When a user creates a measurement, broadcast to all clients via Liveblocks
- [ ] Other clients render the new measurement immediately
- [ ] When a user edits a measurement (vertex move, override, condition reassign), broadcast the change
- [ ] When a user deletes a measurement, broadcast the deletion
- [ ] Quantities panel updates in real-time for all users
- [ ] Ensure database persistence and Liveblocks broadcast happen together

### 5. Lock-on-Select
- [ ] When a user selects a measurement, broadcast lock state: `{lockedMeasurementId, lockedBy}`
- [ ] Other clients see a visual indicator on locked measurements:
  - Colored outline matching the locking user's color
  - Tooltip: "Being edited by Sarah"
- [ ] Locked measurements cannot be selected, edited, or deleted by others
- [ ] Lock releases when user deselects, switches tools, or leaves
- [ ] Server-side timeout: release stale locks after 2 minutes of inactivity

### 6. Condition Sync
- [ ] When a user creates, edits, or deletes a condition, broadcast to all clients
- [ ] Condition style changes update all rendered measurements in real-time for all users
- [ ] Condition property changes trigger assembly recalculation for all users

### 7. Connection Handling
- [ ] "Connected" / "Reconnecting" / "Disconnected" status indicator
- [ ] Brief disconnection (< 30s): queue local changes, sync on reconnect
- [ ] Extended disconnection: show "Connection lost" banner, disable editing
- [ ] On reconnect: sync queued changes, pull latest state

### 8. Comments & Activity Log Groundwork
- [ ] Add comment-related fields to the database schema (tables, foreign keys) -- no UI yet
- [ ] Ensure all measurement/condition changes are logged to `event_log` table
- [ ] These are data-layer preparations for post-MVP features

---

## Acceptance Criteria

- [ ] Two users can open the same project and see each other's avatar in the top bar
- [ ] Live cursors appear on the plan when two users are on the same sheet
- [ ] Cursors move smoothly with name labels and distinct colors
- [ ] When one user creates a measurement, it appears on the other user's screen within 1 second
- [ ] When one user selects a measurement, others see "Being edited by [name]" and cannot select it
- [ ] Lock releases when the editing user deselects or leaves
- [ ] Condition changes sync in real-time to all connected users
- [ ] Quantities panel updates in real-time for all users
- [ ] Disconnection and reconnection are handled gracefully

---

## Key References

- [Real-Time Editing Feature](../features/collaboration/real-time-editing.md)
- [Comments & Markup Feature](../features/collaboration/comments-and-markup.md) -- groundwork only
- [Activity Log Feature](../features/collaboration/activity-log.md) -- groundwork only
- [Backend Architecture - Liveblocks Integration](../docs/architecture/backend.md)
