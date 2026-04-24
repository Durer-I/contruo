# Contruo Backend Architecture

> **Status:** In Progress
> **Stack:** FastAPI (Python) + PostgreSQL (Supabase) + Liveblocks + Supabase Storage

---

## Tech Stack Overview

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI (Python 3.11+) | REST API, WebSocket endpoints, business logic |
| **Database** | PostgreSQL via Supabase | Relational data storage, row-level security |
| **Authentication** | Supabase Auth | User registration, login, session management, JWT tokens |
| **Real-Time Collaboration** | Liveblocks | Live cursors, presence, measurement sync, conflict resolution |
| **File Storage** | Supabase Storage | PDF plan uploads, logo uploads, exported files |
| **Payment Processing** | DodoPayments | Subscriptions, seat billing, invoicing |
| **PDF Processing** | PyMuPDF (fitz) + pdfplumber | PDF rendering, vector extraction, text search, metadata parsing |
| **Task Queue** | Celery + Redis (or similar) | Async jobs: PDF processing, export generation, email sending |
| **Email** | Resend / SendGrid / AWS SES | Transactional emails: invitations, password reset, notifications |
| **Deployment** | TBD | Container-based (Docker), cloud hosting |

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Next.js    │────▶│   FastAPI    │────▶│  PostgreSQL  │
│   Frontend   │     │   Backend    │     │  (Supabase)  │
└──────┬──────┘     └──────┬───────┘     └──────────────┘
       │                   │
       │            ┌──────┴───────┐
       │            │  Celery      │
       │            │  Workers     │
       │            └──────┬───────┘
       │                   │
       ├──────────▶ ┌──────┴───────┐
       │            │  Supabase    │
       │            │  Storage     │
       │            └──────────────┘
       │
       └──────────▶ ┌──────────────┐
                    │  Liveblocks  │
                    │  (Real-Time) │
                    └──────────────┘
```

### Data Flow

1. **Frontend (Next.js)** communicates with the **FastAPI backend** via REST API for CRUD operations
2. **Frontend** connects directly to **Liveblocks** for real-time collaboration (cursors, presence, live measurement sync)
3. **FastAPI** reads/writes to **PostgreSQL (Supabase)** for persistent data
4. **Supabase Auth** handles authentication; JWT tokens are validated by FastAPI middleware on every request
5. **Supabase Storage** stores uploaded PDFs and files; FastAPI generates signed URLs for secure access
6. **Celery workers** handle async tasks (PDF processing, export generation, email sending)
7. **DodoPayments webhooks** are received by FastAPI endpoints for billing events

---

## Project Structure

```
contruo-backend/
├── app/
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Environment config, settings
│   ├── dependencies.py          # Shared dependencies (DB session, auth, etc.)
│   │
│   ├── api/                     # API route handlers
│   │   ├── v1/
│   │   │   ├── auth.py          # Login, register, password reset
│   │   │   ├── organizations.py # Org CRUD, settings
│   │   │   ├── members.py       # Team member management, invitations
│   │   │   ├── projects.py      # Project CRUD
│   │   │   ├── plans.py         # Plan upload, sheet management
│   │   │   ├── conditions.py    # Condition & assembly CRUD
│   │   │   ├── measurements.py  # Measurement CRUD, overrides
│   │   │   ├── templates.py     # Condition template library
│   │   │   ├── export.py        # PDF/Excel export triggers
│   │   │   ├── billing.py       # Subscription, seats, invoices
│   │   │   └── webhooks.py      # DodoPayments webhooks
│   │   └── router.py            # API router aggregation
│   │
│   ├── models/                  # SQLAlchemy / SQLModel ORM models
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── project.py
│   │   ├── plan.py
│   │   ├── sheet.py
│   │   ├── condition.py
│   │   ├── assembly_item.py
│   │   ├── measurement.py
│   │   ├── invitation.py
│   │   ├── subscription.py
│   │   ├── event_log.py         # Audit/activity log events
│   │   └── base.py              # Base model with org_id, timestamps
│   │
│   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── organization.py
│   │   ├── project.py
│   │   ├── plan.py
│   │   ├── condition.py
│   │   ├── measurement.py
│   │   └── export.py
│   │
│   ├── services/                # Business logic layer
│   │   ├── auth_service.py
│   │   ├── org_service.py
│   │   ├── project_service.py
│   │   ├── plan_service.py      # PDF processing, sheet extraction
│   │   ├── condition_service.py
│   │   ├── measurement_service.py
│   │   ├── formula_engine.py    # Expression parser for assembly formulas
│   │   ├── export_service.py    # PDF/Excel generation
│   │   ├── billing_service.py   # Seat management, proration
│   │   ├── permission_service.py# Role/permission checks
│   │   └── event_service.py     # Audit log event recording
│   │
│   ├── middleware/
│   │   ├── auth.py              # JWT validation, user injection
│   │   ├── org_scope.py         # Inject org_id, enforce data isolation
│   │   ├── rate_limit.py        # API rate limiting
│   │   └── error_handler.py     # Global error handling
│   │
│   ├── tasks/                   # Celery async tasks
│   │   ├── pdf_processing.py    # Extract sheets, metadata, text, vectors
│   │   ├── export_generation.py # Generate PDF/Excel exports
│   │   └── email.py             # Send transactional emails
│   │
│   └── utils/
│       ├── pdf.py               # PDF parsing utilities (PyMuPDF wrappers)
│       ├── geometry.py          # Polygon math, area/perimeter calculations
│       ├── formula.py           # Math expression parser
│       └── storage.py           # Supabase Storage helpers
│
├── migrations/                  # Alembic database migrations
├── tests/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Database Schema (Core Tables)

