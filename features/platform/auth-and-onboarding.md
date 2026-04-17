# Authentication & Onboarding

> **Category:** Platform & Infrastructure
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Handle user registration, login, and initial onboarding into Contruo. Authentication at MVP is **email/password only**. Signup requires creating an organization immediately (company name) -- there are no personal-only accounts. After signup, the user (who becomes the org Owner) lands in their workspace with a **welcome modal** providing a quick overview of how Contruo works. Team members join via email invitations from an admin or owner.

## User Stories

- As a new user, I want to sign up with my email and password and set up my organization so that I can start using Contruo with my team.
- As a new user, I want to see a quick welcome overview after my first login so that I understand the core workflow without reading documentation.
- As an admin, I want to invite team members by email so that they can create their accounts and join our organization.
- As an invited user, I want to click a link in my invitation email, create my password, and land in the organization workspace so that I can start working immediately.
- As a user, I want to reset my password via email if I forget it so that I can regain access to my account.
- As a guest, I want to create a free account when invited to review a shared project so that I can view the takeoff and leave feedback.

## Key Requirements

### Authentication
- **Email/password** authentication only at MVP
- Secure password requirements (minimum length, complexity rules)
- Password hashing with bcrypt or argon2 (never store plaintext)
- Email verification on signup (confirm email before full access)
- Password reset via email link (time-limited token)
- Session management with JWT or secure session tokens
- Auto-logout after extended inactivity (configurable, e.g., 24 hours)

### Signup Flow

```
1. Landing page -> "Sign Up" button
2. Enter: Full name, Email, Password
3. Enter: Organization/Company name
4. Email verification sent -> user clicks verification link
5. User lands in their workspace as the Owner
6. Welcome modal appears with quick overview
7. Optional: "Invite your team" prompt (can skip)
```

- Organization is created as part of signup -- no standalone personal accounts
- The signing-up user becomes the **Owner** role automatically
- Organization name can be changed later in settings

### Invitation Flow

```
1. Admin/Owner enters team member's email + selects their role (Admin, Estimator, Viewer)
2. System sends invitation email with a unique link
3. Invitee clicks link -> lands on account creation page (name, password)
4. Account created -> invitee lands in the organization workspace with their assigned role
5. Invitation expires after 7 days if not accepted (can be re-sent)
```

- Pending invitations visible in the team management UI with status (pending/accepted/expired)
- Admin can cancel or re-send pending invitations
- If the invitee already has a Contruo account (e.g., a guest account), they're added to the org without re-registering

### Guest Account Flow

```
1. Admin/Owner shares a project with an external email
2. System sends invitation email: "You've been invited to review a project on Contruo"
3. Guest clicks link -> creates a free account (name, email, password)
4. Guest lands in a limited view showing only the shared project
5. Guest has Viewer-level permissions on the shared project only
```

- Guest accounts are free and don't count toward the org's seat billing
- Guests can later upgrade to a full account if they create their own organization

### Welcome Modal (Onboarding)
- Appears on first login only (dismissible, doesn't return)
- Brief overview of the core workflow in 3-4 steps:
  1. Upload a plan (PDF)
  2. Create a condition (name, color, measurement type)
  3. Start measuring (linear, area, count tools)
  4. Review quantities in the panel on the right
- Optional "Show me" link to documentation or a short video (if available)
- "Got it" button to dismiss

### Account Settings
- Edit profile: name, email, password
- Notification preferences (for future use with Comments & Markup)
- Active sessions view (see where you're logged in)

## Nice-to-Have

- **Google Sign-In**: OAuth2 integration for one-click signup/login
- **Microsoft Sign-In**: OAuth2 for enterprise users on Microsoft 365
- **Full SSO (SAML/OIDC)**: for enterprise clients with identity providers (Okta, Azure AD, etc.)
- **Guided interactive tour**: step-by-step walkthrough with tooltips highlighting features
- **Sample project**: pre-loaded project with a real construction plan so new users can try tools immediately
- **Two-factor authentication (2FA)**: TOTP-based 2FA for enhanced security
- **Magic link login**: passwordless login via email link
- **Remember device**: skip re-authentication on trusted devices

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Desktop software with license key activation. No cloud authentication. No team invitations -- each user has their own license. |
| Bluebeam | Desktop with Bluebeam account for cloud features. Email/password + SSO for enterprise. Bluebeam Studio requires account creation. |
| On-Screen Takeoff | Desktop with license key. No cloud auth. Shared via network file access, not user accounts. |
| Togal.AI | Web-based with email/password signup. Google Sign-In available. Basic team invitation system. Minimal onboarding flow. |

## Open Questions

- [ ] What should the minimum password requirements be? (8+ chars, must include number/special char?)
- [ ] How long should sessions last before requiring re-authentication?
- [ ] Should we support "remember me" checkbox for extended sessions?
- [ ] What email provider should be used for transactional emails (verification, invitations, password reset)? (SendGrid, AWS SES, Resend, etc.)
- [ ] Should failed login attempts trigger account lockout? If so, after how many attempts?

## Technical Considerations

- Use a proven auth library or service rather than building from scratch -- consider Supabase Auth, Firebase Auth, or Auth.js (NextAuth) depending on the tech stack
- JWT tokens should be short-lived (15-60 minutes) with refresh tokens for session continuity
- All auth endpoints must be rate-limited to prevent brute force attacks
- Invitation tokens should be single-use, time-limited (7 days), and cryptographically secure
- Email verification and password reset tokens should expire and be single-use
- The user/account table needs to distinguish between regular users and guest users (a `type` or `is_guest` field)
- Session management needs to integrate with the real-time collaboration WebSocket connections -- when a session expires, the WebSocket connection should close gracefully

## Notes

- Email/password only at MVP is the right call. Social logins (Google, Microsoft) are the highest-priority post-MVP auth additions -- they reduce signup friction significantly. SSO (SAML/OIDC) is an enterprise feature that can come later when Contruo has enterprise customers asking for it.
- Requiring an organization at signup aligns perfectly with Contruo's B2B model. Every project, template, and billing relationship is org-scoped. Allowing org-less accounts would create unnecessary complexity.
- The welcome modal is a minimal-effort, high-impact onboarding touchpoint. It takes perhaps a day to build and prevents the "blank canvas paralysis" that kills SaaS trial conversions. A full interactive tour can be built later based on real user feedback about where people get stuck.
- The guest account flow is a deliberate growth engine: every guest who creates an account is a potential future paying customer (their own org, their own subscription).
