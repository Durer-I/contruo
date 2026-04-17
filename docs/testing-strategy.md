# Contruo Testing Strategy

> **Status:** Complete
> **Philosophy:** Pragmatic -- test critical paths and business logic thoroughly, skip low-value tests
> **Coverage Target:** 80% (unit + integration combined)
> **CI Policy:** All tests must pass before merging

---

## Testing Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| **Backend Unit + Integration** | pytest + pytest-asyncio | FastAPI endpoints, services, formula engine, geometry |
| **Backend Fixtures** | Factory Boy + Faker | Generate test data (users, projects, conditions, measurements) |
| **Backend DB Testing** | pytest + test database | Test against a real PostgreSQL instance (Supabase local or Docker) |
| **Frontend Unit** | Vitest + React Testing Library | Component rendering, hooks, utilities, formula parser |
| **Frontend Integration** | Vitest + MSW (Mock Service Worker) | Component flows with mocked API responses |
| **End-to-End** | Playwright | Critical user journeys in a real browser |
| **Coverage** | coverage.py (backend) + v8 (frontend) | Track and enforce 80% coverage |
| **CI Runner** | GitHub Actions | Run all tests on every PR, block merge on failure |

---

## Testing Layers

### Layer 1: Unit Tests (Highest Volume)

Pure function and isolated component tests. Fast, reliable, and the backbone of the test suite.

**Backend unit test targets:**

| Module | Priority | What to Test |
|--------|----------|-------------|
| Formula engine | Critical | Parsing, evaluation, variable substitution, edge cases (division by zero, missing vars, nested parens) |
| Geometry calculations | Critical | Length, area, perimeter, arc length for all shape types. Cutout subtraction. Coordinate transforms. |
| Scale calibration | Critical | Pixel-to-real-world conversion, unit conversions (imperial ↔ metric) |
| Auth helpers | High | JWT validation, role checking, permission matrix |
| RLS policy logic | High | Org isolation verification -- user A cannot access org B's data |
| PDF metadata extraction | Medium | Scale detection from PDF metadata/title blocks |
| Proration calculations | Medium | Seat additions mid-cycle, billing math |
| API request validation | Medium | Pydantic model validation, required fields, type checking |

**Frontend unit test targets:**

| Module | Priority | What to Test |
|--------|----------|-------------|
| Formula parser (client) | Critical | Same formula engine logic mirrored on the frontend for live preview |
| Geometry utilities | Critical | Coordinate math, distance calculations, area calculations |
| Scale conversion | High | Zoom-to-plan coordinate transforms |
| UI components | Medium | shadcn/ui customized components render correctly, handle props |
| Hooks | Medium | `useAuth`, `useConditions`, `useMeasurements` state management |
| Keyboard shortcuts | Low | Shortcut registration, conflict detection |

### Layer 2: Integration Tests (Medium Volume)

Tests that verify multiple components working together, including database and API interactions.

**Backend integration test targets:**

| Flow | Priority | What to Test |
|------|----------|-------------|
| Auth flow | Critical | Signup → org creation → login → JWT → protected endpoint |
| Measurement CRUD | Critical | Create condition → draw measurement → verify quantities → edit → delete |
| PDF upload pipeline | High | Upload → Supabase Storage → Celery task → sheet extraction → thumbnails |
| Export generation | High | Project with measurements → trigger export → verify PDF/Excel output |
| Invitation flow | High | Owner invites → email sent → accept invite → correct role assigned |
| Seat management | Medium | Add seat → proration calculated → DodoPayments webhook → subscription updated |
| RLS cross-org | Medium | Authenticated user A makes requests that should/shouldn't access org B data |

**Frontend integration test targets:**

| Flow | Priority | What to Test |
|------|----------|-------------|
| Login form → API → redirect | High | Form validation, API call with MSW, redirect to dashboard |
| Dashboard → project list | High | Fetch projects, render cards, empty state |
| Condition manager | High | Create, edit, delete conditions with mocked API |
| Quantities panel | High | Tree renders correctly from measurement data, subtotals correct |
| Export dialog | Medium | Format selection, trigger export, handle loading/success/error states |