### Organizations & Users

```sql
-- Organizations
CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    logo_url        TEXT,
    default_units   VARCHAR(20) DEFAULT 'imperial',  -- 'imperial' | 'metric'
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Users (extends Supabase auth.users)
CREATE TABLE users (
    id              UUID PRIMARY KEY REFERENCES auth.users(id),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'estimator',  -- 'owner' | 'admin' | 'estimator' | 'viewer'
    is_guest        BOOLEAN DEFAULT false,
    deactivated_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Invitations
CREATE TABLE invitations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    email           VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL,
    invited_by      UUID NOT NULL REFERENCES users(id),
    token           VARCHAR(255) NOT NULL UNIQUE,
    status          VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'accepted' | 'expired' | 'cancelled'
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### Projects & Plans

```sql
-- Projects
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) DEFAULT 'active',  -- 'active' | 'archived'
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Plans (uploaded PDF files)
CREATE TABLE plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    project_id      UUID NOT NULL REFERENCES projects(id),
    filename        VARCHAR(255) NOT NULL,
    storage_path    TEXT NOT NULL,
    file_size       BIGINT,
    page_count      INTEGER,
    status          VARCHAR(20) DEFAULT 'processing',  -- 'processing' | 'ready' | 'error'
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Sheets (individual pages from a plan PDF)
CREATE TABLE sheets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    plan_id         UUID NOT NULL REFERENCES plans(id),
    page_number     INTEGER NOT NULL,
    sheet_name      VARCHAR(255),  -- auto-detected: "A1.01 - First Floor Plan"
    scale_value     FLOAT,         -- calibrated scale (pixels per real-world unit)
    scale_unit      VARCHAR(20),   -- 'ft' | 'm'
    scale_label     VARCHAR(100),  -- display: '1/4" = 1\'-0"'
    width_px        INTEGER,
    height_px       INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### Conditions & Assemblies

