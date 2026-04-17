# Roles & Permissions

> **Category:** Collaboration
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Control access to Contruo's features through a role-based permission system. At MVP, the system uses **fixed predefined roles** (Owner, Admin, Estimator, Viewer) applied at the **organization level** -- a user has one role across the entire organization. The architecture is designed for custom roles to be added in a future release. External users can be invited as **guests** by creating a free guest account, enabling GCs and subs to share takeoffs for review without giving full access.

## User Stories

- As an organization owner, I want to assign roles to my team members so that each person has the appropriate level of access to our projects and data.
- As an admin, I want to invite new team members by email and assign them a role so that they can start working immediately.
- As an admin, I want to change a user's role if their responsibilities change so that their access stays appropriate.
- As an estimator, I want to be able to create, edit, and delete takeoffs without being able to access billing or organization settings so that I can focus on my work without accidentally changing admin settings.
- As a viewer, I want to see takeoff results and quantities without being able to edit measurements so that I can review work without risk of accidental changes.
- As a GC project manager, I want to invite a subcontractor to view a specific takeoff as a guest so that they can review quantities and provide feedback without accessing our other projects.
- As a guest, I want to create a free account and view the shared takeoff so that I can review the work and leave feedback.

## Key Requirements

### Predefined Roles (MVP)

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| **Owner** | Organization creator. Full unrestricted access. Cannot be removed. | Everything. Manage billing, delete org, transfer ownership. |
| **Admin** | Organization administrator. Manages team and settings. | Invite/remove users, assign roles, create/archive projects, manage org settings, manage condition template library. Cannot delete the org or access billing (Owner only). |
| **Estimator** | Core working role. Creates and manages takeoffs. | Create/edit/delete measurements, manage conditions and assemblies, import templates, export data, view all projects they're assigned to. Cannot manage users or org settings. |
| **Viewer** | Read-only access for review and oversight. | View plans, measurements, quantities, and reports. Cannot create, edit, or delete any takeoff data. Can participate in comments (when Comments & Markup is added). |

### Permission Matrix

| Action | Owner | Admin | Estimator | Viewer | Guest |
|--------|-------|-------|-----------|--------|-------|
| View plans & measurements | Yes | Yes | Yes | Yes | Yes (shared only) |
| Create/edit/delete measurements | Yes | Yes | Yes | No | No |
| Manage conditions & assemblies | Yes | Yes | Yes | No | No |
| Import condition templates | Yes | Yes | Yes | No | No |
| Export data (PDF/Excel) | Yes | Yes | Yes | Yes | No |
| Create/archive projects | Yes | Yes | No | No | No |
| Upload/manage plan sets | Yes | Yes | Yes | No | No |
| Invite team members | Yes | Yes | No | No | No |
| Assign/change roles | Yes | Yes | No | No | No |
| Remove team members | Yes | Yes | No | No | No |
| Manage org settings | Yes | Yes | No | No | No |
| Manage condition template library | Yes | Yes | No | No | No |
| Manage billing & subscription | Yes | No | No | No | No |
| Delete organization | Yes | No | No | No | No |
| Transfer ownership | Yes | No | No | No | No |

### Organization-Level Assignment
- Each user has **one role** across the entire organization
- Role applies uniformly to all projects within the org
- Simple to manage and reason about -- no per-project permission confusion
- Future enhancement: per-project role overrides (e.g., an Estimator on most projects but Viewer on a sensitive one)

### Guest Access
- An org member (Admin or Owner) can invite an external user by email to view a specific project
- The external user receives an email invitation with a link
- They must create a **free Contruo guest account** (name, email, password) to access the shared content
- Guests can only see the specific project(s) they've been invited to
- Guests have **Viewer-level** permissions on the shared project (view-only, no editing)
- Guests do not count toward the org's seat/user limit for billing purposes
- The inviting org can revoke guest access at any time
- Guest accounts are real Contruo accounts -- if a guest later wants to start their own workspace, they upgrade to a paid plan (growth funnel)

### User Management UI
- Team member list showing: name, email, role, last active date, status (active/invited/deactivated)
- Invite flow: enter email + select role -> sends invitation email -> pending until accepted
- Change role: dropdown to switch a user's role (Owner can change anyone, Admin can change Estimator/Viewer)
- Remove user: deactivate (preserve their work history) or remove from org
- Guest list: separate section showing external guests, which projects they can access, and who invited them

## Nice-to-Have

- **Custom roles**: admins define their own roles with custom permission combinations (planned for future release)
- **Per-project role overrides**: assign a different role to a user for a specific project
- **Reviewer role**: a role between Estimator and Viewer -- can add comments and approve/reject measurements but not create new ones
- **Role-based feature access**: tie certain features to subscription tiers (e.g., guest access only on Pro plan)
- **SSO role mapping**: automatically assign roles based on SSO group membership (e.g., "Estimators" group in Azure AD -> Estimator role in Contruo)
- **Bulk invite**: upload a CSV of emails and roles to onboard a large team
- **Access audit log**: track who was granted/revoked what access and when
- **Two-factor authentication**: add 2FA requirement for Admin and Owner roles

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Desktop software with per-seat licensing. No role system -- whoever has the license has full access. No collaboration means no permission model needed. |
| Bluebeam | Bluebeam Studio has basic permission levels for collaboration sessions (host, contributor, viewer). Not a full organizational role system. |
| On-Screen Takeoff | Per-seat desktop licensing. No role-based access control. File-level access controlled by the OS/network permissions. |
| Togal.AI | Web-based with basic team management. Limited role system. No guest access model. |

## Open Questions

- [ ] Should deactivated users' measurements remain attributed to them, or be reassigned to another user?
- [ ] What happens to a guest's account if access to all shared projects is revoked? (Account persists but has no content?)
- [ ] Should there be a limit on the number of guests per project or per organization?
- [ ] How should permissions interact with the real-time collaboration locks? (Can a Viewer see lock indicators from Estimators?)
- [ ] Should the Owner role be transferable? If the owner leaves the company, how is ownership transferred?

## Technical Considerations

- Role and permission checks must happen **both client-side** (to hide/disable UI elements) and **server-side** (to enforce access control on API requests). Never trust the client alone.
- The permission model should be implemented as a centralized permission-checking service/middleware that all API endpoints use -- not scattered permission checks throughout the codebase.
- Guest accounts share the same user table as regular accounts, with a `type` field distinguishing them. Guest-to-project access is a many-to-many relationship table.
- The data model should support future custom roles: store permissions as a set of permission flags on the role, not as hardcoded role-name checks. Even though MVP has fixed roles, the underlying model should be `role -> [permissions]` so adding custom roles later is a schema extension, not a rewrite.
- For the real-time collaboration system, permission checks need to happen at the WebSocket connection level (can this user join this room?) and on each operation (can this user create/edit/delete in this room?).

## Notes

- The fixed-role model at MVP covers the needs of 95%+ of construction estimating teams. Most teams are small (3-10 people) with clear role divisions: a manager/admin, several estimators, and occasional external reviewers.
- Guest access via free accounts is a deliberate growth strategy. Every guest who creates an account is a potential future paying customer. This is the same playbook that made Figma, Slack, and Notion grow virally within organizations.
- Organization-level roles (rather than per-project) keep the mental model simple for MVP. Estimators in construction firms typically work across all the firm's projects, so per-project permissions add complexity without solving a common problem.
- The permission matrix is intentionally conservative for MVP. It's always easier to grant more permissions later than to take them away.
