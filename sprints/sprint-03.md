# Sprint 03: Organization Management

> **Phase:** 1 - Foundation
> **Duration:** 2 weeks
> **Status:** Complete
> **Depends On:** Sprint 02

## Sprint Goal

Build the organization management system -- settings, team invitations, role management, and guest access. At the end of this sprint, admins can manage org settings, invite team members by email, assign roles, and invite external guests to view projects.

---

## Tasks

### 1. Organization Settings Page
- [ ] Create settings page with tabbed layout (General, Team, Account)
- [ ] General tab: org name (editable), logo upload, default unit system toggle (imperial/metric)
- [ ] Account tab: user profile editing (name, email, password change)
- [ ] Implement `PATCH /api/v1/org` endpoint for updating org settings
- [ ] Logo upload to Supabase Storage (org-scoped path)

### 2. Team Member Management
- [ ] Create Team tab UI: member list table (name, email, role, status, last active)
- [ ] Implement `GET /api/v1/org/members` endpoint
- [ ] Role display with appropriate badges (Owner, Admin, Estimator, Viewer)
- [ ] Role change dropdown (Owner/Admin can change others' roles)
- [ ] Implement `PATCH /api/v1/org/members/:id` for role changes
- [ ] Deactivate member flow: confirm dialog -> soft delete -> remove access
- [ ] Implement `DELETE /api/v1/org/members/:id` (soft delete)

### 3. Invitation Flow
- [ ] Create invite dialog: email input + role selector
- [ ] Implement `POST /api/v1/org/members/invite` endpoint
  - Generate secure invitation token
  - Create `invitations` record (pending status)
  - Send invitation email with accept link
- [ ] Invitation acceptance page: invitee creates password, joins org
- [ ] Pending invitation list in Team tab (with resend/cancel options)
- [ ] Handle expired invitations (7-day expiry)
- [ ] Handle case where invitee already has a Contruo account

### 4. Guest Access
- [ ] Guest invitation flow: invite external email to a specific project
- [ ] Guest signup page (lighter flow -- name, email, password)
- [ ] Guest accounts flagged as `is_guest: true` in the database
- [ ] Guest access scoped to specific shared projects only
- [ ] Guest list in Team tab (separate section showing project access)
- [ ] Revoke guest access action

### 5. Permission Enforcement
- [ ] Create `permission_service.py` with role-based permission checks
- [ ] Implement permission matrix from `roles-and-permissions.md`
- [ ] Add permission middleware to all existing API endpoints
- [ ] Frontend: hide/disable UI elements based on user role
- [ ] Test permission boundaries: Viewer can't edit, Estimator can't manage team, etc.

### 6. Database & RLS
- [ ] Create/update migrations for `invitations` table
- [ ] Add RLS policies to all tables created so far
- [ ] Test cross-org data isolation (verify user A cannot access org B's data)

---

## Acceptance Criteria

- [ ] Admin can edit org name, upload logo, and set default unit system
- [ ] Admin can view all team members with their roles and status
- [ ] Admin can invite a new team member by email with a selected role
- [ ] Invitee receives an email and can accept to join the org
- [ ] Admin can change a member's role
- [ ] Admin can deactivate a member (preserves work history, removes access)
- [ ] Admin can invite an external guest to view a specific project
- [ ] Guest can create a free account and access only the shared project
- [ ] Permission checks enforce the role matrix on all API endpoints
- [ ] UI elements are hidden/disabled appropriately for each role

---

## Key References

- [Organization Management Feature](../features/platform/organization-management.md)
- [Roles & Permissions Feature](../features/collaboration/roles-and-permissions.md)
- [Auth & Onboarding Feature](../features/platform/auth-and-onboarding.md)
- [Screen Layouts - Settings](../docs/design/screen-layouts.md)