```sql
-- Conditions
CREATE TABLE conditions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    project_id      UUID NOT NULL REFERENCES projects(id),
    name            VARCHAR(255) NOT NULL,
    measurement_type VARCHAR(20) NOT NULL,  -- 'linear' | 'area' | 'count'
    unit            VARCHAR(20) NOT NULL,   -- 'LF' | 'SF' | 'EA' | 'CF' etc.
    color           VARCHAR(7) NOT NULL,    -- hex: '#ef4444'
    line_style      VARCHAR(20) DEFAULT 'solid',  -- 'solid' | 'dashed' | 'dotted'
    line_width      FLOAT DEFAULT 2.0,
    fill_opacity    FLOAT DEFAULT 0.3,      -- for area conditions
    fill_pattern    VARCHAR(20) DEFAULT 'solid',  -- 'solid' | 'hatch' | 'crosshatch'
    properties      JSONB DEFAULT '{}',     -- custom properties: {"height": 8, "spacing": 16}
    trade           VARCHAR(100),           -- optional: "03 - Concrete"
    description     TEXT,
    notes           TEXT,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Assembly Items
CREATE TABLE assembly_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    condition_id    UUID NOT NULL REFERENCES conditions(id),
    parent_id       UUID REFERENCES assembly_items(id),  -- NULL at MVP, for future nesting
    name            VARCHAR(255) NOT NULL,
    unit            VARCHAR(20) NOT NULL,
    formula         TEXT NOT NULL,           -- expression: "length * height * 2 / 32"
    description     TEXT,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Condition Templates (org-level library)
CREATE TABLE condition_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(255) NOT NULL,
    measurement_type VARCHAR(20) NOT NULL,
    unit            VARCHAR(20) NOT NULL,
    color           VARCHAR(7) NOT NULL,
    line_style      VARCHAR(20) DEFAULT 'solid',
    line_width      FLOAT DEFAULT 2.0,
    fill_opacity    FLOAT DEFAULT 0.3,
    fill_pattern    VARCHAR(20) DEFAULT 'solid',
    properties      JSONB DEFAULT '{}',
    trade           VARCHAR(100),
    description     TEXT,
    assembly_items  JSONB DEFAULT '[]',  -- snapshot of assembly items for import
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### Measurements

```sql
-- Measurements
CREATE TABLE measurements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    project_id      UUID NOT NULL REFERENCES projects(id),
    sheet_id        UUID NOT NULL REFERENCES sheets(id),
    condition_id    UUID NOT NULL REFERENCES conditions(id),
    measurement_type VARCHAR(20) NOT NULL,  -- 'linear' | 'area' | 'count'
    geometry        JSONB NOT NULL,         -- vertices, arcs, etc.
    measured_value  FLOAT NOT NULL,         -- calculated from geometry
    override_value  FLOAT,                  -- manual override (NULL = use measured)
    deductions      JSONB DEFAULT '[]',     -- deduction segments for linear
    label           VARCHAR(255),
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### Billing

```sql
-- Subscriptions
CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) UNIQUE,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    -- 'active' | 'past_due' | 'grace_period' | 'read_only' | 'suspended' | 'cancelled'
    seat_count      INTEGER NOT NULL DEFAULT 1,
    price_per_seat  INTEGER NOT NULL,       -- in smallest currency unit (cents/paise)
    currency        VARCHAR(3) DEFAULT 'USD',
    billing_cycle_start TIMESTAMPTZ NOT NULL,
    billing_cycle_end   TIMESTAMPTZ NOT NULL,
    payment_provider_id VARCHAR(255),       -- DodoPayments subscription ID
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### Event Log (Audit Trail Groundwork)

```sql
-- Event Log (captured from day one, UI comes post-launch)
CREATE TABLE event_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    project_id      UUID REFERENCES projects(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    event_type      VARCHAR(50) NOT NULL,
    -- 'measurement.created' | 'measurement.edited' | 'measurement.deleted'
    -- 'condition.created' | 'condition.edited' | 'plan.uploaded' | etc.
    entity_type     VARCHAR(50),            -- 'measurement' | 'condition' | 'plan' | etc.
    entity_id       UUID,
    payload         JSONB DEFAULT '{}',     -- before/after snapshots, change details
    session_id      UUID,                   -- group related changes
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_event_log_org_project ON event_log(org_id, project_id, created_at DESC);
CREATE INDEX idx_event_log_entity ON event_log(entity_type, entity_id, created_at DESC);
```

---

## Row-Level Security (Multi-Tenancy)

Every table with user data has an `org_id` column. Supabase RLS policies enforce data isolation:

```sql
-- Example RLS policy for projects table
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their org's projects"
    ON projects
    FOR ALL
    USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()));
```

This pattern is applied to ALL data tables. Even if application code has a bug, the database itself prevents cross-org data access.

---

## API Design Patterns

### Versioned API
- All endpoints under `/api/v1/`
- Future-proofs for public API release (P2) without breaking existing clients

### Consistent Response Format

```python
# Success
{
    "data": { ... },
    "meta": {
        "total": 47,
        "page": 1,
        "per_page": 50
    }
}

