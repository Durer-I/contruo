---
name: Codebase audit findings
overview: Comprehensive read-only audit of the Contruo codebase covering security, UI/UX, redundancy, architecture/performance, and general recommendations — with concrete file references and a prioritized remediation roadmap.
todos:
  - id: p0-secrets
    content: "P0: Rotate Redis credential and remove hardcoded URL from backend/app/config.py; add gitleaks to CI"
    status: completed
  - id: p0-guest
    content: "P0: Enforce guest_project_access scoping in project_service list/get/plans/sheets/liveblocks/exports"
    status: completed
  - id: p0-rls
    content: "P0: Add cross-org access integration tests to harden the org_id filter defense"
    status: pending
  - id: p0-webhook
    content: "P0: Require DODOPAYMENTS_WEBHOOK_SECRET outside localhost; remove dev unsafe_unwrap path in deployed envs"
    status: completed
  - id: p0-500
    content: "P0: Sanitize 500 responses in middleware/error_handler.py; add request-id correlation"
    status: completed
  - id: p0-ratelimit
    content: "P0: Add slowapi rate limiting (auth, webhooks, exports)"
    status: completed
  - id: p0-docs
    content: "P0: Disable /docs and /redoc in production; trim /health response"
    status: completed
  - id: p1-pagination
    content: "P1: Add cursor pagination + default limits to measurements and projects list endpoints"
    status: completed
  - id: p1-refetch
    content: "P1: Replace per-edit full refetch with optimistic local updates + targeted broadcast in plan-viewer-workspace"
    status: pending
  - id: p1-reactquery
    content: "P1: Adopt @tanstack/react-query for projects/conditions/measurements (or remove the unused dep)"
    status: pending
  - id: p1-locking
    content: "P1: Add version column + If-Match handling on measurement updates; server-enforce select-locks"
    status: completed
  - id: p1-darktheme
    content: "P1: Default theme to dark; consolidate globals.css; delete globals_O.css"
    status: completed
  - id: p1-errors
    content: "P1: Add app/error.tsx ErrorBoundary, install sonner, replace silent .catch(() => {}) with toast"
    status: pending
  - id: p1-modal
    content: "P1: Fix welcome-modal.tsx render-time setState (use useEffect or lazy initializer)"
    status: completed
  - id: p1-settings
    content: "P1: Uncomment Settings General tab in settings-subnav.tsx"
    status: completed
  - id: p1-megacomp
    content: "P1: Split plan-viewer-workspace.tsx, quantities-panel.tsx, condition-manager-panel.tsx, measurement_service.py"
    status: pending
  - id: p2-indexes
    content: "P2: Add composite indexes (org_id, project_id [, sheet_id]) on measurements; add pg_trgm GIN on sheet text_content"
    status: pending
  - id: p2-formula
    content: "P2: lru_cache the formula AST parse step in formula_engine.py"
    status: pending
  - id: p2-celery
    content: "P2: Wire actual Celery retry (autoretry_for + backoff) on PDF and export tasks"
    status: pending
  - id: p2-jwks
    content: "P2: Add TTL + refresh-on-miss to JWKS cache in middleware/auth.py"
    status: pending
  - id: p2-pdfworker
    content: "P2: Self-host pdf.js worker in frontend/public/ instead of unpkg CDN"
    status: completed
  - id: p3-dupes
    content: "P3: Extract plan_to_response(), formatMeasurementTypeLabel(), test conftest.py; route Liveblocks auth through shared api client"
    status: pending
  - id: p3-codegen
    content: "P3: Add openapi-typescript codegen to keep frontend types in sync with backend schemas"
    status: pending
  - id: p3-validation
    content: "P3: Add max_length to LoginRequest password, condition description/notes, assembly formula"
    status: pending
  - id: p3-a11y
    content: "P3: aria-pressed/aria-label on takeoff-toolbar; aria-label on quantities chevron; align app-shell width warning to 1280px"
    status: pending
isProject: false
---

# Contruo Codebase Audit — Findings & Recommendations

A thorough sweep of `backend/`, `frontend/`, migrations, and config. Each finding cites real code. Severities reflect production risk, not MVP urgency.

---

## P0 — Fix Immediately (Security / Data)

