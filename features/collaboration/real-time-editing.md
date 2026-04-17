# Real-Time Multi-User Editing

> **Category:** Collaboration
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Multiple estimators can work on the same project -- and the same sheet -- simultaneously in a full Figma/Google Docs-style experience. Users see each other's live cursors moving across the plan in real time, and measurements appear on everyone's screen as they're completed. Individual measurements are locked when selected for editing, preventing conflicts while keeping the experience fluid. The system supports 2-5 simultaneous users per sheet and requires an active internet connection (online only at MVP).

## User Stories

- As an estimator, I want to work on the same sheet as my colleague at the same time so that we can divide a complex floor plan and finish the takeoff faster.
- As an estimator, I want to see my colleague's cursor moving on the plan with their name label so that I know where they're working and can avoid duplicating effort.
- As an estimator, I want to see a measurement appear on the plan as soon as my colleague completes it so that I have an accurate picture of what's been done.
- As an estimator, I want a measurement to be locked when someone else selects it so that we don't accidentally overwrite each other's edits.
- As an estimator, I want to see a visual indicator (e.g., "Being edited by Sarah") on a locked measurement so that I know who's working on it and can coordinate.
- As an estimator, I want to see an avatar bar showing who's online in the project and which sheet they're on so that I know who's available.
- As a project manager, I want to see at a glance how work is distributed across my team in real-time so that I can identify bottlenecks or idle capacity.

## Key Requirements

### Simultaneous Same-Sheet Editing
- Multiple users (2-5) can be on the same sheet at the same time
- Each user has their own independent viewport (zoom, pan) -- they don't have to be looking at the same area
- New measurements created by any user appear on all users' screens immediately upon completion
- Deleted measurements disappear from all users' screens immediately
- Condition changes (reassignment, property edits) propagate to all users in real-time
- Quantities panel updates in real-time as any user adds, edits, or removes measurements

### Presence & Live Cursors
- **Avatar bar** at the top of the workspace showing all online users in the project
  - Each user gets a distinct color assignment (persists for the session)
  - Shows which sheet each user is currently viewing
  - Clicking an avatar could show more detail (name, role, active sheet)
