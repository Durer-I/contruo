# Comments & Markup

> **Category:** Collaboration
> **Priority:** P1 - Post-Launch
> **Status:** Light Brainstorm (groundwork to be built in MVP architecture)

## Overview

Enable in-context comments attached directly to specific measurements on the plan. Team members can leave questions, feedback, or instructions on any takeoff measurement, with @mentions to notify colleagues and threaded conversations for organized discussions. Notifications are delivered both in-app and via email. While this feature ships post-launch, the **data model and infrastructure groundwork** should be built into the MVP architecture so comments can be added without re-engineering.

## User Stories

- As an estimator, I want to leave a comment on a specific measurement to ask my colleague a question about it so that we can resolve ambiguities without a separate phone call or email.
- As a reviewer, I want to comment on a measurement I think is incorrect so that the estimator can review and fix it.
- As an estimator, I want to @mention a colleague in a comment so that they get notified and can respond quickly.
- As a team lead, I want to see all unresolved comments on a project so that I can track open questions before submitting a bid.
- As a guest viewer, I want to leave comments on measurements so that I can provide feedback on the takeoff to the estimating team.

## Key Requirements

### Comment Anchoring
- Comments are **attached to specific measurements** (not arbitrary plan locations)
- A comment references a measurement ID -- clicking the comment highlights the measurement on the plan, and vice versa
- If a measurement is deleted, its comments are archived (not lost)
- Multiple comments can be attached to the same measurement

### Threaded Conversations
- Each comment can have replies, forming a thread
- Threads are collapsible for clean UI
- Threads can be marked as "resolved" to indicate the discussion is closed

### @Mentions & Notifications
- Type `@` followed by a name to mention a team member
- Mentioned users receive:
  - **In-app notification** via a notification bell/panel
  - **Email notification** with the comment text and a link to the measurement
- Users who are part of a thread get notified of new replies

### Comment Display
- A small comment indicator icon on measurements that have comments
- Clicking the indicator opens the comment thread in a side panel or popover
- Comment count badge on the measurement
- A project-level "Comments" panel listing all comments, filterable by resolved/unresolved

## Nice-to-Have

- Pin comments to arbitrary plan locations (not just measurements) for general notes
- Visual markup tools alongside comments (arrows, highlights, cloud markups)
- Comment assignments ("assign this to Sarah to fix")
- Comment due dates or urgency flags
- Real-time comment sync (new comments appear live for all connected users)
- File/image attachments in comments

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | No built-in comment system. Users rely on external communication (email, phone). |
| Bluebeam | Strong markup and comment tools. Comments attached to PDF annotations. Threaded replies. Bluebeam Studio enables real-time comment collaboration. Industry-leading in this area. |
| On-Screen Takeoff | No built-in comment system. External communication required. |
| Togal.AI | Limited or no comment features. Focused on AI output review, not team communication. |

## Open Questions

- [ ] Should comments be synced in real-time (like the takeoff data) or is near-real-time (polling every few seconds) acceptable?
- [ ] Should resolved comments be hidden by default or just visually dimmed?
- [ ] How should comments interact with measurement version history? (If a measurement is edited after a comment, should the comment reference the old state?)

## Technical Considerations

- **MVP Groundwork**: The data model for comments (comment table with measurement_id foreign key, author, timestamp, thread_id, resolved flag) should be included in the MVP database schema even though the UI ships later. This avoids migrations.
- **Notification infrastructure**: the email notification system (SendGrid, AWS SES, or similar) and the in-app notification model (notification table, read/unread state) should be built as part of the MVP platform, as they'll be reused by other features.
- Comments on measurements create a relationship that must be considered when deleting or reassigning measurements -- cascade rules need to be defined.
- @mention parsing requires a user lookup API that returns matching team members as the user types.

## Notes

- Bluebeam's comment and markup system is the gold standard in the construction industry. Contruo doesn't need to match its full markup toolkit, but the core comment-on-measurement workflow should feel just as natural.
- Building the data model and notification infrastructure into the MVP is critical. Adding comments post-launch should be a frontend feature addition, not a backend re-architecture.
- Guest viewers being able to comment is a key workflow: the GC's estimator shares a takeoff with a subcontractor, the sub reviews and leaves questions as comments, the estimator responds -- all within Contruo instead of scattered across emails.