### Layer 3: End-to-End Tests (Low Volume, High Value)

Full browser tests covering the critical user journeys. Written during Sprint 15 (Polish & QA).

**E2E test suite (5-10 tests):**

| Test | What It Covers |
|------|---------------|
| **Signup & onboarding** | Create account → org created → welcome modal → lands on dashboard |
| **Login & session** | Login with credentials → dashboard loads → logout → redirect to login |
| **Create project** | Dashboard → new project → name/upload plan → project opens in viewer |
| **Plan navigation** | Sheet index → click sheet → plan renders → zoom/pan → switch sheets |
| **Scale calibration** | Open calibration tool → draw known distance → enter value → scale set |
| **Linear takeoff** | Select condition → draw a line → running total updates → measurement saved |
| **Area takeoff** | Select area tool → draw polygon → area calculated → shows in quantities |
| **Count takeoff** | Select count tool → click to place markers → count updates |
| **Export** | Project with measurements → export dialog → download Excel → verify file exists |
| **Team invitation** | Settings → invite member → (verify API call) → member appears in team list |

**E2E conventions:**
- Use Playwright's `test.describe` to group related flows
- Each test is independent (creates its own test data via API seed)
- Tests run against a local dev environment (not production)
- Timeout: 30 seconds per test (canvas rendering can be slow)
- Screenshots captured on failure for debugging

---

## What We Don't Test

Pragmatic testing means explicitly deciding what's NOT worth testing:

| Skip | Reason |
|------|--------|
| Canvas pixel-perfect rendering | Too brittle, visual QA is manual. No snapshot tests at MVP. |
| Liveblocks real-time sync | Third-party service -- trust their tests. Mock at the boundary. |
| PDF rendering fidelity | PDF.js/PSPDFKit handles this. We test our overlay layer, not theirs. |
| shadcn/ui base components | Already tested upstream. Only test our customizations. |
| CSS/styling | Covered by manual review and design QA. No visual regression tools. |
| DodoPayments webhooks | Mock the webhook payloads, don't test their delivery infrastructure. |
| Supabase Auth internals | Mock at the Supabase client boundary. Test our auth helpers. |

---

## Test File Conventions

### Backend (Python / pytest)

```
contruo-backend/
├── tests/
│   ├── conftest.py              # Shared fixtures (test DB, auth tokens, factories)
│   ├── factories.py             # Factory Boy factories for all models
│   ├── unit/
│   │   ├── test_formula_engine.py
│   │   ├── test_geometry.py
│   │   ├── test_scale.py
│   │   ├── test_proration.py
│   │   └── test_permissions.py
│   ├── integration/
│   │   ├── test_auth_flow.py
│   │   ├── test_measurements.py
│   │   ├── test_pdf_pipeline.py
│   │   ├── test_export.py
│   │   ├── test_invitations.py
│   │   └── test_rls.py
│   └── fixtures/
│       ├── sample-plan.pdf      # Small test PDF for upload tests
│       └── sample-plan-multi.pdf # Multi-page test PDF
```

**Naming:** `test_<module>.py` with `test_<behavior>` functions.

```python
# Example: tests/unit/test_formula_engine.py
class TestFormulaEngine:
    def test_basic_arithmetic(self): ...
    def test_variable_substitution(self): ...
    def test_division_by_zero_returns_error(self): ...
    def test_nested_parentheses(self): ...
    def test_unknown_variable_raises(self): ...
```

### Frontend (TypeScript / Vitest)

```
contruo-frontend/
├── __tests__/                   # or colocated .test.ts files
│   ├── unit/
│   │   ├── formula.test.ts
│   │   ├── geometry.test.ts
│   │   └── scale.test.ts
│   ├── integration/
│   │   ├── login-form.test.tsx
│   │   ├── dashboard.test.tsx
│   │   ├── condition-manager.test.tsx
│   │   └── quantities-panel.test.tsx
│   └── mocks/
│       ├── handlers.ts          # MSW request handlers
│       └── server.ts            # MSW server setup
├── e2e/
│   ├── auth.spec.ts
│   ├── project.spec.ts
│   ├── takeoff.spec.ts
│   ├── export.spec.ts
│   └── team.spec.ts
```

