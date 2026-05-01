# Sprint AI-01: Foundations & Infrastructure

> **Track:** AI / Auto-Takeoff
> **Duration:** 2 weeks
> **Status:** Complete (2026-04)
> **Depends On:** MVP shipped (Sprints 01-16)

## Sprint Goal

Lay the architectural foundation for AI Auto-Takeoff: new database tables, a dedicated Celery queue, model/provider abstraction interfaces, content-hash caching, per-sheet AI lock, and a manual "Run Auto-Takeoff" trigger that runs an empty pipeline end-to-end. At the end of this sprint, no real detections happen yet, but the user can click a button, see an `ai_runs` row created, watch it complete, and observe a clean run record with cost/timing telemetry.

This is the unglamorous-but-critical sprint. Every later AI sprint depends on what we build here.

---

## Tasks

### 1. Database Schema

- [ ] Migration: create `ai_runs` table
  - `id`, `org_id`, `plan_id`, `triggered_by` (user_id), `status` (`queued`, `running`, `completed`, `failed`, `cancelled`)
  - `model_versions` JSONB (vision/embedding model snapshot for reproducibility)
  - `started_at`, `finished_at`
  - `cost_cents`, `tokens_used`, `items_total`, `items_accepted_auto`, `items_pending`, `items_low_confidence`
  - `summary_jsonb` (per-stage timings, per-condition counts, errors)
  - RLS by `org_id`, FK to `plans`
- [ ] Migration: create `ai_layer_items` table
  - `id`, `org_id`, `ai_run_id`, `sheet_id`, `condition_id` (nullable until resolver runs), `measurement_type`, `geometry` JSONB
  - `confidence`, `source_stage`, `status` (`pending`, `accepted_auto`, `accepted_user`, `rejected`)
  - `metadata_jsonb` (e.g., matched legend label, source template)
  - RLS by `org_id`
- [ ] Migration: create `extracted_schedules` table (one row per detected schedule table)
  - `id`, `org_id`, `ai_run_id`, `sheet_id`, `bbox_pdf` JSONB, `tag_column_index`, `extracted_table_jsonb`, `extraction_method` (`pdfplumber_lines`, `pdfplumber_text`, `vision`)
- [ ] Migration: create `extracted_legends` table (one row per detected legend symbol)
  - `id`, `org_id`, `ai_run_id`, `sheet_id`, `bbox_pdf` JSONB, `label`, `template_storage_path`, `template_hash`, `extraction_method`
- [ ] Migration: create `ai_stage_cache` table
  - Cache key on `(content_hash, stage, model_version)`, value as JSONB blob, TTL on read
- [ ] Migration: add columns to `measurements`
  - `source` VARCHAR(20) NOT NULL DEFAULT `'user'` (`'user'` | `'ai'`)
  - `ai_run_id` UUID nullable, FK to `ai_runs`
  - Index on `(ai_run_id)` for bulk-by-run queries
- [ ] Migration: add columns to `conditions`
  - `source` VARCHAR(20) NOT NULL DEFAULT `'user'` (`'user'` | `'template_clone'` | `'ai_created'` | `'imported'`)
  - `source_template_id` UUID nullable, FK to `condition_templates`
  - `source_ai_run_id` UUID nullable, FK to `ai_runs`
- [ ] Migration: add columns to `sheets`
  - `discipline` VARCHAR(40) nullable (architectural, structural, mechanical, plumbing, electrical, fire_protection, civil, other)
  - `sheet_type` VARCHAR(40) nullable (cover, index, plan, schedule, legend, detail, spec, elevation, section, other)
  - `classification_confidence` FLOAT nullable
  - `classification_method` VARCHAR(20) nullable (`lexical`, `vision`)

### 2. Celery AI Queue

- [ ] Add new Celery queue `ai_pipeline` in `backend/app/tasks/celery_app.py`
- [ ] Create `backend/app/tasks/ai_pipeline.py` with placeholder task chain skeleton:
  - `start_ai_run` -> `stage_title_block` -> `stage_classification` -> `stage_schedules_legends` -> `stage_element_detection` -> `stage_resolver_and_layer_write` -> `finalize_ai_run`
  - Stages are no-ops in this sprint; they exist as task functions for future sprints to fill in.
- [ ] Worker config: separate worker process for the AI queue (different `--queues=ai_pipeline` flag) so heavy AI workloads don't starve PDF processing or exports.

### 3. Provider Abstraction Layer

- [ ] Create `backend/app/services/ai_models.py` with three interfaces:
  - `VisionModel` (methods: `classify_image`, `extract_structured`, `analyze_region`)
  - `EmbeddingModel` (methods: `embed_text`, `embed_batch`)
  - `LLMModel` (methods: `summarize`, `structured_output`)
- [ ] Concrete implementations:
  - `AnthropicVisionModel` (default, current Claude Sonnet)
  - `OpenAIEmbeddingModel` (default, `text-embedding-3-small`)
  - `AnthropicLLMModel` (default for structured-text tasks)