# Error
{
    "error": {
        "code": "MEASUREMENT_NOT_FOUND",
        "message": "Measurement with ID abc123 not found",
        "details": {}
    }
}
```

### Authentication Flow

```
1. User logs in via Supabase Auth (email/password)
2. Supabase returns JWT access token + refresh token
3. Frontend includes JWT in Authorization header: "Bearer <token>"
4. FastAPI middleware validates JWT via Supabase's JWKS endpoint
5. Middleware extracts user_id, looks up org_id, injects into request state
6. All downstream queries are scoped to that org_id
```

### Key API Endpoints

```
POST   /api/v1/auth/register          # Sign up + create org
POST   /api/v1/auth/login             # Login (delegates to Supabase)
POST   /api/v1/auth/reset-password    # Request password reset

GET    /api/v1/org                     # Get current org details
PATCH  /api/v1/org                     # Update org settings
GET    /api/v1/org/members             # List team members
POST   /api/v1/org/members/invite      # Send invitation
DELETE /api/v1/org/members/:id         # Deactivate member

GET    /api/v1/projects                # List projects
POST   /api/v1/projects                # Create project
GET    /api/v1/projects/:id            # Get project details
PATCH  /api/v1/projects/:id            # Update project
DELETE /api/v1/projects/:id            # Archive project

POST   /api/v1/projects/:id/plans      # Upload plan PDF
GET    /api/v1/projects/:id/sheets     # List sheets
PATCH  /api/v1/sheets/:id/scale        # Set scale calibration

GET    /api/v1/projects/:id/conditions         # List conditions
POST   /api/v1/projects/:id/conditions         # Create condition
PATCH  /api/v1/conditions/:id                  # Update condition
DELETE /api/v1/conditions/:id                  # Delete condition
POST   /api/v1/conditions/:id/assembly-items   # Add assembly item
PATCH  /api/v1/assembly-items/:id              # Update assembly item
DELETE /api/v1/assembly-items/:id              # Delete assembly item

GET    /api/v1/projects/:id/measurements       # List measurements (with aggregation)
POST   /api/v1/projects/:id/measurements       # Create measurement
PATCH  /api/v1/measurements/:id                # Update measurement (geometry, override)
DELETE /api/v1/measurements/:id                # Delete measurement
PATCH  /api/v1/measurements/:id/condition      # Reassign condition

POST   /api/v1/projects/:id/export             # Trigger export generation
GET    /api/v1/exports/:id/download            # Download generated export

GET    /api/v1/org/templates                   # List condition templates
POST   /api/v1/org/templates                   # Create template
POST   /api/v1/projects/:id/conditions/import  # Import template into project