**Naming:** `<module>.test.ts` for unit/integration, `<flow>.spec.ts` for E2E.

---

## CI/CD Pipeline

```
PR Opened / Push to Branch
        │
        ▼
┌───────────────────┐
│  Lint & Type Check │  ESLint + tsc (frontend), ruff + mypy (backend)
└────────┬──────────┘
         │ pass
         ▼
┌───────────────────┐     ┌───────────────────┐
│  Backend Tests     │     │  Frontend Tests    │  (run in parallel)
│  pytest --cov=80%  │     │  vitest --coverage │
└────────┬──────────┘     └────────┬──────────┘
         │ pass                     │ pass
         ▼                          ▼
┌─────────────────────────────────────────────┐
│  E2E Tests (Playwright)                      │  (Sprint 15+)
│  Only runs if unit + integration pass        │
└────────────────────┬────────────────────────┘
                     │ pass
                     ▼
              ✅ PR Mergeable
```

**CI rules:**
- All tests must pass to merge (blocking)
- Coverage must meet 80% threshold (enforced by CI)
- Lint + type check run first (fast fail)
- Backend and frontend tests run in parallel
- E2E tests run last (slowest, only after everything else passes)
- E2E tests are added to the pipeline starting Sprint 15

---

## Sprint Integration

Testing fits into the sprint workflow as follows:

| Sprint Phase | Testing Activity |
|-------------|-----------------|
| **Sprints 01-03** (Foundation) | Set up test infrastructure: pytest, Vitest, CI pipeline. Write first auth + RLS tests. |
| **Sprints 04-06** (Plan Viewing) | PDF pipeline integration tests, scale calibration unit tests |
| **Sprints 07-10** (Takeoff Tools) | Formula engine unit tests (heavy), geometry unit tests (heavy), measurement CRUD integration tests |
| **Sprints 11-12** (Data & Export) | Quantities aggregation tests, export generation integration tests |
| **Sprints 13-14** (Collab & Billing) | Liveblocks mock tests, proration unit tests, invitation flow integration tests |
| **Sprint 15** (Polish & QA) | Write all E2E tests, coverage audit, fix gaps to hit 80% |
| **Sprint 16** (Deploy & Launch) | E2E runs in staging environment, smoke tests post-deploy |

**Per-sprint testing rule:** Every feature PR must include tests. The sprint is not complete until its tests pass and coverage hasn't dropped below 80%.

---

## Test Database Strategy

Backend integration tests need a real PostgreSQL database:

- **Local development:** Use Supabase CLI (`supabase start`) which runs a local PostgreSQL instance
- **CI:** Use a PostgreSQL Docker container spun up as a GitHub Actions service
- **Isolation:** Each test run uses a fresh database (migrations applied, seeded with factory data, torn down after)
- **RLS testing:** Tests authenticate as different users to verify org isolation

---

## Key Testing Principles

1. **Test behavior, not implementation.** Assert what the function returns or what the API responds, not how it internally works.
2. **One assertion per concept.** A test can have multiple `assert` lines, but they should all verify one logical thing.
3. **Fast by default.** Unit tests should run in <5 seconds total. Integration tests in <30 seconds. E2E in <3 minutes.
4. **No flaky tests.** If a test fails intermittently, fix it or delete it. Flaky tests erode trust in the entire suite.
5. **Test the edges.** Division by zero, empty arrays, maximum values, Unicode in project names, special characters in formulas.
6. **Mock at the boundary.** Mock Supabase, Liveblocks, DodoPayments, and Celery at the service boundary. Never mock internal functions.

---

## Notes

- Visual regression testing (screenshot comparison) is explicitly deferred. Revisit post-MVP if canvas rendering bugs become frequent.
- Load/performance testing is not in scope for MVP. Will be addressed if scale demands it post-launch.
- The formula engine and geometry modules are the highest-value test targets. They're pure functions with tons of edge cases -- perfect for thorough unit testing.