- [ ] Factory: `get_vision_model()`, `get_embedding_model()`, `get_llm_model()` reading from `config.py`
- [ ] Add config keys to `backend/app/config.py`:
  - `AI_VISION_PROVIDER` (default `anthropic`)
  - `AI_VISION_MODEL` (default current Sonnet model id)
  - `AI_EMBEDDING_PROVIDER` (default `openai`)
  - `AI_EMBEDDING_MODEL` (default `text-embedding-3-small`)
  - `AI_LLM_PROVIDER` / `AI_LLM_MODEL`
  - `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
  - `AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG` (default high default, e.g. $50)
- [ ] Cost wrapper: every `VisionModel`/`EmbeddingModel`/`LLMModel` call records `cost_cents` and `tokens_used` to the active `ai_runs` row via a `with_cost_tracking(ai_run_id)` context manager.

### 4. Content-Hash Caching

- [ ] Hash helper in `backend/app/services/ai_cache.py`:
  - `compute_sheet_content_hash(sheet)` -> SHA-256 of relevant inputs (PDF bytes for sheet, scale calibration, model version)
  - `cache_get(content_hash, stage, model_version)` / `cache_put(...)`
- [ ] Integrate cache check at the top of every Celery stage task (skip if cached, write on completion).

### 5. Per-Sheet AI Lock

- [ ] Implement Postgres advisory lock in `backend/app/services/ai_run_service.py`:
  - `acquire_sheet_lock(plan_id, sheet_id, ai_run_id)` -> raises if another `ai_runs` row is `running` for same `(plan_id, sheet_id)`
  - `release_sheet_lock(...)` on stage completion / failure
- [ ] Surface lock state in `ai_runs.summary_jsonb` for debugging.

### 6. Cost & Abuse Circuit Breaker

- [ ] In `backend/app/services/ai_run_service.py`, before queueing a new run:
  - Sum `cost_cents` of org's `ai_runs` in the last 24h.
  - If above `AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG`, raise an internal error and log a structured alert.
- [ ] Internal admin endpoint (placeholder in this sprint) to view per-org daily cost: `GET /internal/ai/cost-by-org` (RBAC-protected, not exposed to customers).

### 7. Manual Trigger (End-to-End Empty Run)

- [ ] API: `POST /api/v1/projects/{project_id}/ai/runs`
  - Body: `{ "plan_id": "...", "scope": "full_plan" }` (scope reserved for future per-sheet runs)
  - Creates `ai_runs` row with status `queued`, returns `{ ai_run_id }`
  - Enqueues `start_ai_run` task
- [ ] API: `GET /api/v1/projects/{project_id}/ai/runs/{ai_run_id}` -> run status, summary
- [ ] API: `GET /api/v1/projects/{project_id}/ai/runs?status=...&limit=...` -> list runs
- [ ] Frontend: minimal trigger UI
  - "Run Auto-Takeoff" button in the plan viewer toolbar (visible to Estimator+ roles)
  - Disabled state when an `ai_runs` row is currently `running` for the plan
  - Lightweight status pill: "Idle" | "Queued" | "Running stage 3 of 6" | "Completed" | "Failed"
- [ ] Liveblocks integration: broadcast `ai_run.status_changed` events so other users in the project see the pill update live.

### 8. Telemetry & Observability

- [ ] Structured logging on every AI task: `(ai_run_id, stage, duration_ms, cost_cents, tokens_used)`
- [ ] Sentry/error tracking integration for AI task failures (separate tag `ai_pipeline`)
- [ ] Internal dashboard query templates (Grafana/Looker placeholder doc in `docs/ops/ai-runs-monitoring.md`):
  - Runs per day per org
  - Median cost per run
  - Stage failure rates

### 9. Documentation

- [ ] `docs/architecture/ai-pipeline.md` -- new doc covering the Celery DAG, model abstraction, caching, lock behavior, cost tracking
- [ ] Update `backend/README.md` with the new env vars and how to run the AI worker locally

---

## Acceptance Criteria

- [ ] All migrations apply cleanly on a fresh dev DB.
- [ ] An estimator can click "Run Auto-Takeoff" on a plan with the AI worker running and see an `ai_runs` row created and complete (with no real detections, just empty stages) within 30s.
- [ ] Concurrent click attempts on the same plan/sheet are rejected with a clear error.
- [ ] Cost tracking records zero cents on the empty run (no model calls happened) and the row's `summary_jsonb` shows per-stage timings.
- [ ] Vision and embedding models can be swapped via env var without code changes.
- [ ] Liveblocks broadcasts the run status changes; another user in the same project sees the status pill update live.
- [ ] All Sprint 01-16 tests still pass; new sprint adds tests for the run lifecycle, the lock, and the cost circuit breaker.

---

## Out of Scope (for later AI sprints)

- Title block detection -> AI-02
- Sheet classification -> AI-02
- Schedule / legend extraction -> AI-03
- Condition resolver -> AI-04
- AI Layer UI overlays + review panel -> AI-05
- Symbol / wall / room / hatch detection -> AI-06, AI-07, AI-08

---

## Key References

- [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md) -- Stage 6 (provenance), Cost & Throttling, Real-Time Collaboration Integration
- [features/ai/ai-element-recognition.md](../../features/ai/ai-element-recognition.md) -- Coordinate System and Output Contract
- [features/ai/ai-quantity-suggestions.md](../../features/ai/ai-quantity-suggestions.md) -- Embedding cache
- [docs/architecture/backend.md](../../docs/architecture/backend.md) -- Celery patterns, RLS conventions