GET    /api/v1/billing                         # Get subscription details
POST   /api/v1/billing/seats                   # Add/remove seats
GET    /api/v1/billing/invoices                # List invoices
POST   /api/v1/webhooks/dodopayments           # DodoPayments webhook handler
```

---

## Liveblocks Integration

Liveblocks handles real-time collaboration. The integration pattern:

### Room Structure
- Each **project** is a Liveblocks room
- Room ID format: `contruo:{org_id}:{project_id}`
- All users in the same project join the same room

### What Liveblocks Manages
- **Presence**: user cursors, active sheet, active tool, selected condition, locked measurement ID
- **Storage**: live measurement state that syncs across clients (used during active editing sessions)
- **Broadcast**: events like "measurement completed", "measurement deleted", "condition changed"

### What the Database Manages
- **Persistent state**: all measurements, conditions, and quantities are persisted to PostgreSQL
- Liveblocks is the real-time transport layer; the database is the source of truth
- When a user creates/edits a measurement, it's sent to both Liveblocks (for instant sync) and the FastAPI backend (for persistence)

### Auth for Liveblocks
- FastAPI provides a `/api/v1/liveblocks/auth` endpoint
- Frontend calls this endpoint to get a Liveblocks auth token
- The endpoint validates the user's Supabase JWT and returns a Liveblocks token scoped to the correct room with the user's identity and permissions

---

## PDF Processing Pipeline

When a user uploads a PDF plan set:

```
Upload → Storage → Queue → Process → Ready
```

1. **Upload**: Frontend uploads PDF to Supabase Storage via signed URL
2. **Record**: FastAPI creates a `plans` record with status `processing`
3. **Queue**: A Celery task is queued for PDF processing
4. **Process** (async worker):
   a. Download PDF from storage
   b. Extract page count and create `sheets` records
   c. Parse sheet names from title blocks (heuristic + regex patterns)
   d. Extract text layer for search indexing
   e. Extract scale information from metadata/title block
   f. Generate thumbnail images for the sheet index
   g. Extract vector geometry for snap-to-geometry feature (store as indexed spatial data)
5. **Ready**: Update plan status to `ready`, notify frontend via Liveblocks broadcast

### PDF Libraries
- **PyMuPDF (fitz)**: primary library for rendering, text extraction, and vector path extraction
- **pdfplumber**: supplementary for table and structured text extraction from title blocks
- **Pillow**: thumbnail generation

---

## Formula Engine

A shared module used by the Conditions & Assemblies feature to evaluate assembly item formulas.

### Supported Syntax
- Arithmetic: `+`, `-`, `*`, `/`, `^`, `()`
- Functions: `round()`, `ceil()`, `floor()`, `min()`, `max()`, `abs()`
- Variables: measurement value (`length`, `area`, `count`), custom properties (`height`, `depth`, `spacing`, etc.)

### Implementation
- Use a lightweight expression parser (e.g., `py_expression_eval` or custom tokenizer/parser)
- Variables are resolved from the measurement value + condition properties at evaluation time
- Formulas are validated on save (syntax check + variable existence check)
- Evaluation is deterministic and side-effect-free

### Example

```python
formula = "length * height * 2 / 32"
variables = {"length": 500, "height": 8}
result = formula_engine.evaluate(formula, variables)
# result = 250.0
```

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Multi-tenant data leak | Row-level security on ALL tables via org_id + Supabase RLS policies |
| Authentication bypass | Supabase JWT validation on every API request via middleware |
| Permission escalation | Centralized permission_service checks role before every write operation |
| File access | Signed URLs with expiration for all storage access; org-scoped storage paths |
| SQL injection | Parameterized queries via ORM (SQLAlchemy/SQLModel); no raw SQL concatenation |
| Rate limiting | Per-user and per-IP rate limits on all API endpoints |
| Webhook tampering | Signature verification on DodoPayments webhooks |
| CORS | Strict CORS policy allowing only the Contruo frontend origin |

---

## Environment Configuration

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx

# Liveblocks
LIVEBLOCKS_SECRET_KEY=xxx

# DodoPayments
DODOPAYMENTS_API_KEY=xxx
DODOPAYMENTS_WEBHOOK_SECRET=xxx
DODOPAYMENTS_ENVIRONMENT=test_mode
DODOPAYMENTS_SUBSCRIPTION_PRODUCT_ID=xxx
DODOPAYMENTS_SEAT_ADDON_ID=xxx

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_PROVIDER=resend
EMAIL_API_KEY=xxx
EMAIL_FROM=noreply@contruo.com

# App
APP_URL=https://app.contruo.com
API_URL=https://api.contruo.com
ENVIRONMENT=production  # development | staging | production
```

---

## Notes

- The architecture separates **real-time** (Liveblocks) from **persistence** (PostgreSQL). This is deliberate: Liveblocks handles the hard parts of conflict resolution and presence, while PostgreSQL is the reliable source of truth. If Liveblocks goes down temporarily, the database still has all data.
- The Celery task queue is essential for PDF processing -- a 200-page construction PDF can take 30+ seconds to process. Users shouldn't wait on a loading spinner; they should see pages appear as they're processed.
- The `org_id` column on every table is the single most important security decision. It enables row-level security and ensures no query can ever accidentally cross organization boundaries.
- The event_log table is populated from day one even though the Activity Log UI ships later. This is zero-regret infrastructure: the storage cost is minimal, the write overhead is negligible, and the data is invaluable for debugging, analytics, and the future activity log feature.
- The API is designed with the future public API (P2) in mind. Consistent endpoint naming, versioned routes, and structured response formats mean the internal API can be exposed externally with minimal changes.
