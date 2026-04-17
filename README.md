# Contruo

Online SaaS platform for construction estimators to create, edit, and manage takeoffs with real-time multi-user collaboration.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js + React + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL via Supabase (with Row-Level Security) |
| Auth | Supabase Auth |
| Real-Time | Liveblocks |
| Task Queue | Celery + Redis |
| Payments | DodoPayments |

## Project Structure

```
contruo/
├── frontend/          # Next.js app
├── backend/           # FastAPI app
├── docs/              # Architecture, design system, testing strategy
├── features/          # Feature specifications
├── sprints/           # Sprint plans and roadmap
├── docker-compose.yml # Local dev services (Redis, Postgres)
└── .github/workflows/ # CI/CD pipelines
```

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (for Redis and local Postgres)

### 1. Clone and configure

```bash
git clone <repo-url>
cd contruo
cp .env.example .env
# Edit .env with your Supabase and service credentials
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts Redis (port 6379) and PostgreSQL (port 5432).

### 3. Backend setup

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database URL

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000 with Swagger docs at http://localhost:8000/docs.

### 4. Frontend setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Edit .env.local with your Supabase public keys

npm run dev
```

The frontend will be available at http://localhost:3000.

### 5. Celery worker (optional for Sprint 01)

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
celery -A app.tasks.celery_app worker --loglevel=info --pool=threads --concurrency=4
```

## Development

### Running tests

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend
cd frontend
npm run lint
npx tsc --noEmit
```

### Database migrations

```bash
cd backend
# Create a new migration
alembic revision --autogenerate -m "description"
# Apply migrations
alembic upgrade head
# Rollback one step
alembic downgrade -1
```

## Key Documentation

- [Backend Architecture](docs/architecture/backend.md)
- [Frontend Architecture](docs/architecture/frontend.md)
- [Design System](docs/design/design-system.md)
- [Screen Layouts](docs/design/screen-layouts.md)
- [Testing Strategy](docs/testing-strategy.md)
- [Sprint Roadmap](sprints/roadmap.md)
