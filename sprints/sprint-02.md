# Sprint 02: Authentication & User Management

> **Phase:** 1 - Foundation
> **Duration:** 2 weeks
> **Status:** Complete
> **Depends On:** Sprint 01

## Sprint Goal

Implement the full authentication flow -- signup, login, email verification, password reset, and session management. At the end of this sprint, users can create an account, verify their email, log in, and access a protected dashboard page.

---

## Tasks

### 1. Signup Flow
- [x] Create signup page UI (name, email, password, organization name)
- [x] Implement Supabase Auth signup (email/password)
- [x] Create FastAPI endpoint: `POST /api/v1/auth/register`
  - Creates Supabase auth user
  - Creates `organizations` record
  - Creates `users` record with role `owner`
- [x] Email verification: Supabase sends verification email on signup
- [x] Post-verification redirect to dashboard
- [x] Form validation (email format, password strength, required fields)

### 2. Login Flow
- [x] Create login page UI (email, password)
- [x] Implement Supabase Auth login
- [x] JWT token storage (Supabase SSR cookies via @supabase/ssr)
- [x] Redirect to dashboard on successful login
- [x] Error handling for invalid credentials

### 3. Password Reset
- [x] Create "Forgot password" page UI (email input)
- [x] Implement Supabase Auth password reset email
- [x] Success/error feedback to user (shows "check your email" confirmation)

### 4. Session Management
- [x] FastAPI middleware: validate Supabase JWT on every API request (JWKS-based)
- [x] Extract user_id and org_id from JWT, inject into request state (AuthContext)
- [x] Handle expired tokens: return 401, frontend redirects to login
- [x] Implement logout (clear session, revoke Supabase token)

### 5. Protected Routes
- [x] Create auth provider in Next.js (`providers/auth-provider.tsx`)
- [x] Implement route protection via Next.js proxy (formerly middleware)
- [x] Unauthenticated users redirected to login; authenticated users redirected away from auth pages
- [x] Show user name and initials in the top bar avatar dropdown

### 6. Welcome Modal
- [x] Create the welcome modal component (4-step overview from screen-layouts.md)
- [x] Show on first login only (tracked via localStorage)
- [x] "Got it, let's go" button dismisses permanently

---

## Acceptance Criteria

- [x] A new user can sign up with name, email, password, and organization name
- [x] Verification email is sent and must be confirmed before full access (Supabase handles this)
- [x] User can log in with email/password and land on the dashboard
- [x] User can reset their password via email
- [x] Unauthenticated users are redirected to the login page
- [x] JWT validation works on all API endpoints (returns 401 for invalid/expired tokens)
- [x] Welcome modal appears on first login and can be dismissed
- [x] Logout clears the session and redirects to login

---

## Implementation Details

### Backend
- **Auth endpoints**: `POST /register`, `POST /login`, `POST /reset-password`, `POST /logout`, `GET /me`
- **JWT middleware**: Validates tokens via Supabase JWKS endpoint, caches public keys
- **Auth service**: Uses Supabase Admin API (service_role_key) for user creation
- **Event logging**: Registration events logged to `event_log` table
- **Pydantic schemas**: Full request validation with `EmailStr`, min/max lengths

### Frontend
- **Supabase SSR**: Uses `@supabase/ssr` for cookie-based session management
- **Proxy (middleware)**: Next.js 16 `proxy.ts` handles route protection server-side
- **Auth provider**: React context providing `signUp`, `signIn`, `signOut`, `resetPassword`
- **API client**: Auto-attaches JWT from Supabase session to all API requests
- **9 backend tests**: All passing (validation, auth, error handling)

---

## Key References

- [Auth & Onboarding Feature](../features/platform/auth-and-onboarding.md)
- [Screen Layouts - Welcome Modal](../docs/design/screen-layouts.md)
- [Backend Architecture - Auth Flow](../docs/architecture/backend.md)