### 1. Hardcoded production-style Redis credential committed to source — Critical
[`backend/app/config.py`](backend/app/config.py) line 44 hardcodes a full `redis://default:<password>@redis-…cloud.redislabs.com:11849` URL as a default for `redis_url`.

```42:44:backend/app/config.py
    # Redis / Celery
    # redis_url: str = "redis://localhost:6379/0"
    redis_url: str = 'redis://default:xi9rQA4Xu9pD9fcRvhsnb1RTlcewMFNg@redis-11849.c261.us-east-1-4.ec2.cloud.redislabs.com:11849'
```

Action: rotate the credential, replace default with `redis://localhost:6379/0` (or empty + fail fast in prod), add `gitleaks`/`trufflehog` to CI.

### 2. Guest scoping is not enforced — High (IDOR)
[`backend/app/services/project_service.py`](backend/app/services/project_service.py) `list_projects` (L68–110) and `get_project` (L132–138) only filter by `Project.org_id`. A `guest` role user with any project UUID in the same org can open it. The `guest_project_access` table exists but isn't joined.

Action: when `User.is_guest`, join `guest_project_access (user_id, project_id)` on every list / get / liveblocks-room / plans / sheets / export path.

### 3. RLS bypass — `org_id` filter is the only defense — High
Migrations enable RLS with `auth.uid()` policies (e.g. [`003_projects_plans_sheets.py`](backend/migrations/versions/003_projects_plans_sheets.py)), but the FastAPI app connects via SQLAlchemy + a privileged role, so RLS doesn't apply. Any service query missing `Model.org_id == org_id` is a cross-tenant bug.

