# Contruo Backend

FastAPI + PostgreSQL (Supabase) + Celery + Liveblocks. See [docs/architecture/backend.md](../docs/architecture/backend.md) for the full stack walkthrough.

---

## Local development

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env  # then fill in real values
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Run the test suite:

```powershell
pytest                                  # full suite
pytest tests/unit/test_ai_run_service.py # one file
```

---

## Celery workers

The API enqueues background work onto Celery. Two queues exist:

| Queue | Tasks | Run with |
|---|---|---|
| `celery` (default) | PDF processing, exports, emails, the `test_task` smoke task | `celery -A app.tasks.celery_app worker -Q celery -n default-worker@%h` |
| `ai_pipeline` | AI Auto-Takeoff stage chain (Sprint AI-01+) | `celery -A app.tasks.celery_app worker -Q ai_pipeline -n ai-worker@%h` |

The `ai_pipeline` queue is isolated so heavy AI workloads don't starve PDF processing or exports. In dev, run both processes side-by-side; in production, scale the AI worker independently of the default worker.

---

## Environment variables

`backend/.env.example` has the canonical list with comments. The most commonly-edited groups:

### Core

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | -- | Supabase connection string (asyncpg). |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + backend. |
| `SUPABASE_URL` | -- | Project URL. |
| `SUPABASE_SERVICE_ROLE_KEY` | -- | Server-side Supabase admin key. |
| `LIVEBLOCKS_SECRET_KEY` | -- | Required for collaboration auth + AI run broadcasts. |

### AI Auto-Takeoff (Sprint AI-01 + AI-02)

Provider selection is a config swap, not a code change. Defaults are the provider+model the AI track was designed against; override per environment.

| Variable | Default | Notes |
|---|---|---|
| `AI_VISION_PROVIDER` | `anthropic` | One of `anthropic`. |
| `AI_VISION_MODEL` | `claude-sonnet-4-5` | Anthropic model id. |
| `AI_EMBEDDING_PROVIDER` | `openai` | One of `openai`. |
| `AI_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI model id (1536-dim). |
| `AI_LLM_PROVIDER` | `anthropic` | One of `anthropic`. |
| `AI_LLM_MODEL` | `claude-sonnet-4-5` | Anthropic model id. |
| `ANTHROPIC_API_KEY` | -- | Required when an Anthropic provider is selected. |
| `OPENAI_API_KEY` | -- | Required when an OpenAI provider is selected. |
| `AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG` | `5000` | 24h per-org spend cap. Abuse cutoff, not a customer-facing usage cap. Set `0` to disable. |

#### AI-02 (title block + classification)

| Variable | Default | Notes |
|---|---|---|
| `AI_TESSERACT_CMD` | -- | Path to the `tesseract` binary for OCR fallback. Leave empty to auto-resolve from `PATH`; when no binary is found, the OCR fallback is skipped (text-layer reads still work). |
| `AI_TITLE_BLOCK_CONFIDENCE_THRESHOLD` | `0.7` | Detection confidence below this pauses the run for manual title-block confirmation. |
| `AI_CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.7` | Lexical-classification confidence below this escalates *interesting* sheets to the vision model (cover/index/spec sheets never escalate). |
| `AI_VISION_CLASSIFY_BATCH_SIZE` | `6` | Number of sheets sent in a single vision classification batch. |
| `AI_ANTHROPIC_VISION_INPUT_PER_1K_CENTS` | `0.3` | Per-1K-input-token cost (cents) used for vision-call cost telemetry. |
| `AI_ANTHROPIC_VISION_OUTPUT_PER_1K_CENTS` | `1.5` | Per-1K-output-token cost (cents) used for vision-call cost telemetry. |

OCR is local CPU and does **not** count against the spend cap. Vision calls are tracked via `with_cost_tracking` and billed against the active `ai_runs` row.

See [docs/architecture/ai-pipeline.md](../docs/architecture/ai-pipeline.md) for how the providers are wired and how cost attribution works.

---

## Database migrations

Alembic. Create a new migration:

```powershell
alembic revision -m "describe the change"
```

Apply / rollback:

```powershell
alembic upgrade head
alembic downgrade -1
```

Every new table must:

- Have an `org_id uuid NOT NULL` column referencing `organizations.id`.
- Have an `ix_<table>_org_id` index.
- Enable RLS with the canonical `org_id = (SELECT org_id FROM users WHERE id = auth.uid())` policy.

See `migrations/versions/005_conditions_and_measurements.py` for the reference pattern, and `014_ai_title_block_and_pause.py` for the most recent example.
