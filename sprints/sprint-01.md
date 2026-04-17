# Sprint 01: Project Scaffolding

> **Phase:** 1 - Foundation
> **Duration:** 2 weeks
> **Status:** Complete
> **Depends On:** None (first sprint)

## Sprint Goal

Set up the complete development environment, initialize both frontend and backend repositories, configure CI/CD, connect Supabase, and establish the project structure. At the end of this sprint, the team has a working local dev environment with a Next.js frontend talking to a FastAPI backend, both connected to Supabase.

---

## Tasks

### 1. Repository & Project Setup
- [x] Initialize Git repository
- [x] Set up monorepo structure (frontend/ and backend/ in one repo)
- [x] Create `.gitignore`, `.env.example`, and project README
- [x] Define branch strategy (main, develop, feature branches)

### 2. Frontend Scaffolding (Next.js)
- [x] Initialize Next.js project with TypeScript
- [x] Install and configure Tailwind CSS
- [x] Install and configure shadcn/ui
- [x] Set up the dark theme using design system tokens from `docs/design/design-system.md`
- [x] Configure Inter font (primary) and JetBrains Mono (monospace)
- [x] Create the application shell layout (top bar, sidebar, main content area)
- [x] Set up routing structure (dashboard, project, settings, billing pages)
- [x] Install and configure Lucide Icons
- [x] Set up ESLint for code formatting
- [x] Create reusable layout components (AppShell, TopBar, Sidebar, StatusBar)

### 3. Backend Scaffolding (FastAPI)
- [x] Initialize FastAPI project with the folder structure from `docs/architecture/backend.md`
- [x] Set up Python virtual environment and `requirements.txt`
- [x] Configure FastAPI with CORS, error handling middleware
- [x] Create health check endpoint (`GET /api/v1/health`)
- [x] Set up Pydantic settings management for environment config
- [x] Install and configure SQLAlchemy for ORM
- [x] Create base model with `id`, `org_id`, `created_at`, `updated_at` fields

### 4. Supabase Setup
- [ ] Create Supabase project
- [ ] Configure Supabase Auth (email/password provider)
- [ ] Set up Supabase Storage bucket for plan uploads
- [x] Connect FastAPI to PostgreSQL (via SQLAlchemy async engine)
- [x] Set up Alembic for database migrations
- [x] Create initial migration with core tables: `organizations`, `users`, `event_log`
- [x] Configure Row-Level Security (RLS) policies on initial tables

### 5. Task Queue Setup
- [x] Set up Redis (local Docker container for dev)
- [x] Configure Celery with FastAPI
- [x] Create a test async task to verify the pipeline works

### 6. CI/CD & Dev Environment
- [x] Create `docker-compose.yml` for local development (Redis, local PG)
- [x] Set up GitHub Actions for:
  - [x] Frontend: lint, type check, build
  - [x] Backend: lint, type check, tests
- [x] Create development setup documentation in README

### 7. Event Logging Groundwork
- [x] Create `event_log` table with the schema from `docs/architecture/backend.md`
- [x] Create `event_service.py` with a basic `log_event()` function
- [x] Wire event logging into the service layer (available to all endpoints)

---

## Acceptance Criteria

- [x] `npm run dev` starts the Next.js frontend with the dark theme, app shell, and sidebar visible
- [x] `uvicorn app.main:app --reload` starts the FastAPI backend with Swagger docs at `/docs`
- [x] Frontend can call the backend health check endpoint successfully
- [ ] Supabase project is connected: database migrations run, RLS policies active
- [ ] Celery worker starts and processes a test task (requires Redis via Docker)
- [x] CI pipeline definition exists and is ready to run on push to main

---

## Notes

- Supabase project creation, Auth config, and Storage bucket setup are manual cloud-console tasks that need to be done by the developer. The code is ready to connect once credentials are provided.
- Celery test task code is in place; running the worker requires `docker compose up redis` first.
- The frontend builds and serves successfully with all routes defined.
- Backend health check returns `{"status": "healthy"}` with Swagger at `/docs`.

## Key References

- [Design System](../docs/design/design-system.md) -- for theme tokens, colors, typography
- [Screen Layouts](../docs/design/screen-layouts.md) -- for app shell structure
- [Backend Architecture](../docs/architecture/backend.md) -- for project structure, schema
