# Sprint 04: Plan Upload & PDF Processing

> **Phase:** 2 - Plan Viewing
> **Duration:** 2 weeks
> **Status:** Complete
> **Depends On:** Sprint 03

## Sprint Goal

Build the plan upload flow and the async PDF processing pipeline. At the end of this sprint, users can upload PDF plan sets, the system processes them asynchronously (extracts pages, detects sheet names, generates thumbnails), and shows processing status.

---

## Tasks

### 1. Project Creation
- [x] Create "New Project" dialog UI (name, optional description)
- [x] Implement `POST /api/v1/projects` endpoint
- [x] Create projects table migration
- [x] Dashboard page: display project cards (name, sheet count, last updated, member count)
- [x] Implement `GET /api/v1/projects` endpoint with project listing
- [x] Click project card -> navigate to project workspace

### 2. Plan Upload UI
- [x] Create plan upload zone (drag-and-drop + file picker)
- [x] Accept PDF files only (validate file type and size)
- [x] Upload progress indicator (percentage bar)
- [x] Upload to Supabase Storage with org-scoped path: `{org_id}/plans/{plan_id}/`
- [x] Implement `POST /api/v1/projects/:id/plans` endpoint
  - Create `plans` record with status `processing`
  - Queue Celery task for PDF processing

### 3. PDF Processing Pipeline (Celery Worker)
- [x] Create `pdf_processing.py` Celery task
- [x] Download PDF from Supabase Storage
- [x] Extract page count using PyMuPDF
- [x] Create `sheets` records for each page
- [x] Parse sheet names from title blocks (heuristic: look for text matching patterns like "A1.01", "Sheet X of Y", common AIA naming)
- [x] Extract page dimensions (width, height in pixels)
- [x] Generate thumbnail images for each page (store in Supabase Storage)
- [x] Extract text layer from each page (store for future search)
- [x] Update plan status to `ready` on success, `error` on failure

### 4. Processing Status
- [x] Polling or WebSocket-based status updates in the frontend (polling via `usePlanStatus`)
- [x] Show processing progress: "Processing page 3 of 47..."
- [x] Show error state if processing fails (with retry option)
- [x] Once ready, navigate to the plan viewer (workspace auto-refreshes, viewer nav is Sprint 05)

### 5. Database
- [x] Create migrations for `plans` and `sheets` tables
- [x] RLS policies on `plans` and `sheets` tables
- [x] Implement `GET /api/v1/projects/:id/sheets` endpoint

---

## Acceptance Criteria

- [x] User can create a new project from the dashboard
- [x] User can upload a PDF file via drag-and-drop or file picker
- [x] Upload shows progress and stores the file in Supabase Storage
- [x] Celery worker picks up the processing task automatically
- [x] Worker extracts all pages, creates sheet records, generates thumbnails
- [x] Sheet names are auto-detected from title block text when possible
- [x] Processing status is visible in the UI (processing -> ready or error)
- [x] Plans and sheets data is accessible via API endpoints

---

## Delivered Artifacts

**Backend**
- Models: `app/models/project.py`, `app/models/plan.py`, `app/models/sheet.py`
- Migration: `migrations/versions/003_projects_plans_sheets.py` (tables + RLS + cascade deletes)
- Schemas: `app/schemas/project.py`, `app/schemas/plan.py`
- Services: `app/services/project_service.py`, `app/services/plan_service.py` (w/ audit events)
- Utilities: `app/utils/storage.py` (Supabase Storage wrapper), `app/utils/pdf.py` (PyMuPDF extractor + sheet-name heuristic)
- Celery task: `app/tasks/pdf_processing.py` (sync DB via `psycopg`, progress updates per page)
- API: `app/api/v1/projects.py`, `app/api/v1/plans.py` (create/list/get/update projects; upload/list plans; list sheets; plan status; retry)

**Frontend**
- Types/helpers: `types/project.ts`, `lib/api.ts` (XHR-based `uploadFile` with progress), `lib/utils.ts` (`formatRelativeTime`, `formatFileSize`)
- Hooks: `hooks/use-projects.ts`, `hooks/use-plan-status.ts`
- Components: `components/projects/plan-upload-zone.tsx`, `components/projects/new-project-dialog.tsx`, `components/projects/plan-processing-status.tsx`
- Pages: `app/(app)/dashboard/page.tsx` (live recent projects), `app/(app)/projects/page.tsx` (search + list + create), `app/(app)/project/[id]/page.tsx` (workspace with sheet index, upload zone, per-plan status)

**Tests**
- `tests/unit/test_pdf_utils.py` — sheet-name heuristic + extract_pdf with a generated fixture PDF
- `tests/unit/test_plan_service.py` — upload validation (content-type, size) and retry gating
- `tests/unit/test_project_endpoints.py` — create/list/get + plan upload/list/sheets with mocked services
- Full suite: **44 passed** (no regressions in Sprint 01-03 tests)

---

## Key References

- [Plan Viewer Feature](../features/core/plan-viewer.md) -- file formats, sheet management
- [Backend Architecture - PDF Pipeline](../docs/architecture/backend.md)
- [Screen Layouts - New Project Dialog](../docs/design/screen-layouts.md)