Action: add a cross-org integration test pattern (`org_a` user can't read `org_b` resource for every endpoint). Long-term: use a non-`BYPASSRLS` role + `SET LOCAL app.org_id` per request, or a repository helper that mandates org scoping.

### 4. Dev-mode webhook signature bypass — High (config risk)
[`backend/app/services/billing_service.py`](backend/app/services/billing_service.py) L1112–1128: when `DODOPAYMENTS_WEBHOOK_SECRET` is empty AND `is_development`, payloads use `unsafe_unwrap` (no verification). Any environment that ever runs with `is_development=true` reachable from the internet is vulnerable.

Action: require the secret outside true `localhost`. Reject unsigned webhooks unconditionally in any deployed env.

### 5. Internal exception strings leak in 500 responses — High
[`backend/app/middleware/error_handler.py`](backend/app/middleware/error_handler.py) L61–72 returns `message: str(exc)` for unhandled errors — leaks DB/internal details.

Action: log full exception server-side with a request-id, return generic `"Internal server error"` to clients.

### 6. No rate limiting — High
[`backend/app/middleware/rate_limit.py`](backend/app/middleware/rate_limit.py) is a placeholder. `/auth/login`, `/auth/register`, exports, search, and webhooks are all unthrottled.

Action: integrate `slowapi` (Redis-backed) with strict limits on auth (5/min/IP), webhooks (per-source), and expensive routes; relaxed elsewhere.

### 7. `/docs`, `/redoc`, and `/health` expose route + env info — Medium
[`backend/app/main.py`](backend/app/main.py) L14–17 and [`backend/app/api/v1/health.py`](backend/app/api/v1/health.py) L7–13. Health returns `environment` (helps targeting).

Action: disable docs in prod via `if settings.is_production: docs_url=None`. Health returns `{ "status": "ok" }` only.

---

## P1 — High-impact Architecture & UX

### 8. Unbounded list endpoints — High
[`backend/app/services/measurement_service.py`](backend/app/services/measurement_service.py) `list_project_measurements` L529–551, [`backend/app/services/project_service.py`](backend/app/services/project_service.py) L68–110 return all rows. With 1k+ measurements per project (realistic), every navigation refetches huge JSON.

Action: add cursor pagination (`created_at`, `id`) with a default `limit=200`, max `1000`. Default measurement loads to sheet-scoped only in the viewer.

### 9. Plan-viewer refetch storm on every edit — High
[`frontend/components/plan-viewer/plan-viewer-workspace.tsx`](frontend/components/plan-viewer/plan-viewer-workspace.tsx) L429–462 calls `loadSheetMeasurements` after each create/patch/delete and broadcasts via `bumpMeasurementsRemote` so peers refetch the entire list. With 2–5 collaborators this is N² traffic.

Action: optimistic local list mutation + rollback on error; broadcast only the changed measurement ID; debounce remote refetch by 250–500 ms.

### 10. `@tanstack/react-query` installed but unused — Medium
[`frontend/package.json`](frontend/package.json) L19 lists it but the codebase uses raw `useEffect + api.get`. No cache, no dedup. Hooks like [`frontend/hooks/use-conditions.ts`](frontend/hooks/use-conditions.ts) reload every mount.

Action: either remove the dep or commit to it — wrap projects, conditions, measurements, and assemblies in `useQuery` with project-keyed cache + invalidation. Big perceived-speed win.

### 11. No optimistic locking on measurement updates — High
[`backend/app/services/measurement_service.py`](backend/app/services/measurement_service.py) `update_measurement` has no version / `If-Match` check; `Measurement.updated_at` is unused for concurrency. Two users editing simultaneously → silent last-write-wins. The "lock-on-select" rule is presence-only ([`frontend/components/collaboration/collaboration-room-shell.tsx`](frontend/components/collaboration/collaboration-room-shell.tsx) L56–65) — server doesn't enforce.

Action: bump `version` int on every update, require `If-Match: <version>`, return 409 on mismatch. Server-side: check `(SELECT lockedMeasurementId FROM presence)` for the room before applying the patch.

### 12. Frontend defaults to LIGHT theme despite dark-first design rules — High (UX)
[`frontend/app/providers.tsx`](frontend/app/providers.tsx) L9–14 uses `defaultTheme="light"`. [`frontend/app/globals.css`](frontend/app/globals.css) L7–72 has full light tokens at `:root`; the documented Contruo dark palette is in `.dark` only. First paint mismatches brand intent and project decisions.

Action: `defaultTheme="dark"`, mark html with `class="dark"`, remove or repurpose `:root` light values. Delete the orphan [`frontend/app/globals_O.css`](frontend/app/globals_O.css) backup.

### 13. No global ErrorBoundary, no toast system — High (UX)
No `app/error.tsx` / `global-error.tsx`. No `sonner` in [`frontend/package.json`](frontend/package.json). Several catches swallow silently:
- [`frontend/providers/auth-provider.tsx`](frontend/providers/auth-provider.tsx) L52–60 (auth/me)
- [`frontend/components/conditions/condition-manager-panel.tsx`](frontend/components/conditions/condition-manager-panel.tsx) L256–265 (templates)
- `.catch(() => {})` in [`frontend/components/plan-viewer/plan-pdf-canvas.tsx`](frontend/components/plan-viewer/plan-pdf-canvas.tsx)

Action: add `app/error.tsx` + `app/(app)/project/[id]/error.tsx`; install `sonner`; replace silent `.catch(() => {})` with toast + log.

### 14. Welcome modal sets state during render — Medium (Bug)
[`frontend/components/auth/welcome-modal.tsx`](frontend/components/auth/welcome-modal.tsx) L39–44 reads localStorage and calls setState in the render body — Rules-of-React violation, can warn in Strict Mode.

Action: lazy `useState(() => …)` initializer (window-guarded), or move sync into `useEffect`.

### 15. Settings "General" tab hidden — Medium (UX)
[`frontend/components/layout/settings-subnav.tsx`](frontend/components/layout/settings-subnav.tsx) L13–17 has the General entry commented out, but [`frontend/app/(app)/settings/page.tsx`](frontend/app/(app)/settings/page.tsx) renders it. Users can't navigate to org settings (name, logo, default unit) without typing the URL.

Action: uncomment the tab.

### 16. Mega-components — Medium (DX)
- [`frontend/components/plan-viewer/plan-viewer-workspace.tsx`](frontend/components/plan-viewer/plan-viewer-workspace.tsx) ~2400 lines
- [`frontend/components/quantities/quantities-panel.tsx`](frontend/components/quantities/quantities-panel.tsx) ~931 lines
- [`frontend/components/conditions/condition-manager-panel.tsx`](frontend/components/conditions/condition-manager-panel.tsx) ~897 lines
- [`backend/app/services/measurement_service.py`](backend/app/services/measurement_service.py) ~793 lines

Action: extract sheet-strip, status-strip, keyboard handler, and measurement-mutation hook from the workspace; split quantities into `QuantitiesTree` + `MeasurementRow` + `QuantityContextMenu`; split measurement service into `parsing/` + `crud/` + `derived/` modules.

---

## P2 — Performance & Schema

### 17. Composite indexes missing — Medium
[`backend/migrations/versions/005_conditions_and_measurements.py`](backend/migrations/versions/005_conditions_and_measurements.py) L71–73 creates single-column indexes on `org_id`, `project_id`, `sheet_id`, `condition_id`. Hot paths filter by `(org_id, project_id)` and `(org_id, project_id, sheet_id)`.

Action: new Alembic migration adding `ix_measurements_org_project (org_id, project_id)` and `ix_measurements_org_project_sheet (org_id, project_id, sheet_id, created_at desc)`.

### 18. Sheet text search has no GIN/trigram index — Medium
[`backend/app/services/sheet_service.py`](backend/app/services/sheet_service.py) L102–112 runs `Sheet.text_content.ilike(pattern)`. Linear scan as projects grow.

Action: enable `pg_trgm` extension, add a GIN index `(text_content gin_trgm_ops)`.

### 19. Formula AST re-parsed on every call — Medium
[`backend/app/services/formula_engine.py`](backend/app/services/formula_engine.py) L120–131 calls `ast.parse` per evaluation. Quantities lists evaluate once per measurement (`_derive_for_measurement` in [`measurement_service.py`](backend/app/services/measurement_service.py) L410–431).

Action: `functools.lru_cache(maxsize=512)` on the parse step keyed by the formula string.

### 20. Celery retries advertised but never invoked — Medium
[`backend/app/tasks/pdf_processing.py`](backend/app/tasks/pdf_processing.py) sets `max_retries=2` but no `self.retry()` and no `autoretry_for` in [`backend/app/tasks/celery_app.py`](backend/app/tasks/celery_app.py). Transient PDF storage hiccups crash with no retry.

Action: `autoretry_for=(IOError, httpx.HTTPError)`, `retry_backoff=True`, `retry_jitter=True` in `@shared_task`.

### 21. Subscription guard double-fetches subscription — Low
[`backend/app/middleware/subscription_guard.py`](backend/app/middleware/subscription_guard.py) L62–68 reads → refresh → reads again on every protected request.

Action: single read + use refresh return value.

### 22. JWKS cache never refreshes — Low
[`backend/app/middleware/auth.py`](backend/app/middleware/auth.py) L35–55. Key rotation requires process restart.

Action: TTL of 30 min, plus refresh-on-`kid`-miss.

### 23. PDF.js worker loaded from unpkg CDN — Low
[`frontend/lib/pdf-worker.ts`](frontend/lib/pdf-worker.ts). External dependency at runtime; CSP-unfriendly.

Action: copy `pdf.worker.min.mjs` into `frontend/public/` and reference locally; pin to `pdfjs-dist` version in deps.

---

## P3 — Code Quality, Redundancy, A11y

### 24. Duplicated `PlanResponse` construction
[`backend/app/api/v1/plans.py`](backend/app/api/v1/plans.py) L36–49, L59–71 vs [`backend/app/api/v1/projects.py`](backend/app/api/v1/projects.py) L227–239, L252–265. Add `def plan_to_response(p: Plan) -> PlanResponse` in `app/schemas/plan.py`.

### 25. Liveblocks auth bypasses shared `api` client
[`frontend/lib/liveblocks-auth.ts`](frontend/lib/liveblocks-auth.ts) L21–28 hand-rolls fetch + token + URL. Use `api.postRaw` from [`frontend/lib/api.ts`](frontend/lib/api.ts).

### 26. `typeLabel` repeated in 3 places
[`frontend/components/conditions/condition-manager-panel.tsx`](frontend/components/conditions/condition-manager-panel.tsx) L349–350, [`frontend/app/(app)/templates/page.tsx`](frontend/app/(app)/templates/page.tsx) L25–26, [`frontend/components/templates/edit-condition-template-dialog.tsx`](frontend/components/templates/edit-condition-template-dialog.tsx) L36–37.
Action: `lib/condition-units.ts` → `formatMeasurementTypeLabel(t)`.

### 27. Test fixture duplication
[`backend/tests/unit/test_measurement_endpoints.py`](backend/tests/unit/test_measurement_endpoints.py) and [`backend/tests/unit/test_condition_endpoints.py`](backend/tests/unit/test_condition_endpoints.py) share identical `_ctx`, `_mock_db`, `_override_auth` (L14–52 each).
Action: extract to `backend/tests/conftest.py`.

### 28. Pydantic ↔ TypeScript type drift risk — Medium
Backend `MeasurementType` and frontend `MeasurementType` are hand-twins. Adding `gross_measured_value` requires touching both.
Action: add `openapi-typescript` or `@hey-api/openapi-ts` in CI; emit types from FastAPI's `/openapi.json` to `frontend/types/api.gen.ts`.

### 29. Login password has no max_length — Medium
[`backend/app/schemas/auth.py`](backend/app/schemas/auth.py) L12–14: `password: str` (registration caps at 128). Allows large-body login attempts.
Action: `Field(..., min_length=1, max_length=128)`.

### 30. Unbounded `description`, `notes`, `formula` fields — Medium
[`backend/app/schemas/condition.py`](backend/app/schemas/condition.py) L36–37, [`backend/app/schemas/assembly.py`](backend/app/schemas/assembly.py) L32–36 have no `max_length`.
Action: cap at 5–10k for text, 2k for `formula`.

### 31. A11y: toolbar tools missing pressed/label
[`frontend/components/plan-viewer/takeoff-toolbar.tsx`](frontend/components/plan-viewer/takeoff-toolbar.tsx) L157–176 uses `title=` only. Add `aria-pressed={active===id}` and `aria-label={...}`.

### 32. App-shell warns at 1024 px instead of 1280
[`frontend/components/layout/app-shell.tsx`](frontend/components/layout/app-shell.tsx) L16–29. Design-system rule says minimum 1280×720.

### 33. Condition list on quantity expand has no accessible name
[`frontend/components/quantities/quantities-panel.tsx`](frontend/components/quantities/quantities-panel.tsx) L473–484: chevron has `aria-expanded` but no `aria-label`.

### 34. Inconsistent REST nesting
Measurements are created at `/projects/{id}/measurements` but updated at `/measurements/{id}`. Pick one style ([`backend/app/api/v1/measurements.py`](backend/app/api/v1/measurements.py)) and document it.

### 35. Settings auth-provider failures swallowed
[`frontend/app/(app)/settings/page.tsx`](frontend/app/(app)/settings/page.tsx) L19–25, L76–81 — failed `api.get` leaves `org` null → infinite spinner.

---

## Summary Table

- **P0 (security/data)**: 7 findings — credentials, IDOR, RLS, webhooks, error leakage, rate limit, info disclosure
- **P1 (architecture/UX)**: 9 findings — pagination, refetch storms, react-query, locking, theme, ErrorBoundary, modal bug, hidden settings, mega-components
- **P2 (performance/schema)**: 7 findings — indexes, search, formula cache, Celery, JWKS, CDN
- **P3 (quality/a11y)**: 12 findings — duplication, drift, validation, accessibility

## Recommended Sprint Slicing

- **Sprint A (1–2 days)**: P0 #1, #4, #5, #6, #7. Pure config/middleware. Highest leverage.
- **Sprint B (3–5 days)**: P0 #2, #3 (guest scoping + cross-org test harness).
- **Sprint C (1 week)**: P1 #8, #10, #11 (pagination + react-query + optimistic lock). Big snappiness win.
- **Sprint D (2–3 days)**: P1 #12, #13, #14, #15 (theme, errors, toast, modal, settings tab). Visible polish.
- **Sprint E (3–5 days)**: P1 #16, P2 indexes/cache/celery. Refactors during a quiet sprint.
- **Sprint F (ongoing)**: P3 cleanup folded into feature work.

I have NOT made any code changes — this is a read-only audit. Confirm if you'd like me to switch to agent mode and start executing on a specific sprint, or if you want me to expand any finding into a more detailed remediation plan.