- **Live cursors** on the plan canvas (when on the same sheet)
  - Each user's cursor appears as a colored arrow with their name label
  - Cursor positions broadcast at ~10-20 updates/second, throttled to balance smoothness and bandwidth
  - Client-side interpolation for smooth cursor movement between updates
  - Cursors use plan-space coordinates (independent of each user's zoom/pan level)
  - Cursors fade out or disappear when a user is idle for a configurable period

### Conflict Resolution: Lock on Select
- When a user **selects** a measurement (clicks on it to enter edit mode), that measurement becomes **locked** for all other users
- Other users see a visual indicator on the locked measurement:
  - Colored outline matching the locking user's presence color
  - Label or tooltip: "Being edited by Sarah"
  - The measurement cannot be selected, edited, moved, or deleted by others while locked
- The lock releases automatically when the user:
  - Deselects the measurement (clicks elsewhere)
  - Switches to a different tool
  - Leaves the sheet or goes offline
  - Is idle on the selection for a timeout period (e.g., 2 minutes)
- Lock state is broadcast via the same presence channel as cursors (lightweight)
- **Creating** new measurements never conflicts -- two users can draw simultaneously since they're creating new objects, not editing existing ones

### Online-Only Requirement
- Active internet connection required to use the product at MVP
- Graceful handling of temporary disconnections:
  - Brief disconnection (< 30 seconds): queue local changes and sync on reconnect
  - Extended disconnection: show a "Connection lost" banner, disable editing, preserve current state
  - On reconnect: sync queued changes and pull any changes made by others during the disconnection
- No offline editing capability at MVP

### Real-Time Data Sync
- All takeoff data (measurements, conditions, quantities) syncs in real-time across all connected clients
- Changes are optimistic (appear locally immediately) and reconciled with the server
- The quantities panel subtotals and aggregations update live as any user makes changes
- Condition property changes (color, formula, etc.) propagate immediately to all users

## Nice-to-Have

- **Follow mode**: click a user's avatar to follow their viewport (see exactly what they see -- useful for training or review) -- planned for post-MVP
- **Active tool indicator**: show what tool/condition each user is using next to their cursor label
- **In-progress drawing preview**: see another user's measurement as they draw it (before completion), not just after
- **User presence history**: see who was working on the project and when (last 24 hours, etc.)
- **Audio/video call integration**: built-in voice chat or integration with Zoom/Teams for talking while collaborating
- **Cursor chat**: quick text bubble attached to your cursor for micro-communications without opening the comments feature
- **10+ simultaneous users**: scale beyond 5 per sheet for large teams

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | No real-time collaboration. Desktop-only single-user application. Teams share project files via network drives or email. No simultaneous editing. |
| Bluebeam | "Bluebeam Studio" offers real-time collaboration on PDF markups. Multiple users can annotate simultaneously. Closest competitor for collaboration, but focused on PDF markup, not takeoff-specific workflows. No live cursors. |
| On-Screen Takeoff | No real-time collaboration. Desktop-only. Teams coordinate by assigning different plan pages to different estimators manually. Project files stored on shared drives. |
| Togal.AI | Web-based but no real-time multi-user editing. Single-user workflow where AI does the takeoff and the user reviews. No live collaboration features. |

## Open Questions

- [ ] Which real-time sync framework should we use? (Yjs, Liveblocks, PartyKit, custom WebSocket implementation?)
- [ ] How do we handle the edge case where a user's browser crashes while they have a measurement locked? (Server-side timeout to release stale locks?)
- [ ] Should cursor positions be sent via the same WebSocket connection as data changes, or a separate lightweight channel?
- [ ] What's the latency target for measurement sync? (< 100ms? < 500ms?)
- [ ] How do we handle simultaneous condition property edits? (e.g., two users both try to rename the same condition)
- [ ] Should the system degrade gracefully at > 5 users per sheet, or hard-block the 6th user?

## Technical Considerations

- **Real-time sync framework**: Yjs (open-source CRDT) or Liveblocks (managed service) are the leading options. Both handle conflict resolution, presence, and cursor syncing. Yjs is free but requires self-hosting the sync server. Liveblocks is a paid service but significantly reduces development effort.
- **WebSocket infrastructure**: persistent connections for all active users. Need a WebSocket server (or managed service) that can handle the connection load and fan-out messages to all users in a room.
- **Cursor coordinate system**: all cursor positions must be in plan-space coordinates (not screen pixels) so they render correctly regardless of each user's zoom/pan state. This requires transform math: screen coords -> plan coords on send, plan coords -> screen coords on receive.
- **Lock state**: lightweight presence metadata attached to each user's connection. When a user selects a measurement, their presence state updates to include `{ lockedMeasurementId: "abc123" }`. All other clients read this and apply the lock UI. Server-side timeout releases stale locks.
- **Optimistic updates**: local changes apply immediately to the UI, then sync to the server. If the server rejects a change (e.g., measurement was locked by someone else between the click and the server roundtrip), the local change is rolled back with a notification.
- **Bandwidth considerations**: with 5 users on a sheet, each sending cursor updates at 15Hz, that's 75 messages/second. Each message is tiny (~50 bytes: userId + x + y), so bandwidth is negligible, but the WebSocket server needs to handle the fan-out efficiently.
- **Reconnection logic**: the client should maintain a reconnection backoff strategy (1s, 2s, 4s, 8s...) and queue local changes during disconnection. On reconnect, replay queued changes and pull the latest state.

## Notes

- Real-time collaboration is Contruo's **single biggest differentiator** against the entrenched desktop competitors (PlanSwift, OST). None of them offer anything close to this. Bluebeam Studio is the nearest comparison, but it's collaboration on PDF markup, not on structured takeoff data with quantities and assemblies.
- The decision to go with full same-sheet editing (rather than sheet-level locking) is ambitious but right. The construction industry is moving to cloud-based workflows and teams expect modern collaboration. Being the "Figma of construction takeoff" is a powerful market position.
- Lock-on-select is the perfect middle ground for conflict resolution. It's simple to implement (just presence metadata), intuitive for users (they understand "someone else is editing this"), and avoids the data-loss risks of last-write-wins.
- Starting with 2-5 users per sheet is pragmatic. In practice, most construction estimating teams have 2-4 people working on a project simultaneously. Supporting more than 5 is a scaling concern that can be addressed based on real usage data post-launch.
- The online-only requirement at MVP is the right call. Offline editing with sync adds enormous complexity (full CRDT-based local-first architecture) and the target users are typically working in offices with reliable internet. Offline support can be evaluated based on user demand.
