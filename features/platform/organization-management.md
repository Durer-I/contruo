# Organization Management

> **Category:** Platform & Infrastructure
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Every Contruo account belongs to an organization -- the top-level container for all projects, condition templates, team members, and billing. At MVP, the organization structure is **flat** (no departments, teams, or sub-groups). Organization settings are **minimal**: org name, logo (groundwork for future branding), and default unit system (imperial/metric). The architecture is built with extensibility in mind for future settings like template libraries and notification preferences.

## User Stories

- As an org owner, I want to set my organization name and upload a logo so that the workspace reflects my company identity.
- As an org owner, I want to set the default unit system (imperial or metric) for my organization so that all new projects use the correct measurement units.
- As an admin, I want to see a list of all team members with their roles and activity status so that I can manage my team.
- As an admin, I want to invite new team members and assign them roles so that they can access our projects.
- As an admin, I want to deactivate a team member who has left the company so that they lose access without deleting their historical work.
- As a user, I want all my organization's projects, templates, and settings to be in one shared workspace so that everyone on the team sees the same data.

## Key Requirements

### Organization as the Core Container

Everything in Contruo is scoped to an organization:

| Entity | Belongs To |
|--------|-----------|
| Projects | Organization |
| Plans / Sheets | Project -> Organization |
| Measurements / Takeoffs | Project -> Organization |
| Conditions & Assemblies | Project (with import from org template library) |
| Condition Template Library | Organization |
| Team Members | Organization |
| Billing / Subscription | Organization |
| Guest Access | Organization -> Project |

### Flat Structure (MVP)
- No departments, teams, or sub-groups within the organization
- All team members are peers within their role level (Owner, Admin, Estimator, Viewer)
- All projects are visible to all org members (no project-level access restrictions at MVP)
- Simple and easy to reason about -- suitable for teams of 2-20 people

### Organization Settings (Minimal MVP)

| Setting | Description | Default |
|---------|-------------|---------|
| **Organization Name** | Company/firm name, displayed in the workspace header | Set during signup |
| **Logo** | Company logo upload (used in future report branding and workspace header) | None (Contruo default) |
| **Default Unit System** | Imperial (feet/inches) or Metric (meters/centimeters) | Imperial |

- Settings page accessible to Owner and Admin roles only
- Logo upload accepts PNG, JPG, SVG with a reasonable size limit (e.g., 2MB)
- Unit system applies as the default for new projects -- individual projects can override if needed

### Team Member Management

This overlaps with the Roles & Permissions feature but lives within the org management UI:

- **Member list view**: name, email, role, status (active/invited/deactivated), last active date
- **Invite flow**: enter email + select role -> sends invitation email
- **Role management**: change a member's role (Owner/Admin can do this)
- **Deactivation**: deactivate a member (preserves their work history, removes access). Deactivated users don't count as seats for billing.
- **Reactivation**: reactivate a previously deactivated member (re-adds a seat to billing)
- **Guest list**: separate section showing external guests, the project(s) they can access, who invited them, and revoke access option

### Data Isolation (Multi-Tenancy)
- Each organization's data is fully isolated from other organizations
- A user cannot see, access, or query data from another organization (except via guest access to specifically shared projects)
- Database-level isolation via org_id foreign key on all data tables (row-level security)
- API endpoints always scope queries to the authenticated user's organization

### Organization Lifecycle

```
Created  ->  Active  ->  Suspended (non-payment)  ->  Reactivated (payment resumed)
                     ->  Deleted (owner request, after data export period)
```

- **Created**: org created during signup, subscription starts
- **Active**: normal operating state, all features available
- **Suspended**: payment failed beyond grace period, read-only access, data preserved
- **Reactivated**: payment resumed, full access restored
- **Deleted**: owner requests deletion, data export offered, data permanently deleted after retention period (e.g., 30 days)

## Nice-to-Have

- **Departments/Teams**: group members into departments (Estimating, Pre-Con, Management) for organizational clarity
- **Project-level access control**: restrict which members can see specific projects
- **Multiple organizations**: allow a user to belong to multiple orgs (e.g., a consultant working for several firms) with an org switcher
- **Organization branding**: custom colors, email templates, and export branding tied to the org
- **Default condition template library**: pre-configured template library that new projects auto-inherit
- **Organization-wide notification preferences**: control what triggers emails at the org level
- **Data retention policies**: configurable auto-archive or delete for old projects
- **Audit log**: track all org-level changes (members added/removed, settings changed, etc.)
- **Organization dashboard**: high-level view of all active projects, team utilization, and recent activity across the org

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | No organization concept -- desktop software with individual licenses. Shared resources via network file shares. No centralized team management. |
| Bluebeam | Bluebeam accounts with "Firms" for enterprise. Basic team management in Bluebeam Studio. Not a full organization workspace. |
| On-Screen Takeoff | No organization concept. Per-seat licenses managed by IT/admin. No shared workspace or centralized settings. |
| Togal.AI | Web-based with basic team/organization structure. Limited org management features. Simpler workspace model. |

## Open Questions

- [ ] Should there be a limit on the number of projects per organization? (Or is it unlimited?)
- [ ] How should data export work when an org owner requests deletion? (Full data dump in what format?)
- [ ] Should the logo upload support cropping/resizing in the UI, or just accept the uploaded file as-is?
- [ ] What's the data retention period after an org is deleted before permanent erasure?
- [ ] Should we support org name changes affecting the URL/slug (e.g., `app.contruo.com/acme-construction`)?

## Technical Considerations

- **Multi-tenancy via row-level security**: every table with user data has an `org_id` column. All queries are scoped by `org_id`. Consider database-level row-level security (RLS) if using PostgreSQL for an additional layer of protection beyond application logic.
- **org_id is mandatory**: no data record should ever exist without an `org_id`. This is enforced at the database level (NOT NULL constraint) and at the API level (middleware injects `org_id` from the authenticated user's session).
- **File storage isolation**: uploaded files (plans, logos) should be stored in org-scoped paths (e.g., `storage/{org_id}/plans/`, `storage/{org_id}/logo/`) to prevent cross-org access.
- **Extensible settings model**: rather than hardcoding individual setting columns, consider a `org_settings` table with key-value pairs or a JSONB column. This allows adding new settings without schema migrations. Alternatively, start with explicit columns for the three MVP settings and add a flexible settings table later.
- **Soft delete for deactivation**: deactivated members are soft-deleted (a `deactivated_at` timestamp), not removed from the database. Their measurements, comments, and activity history remain attributed to them.
- **Org deletion is a sensitive operation**: require password re-entry, send confirmation email, implement a cooling-off period (e.g., 30 days) during which deletion can be cancelled and data is preserved.

## Notes

- The flat organization structure is perfect for MVP. Construction estimating firms are typically small (3-20 people) with simple hierarchies. Adding departments and teams is a natural post-MVP enhancement when larger firms adopt the product, but it's unnecessary complexity for launch.
- Making the organization the core container for everything keeps the data model clean and the permission system simple. Every query starts with "what org does this user belong to?" and everything flows from there.
- The minimal settings (name, logo, unit system) cover the essentials without building a complex settings UI. The logo upload lays groundwork for future report branding (Custom Report Builder, P2) even though it won't be used in exports at MVP.
- Multi-tenancy security is non-negotiable. A data leak between organizations would be a company-ending event for a SaaS product handling proprietary construction bid data. Row-level security at the database level is the strongest protection.
- Supporting both imperial and metric unit systems from day one is important for international market reach, even if the initial target is primarily North American contractors.
