# AI Auto-Takeoff Pipeline

> **Status:** Sprint AI-02 (sheet classification, Stage 2) shipped. Stage 1 (title block) is a deliberate **no-op** until [Sprint AI-02b](../../sprints/ai/sprint-ai-02b.md) lands the redesigned manual-bbox flow. Stages 3–5 remain no-ops until AI-03 onward.
> **Stack:** Celery + dedicated `ai_pipeline` queue, PostgreSQL advisory locks, Liveblocks REST broadcasts, swappable model providers (Anthropic + OpenAI), Tesseract for OCR fallback.

This doc describes the runtime shape of the AI Auto-Takeoff feature: how a user click becomes a multi-stage Celery DAG, how stages share state, how costs are attributed, and how the system protects itself from runaway spend or concurrent runs.

For the product spec see [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md). For monitoring queries see [docs/ops/ai-runs-monitoring.md](../ops/ai-runs-monitoring.md). For the title-block redesign see [sprints/ai/sprint-ai-02b.md](../../sprints/ai/sprint-ai-02b.md).

---

## End-to-end flow

```
┌────────────────────────────┐    POST /api/v1/projects/{id}/ai/runs
│ Plan viewer "Run AI" button│ ─────────────────────────────────────────┐
└────────────────────────────┘                                          │
                                                                        ▼
                                       ┌─────────────────────────────────────────┐
                                       │ FastAPI ai_runs.py                      │
                                       │   - check circuit breaker (24h cap)     │
                                       │   - reject if active run for plan (409) │
                                       │   - INSERT ai_runs status=queued        │
                                       │   - log_event("ai_run.created")         │
                                       │   - enqueue Celery chain                │
                                       └─────────────────────────────────────────┘
                                                                        │
                                                                        ▼
                                       ┌─────────────────────────────────────────┐
                                       │ Celery worker on `ai_pipeline` queue    │
                                       │                                         │
                                       │  start_ai_run                           │
                                       │    └─ pg_try_advisory_lock(plan)        │
                                       │    └─ status -> running                 │
                                       │    └─ broadcast ai_run.status_changed   │
                                       │  stage_title_block       (no-op AI-02b) │
                                       │  stage_classification    (AI-02)        │
                                       │    └─ lexical pass + vision fallback    │
                                       │  stage_schedules_legends (no-op AI-03)  │
                                       │  stage_element_detection (no-op AI-06+) │
                                       │  stage_resolver_and_layer_write (AI-04) │
                                       │  finalize_ai_run                        │
                                       │    └─ release lock                      │
                                       │    └─ status -> completed               │
                                       │    └─ broadcast ai_run.status_changed   │
                                       └─────────────────────────────────────────┘
                                                                        │
                                       ┌────────────────────────────────┘
                                       ▼
                                       Liveblocks REST `broadcast-event`
                                       fanned out to every browser in the
                                       project's collaboration room.
```

Each stage:

1. Reads its inputs from Postgres (sheet rows, prior-stage outputs).
2. Optionally checks the `ai_stage_cache` for a hit on `(content_hash, stage, model_version)`.
3. Sets the active `ai_run_id` ContextVar so any model call inside auto-attributes its cost.
4. Writes its outputs to Postgres (e.g. `ai_layer_items`, `extracted_schedules`).
5. Records a per-stage timing entry into `ai_runs.summary_jsonb["stages"][<stage>]`.
6. Broadcasts a `ai_run.status_changed` event to the project's Liveblocks room.

As of Sprint AI-02:

- **Stage 1 (`stage_title_block`)** -- **no-op.** The Celery task still runs (so the chain shape is preserved end-to-end and `summary_jsonb.stages.title_block` is still recorded with `duration_ms`), but its body delegates to `_noop_stage` and returns immediately. The original AI-02 cut (3-sheet bbox heuristic + per-sheet `extract_title_for_sheet` loop + low-confidence pause) was withdrawn after it failed on real plans; the redesign lives in [Sprint AI-02b](../../sprints/ai/sprint-ai-02b.md).
- **Stage 2 (`stage_classification`)** -- runs a lexical/regex pass over `sheets.sheet_name`, then escalates only the *low-lexical-confidence + interesting* bucket (e.g. floor plans whose names are unparseable) to a batched vision call. Cover/index/spec sheets never escalate. Result is stored on `sheets.discipline` / `sheets.sheet_type` / `sheets.classification_confidence` / `sheets.classification_method`.

Stages 3-5 remain no-ops and are filled in by later sprints without touching the chain wiring. Stage 1 is in the same posture until AI-02b lands.

### Pause / resume

**Removed.** The original AI-02 cut had Stage 1 transition `ai_runs.status` to `'awaiting_title_block'` on low-confidence bbox detection and resume via `POST /api/v1/projects/{pid}/ai/runs/{rid}/title-block`. Both the pause path and the resume endpoint were removed when the detector was reset:

- `ai_run_service.PAUSE_STATUS_AWAITING_TITLE_BLOCK`, `pause_run_for_title_block_sync`, and `resume_run_after_title_block` are gone.
- `confirm_title_block` and `build_partial_chain_after_title_block` are gone.
- `'awaiting_title_block'` is no longer a valid `AiRunStatus` value (frontend or backend).

The `ai_runs.status` column stays widened to `VARCHAR(40)` (migration `014`) so AI-02b can re-introduce a pause-style status without a new migration.

### Per-sheet groundwork

The per-sheet pure-function pattern (a stage body that loops one open `fitz.Document` over each sheet, with a sibling `@celery_app.task` registration so the same function can later be fanned out as a chord) is preserved as the template for AI-06+. Stage 1's prior implementation (`extract_title_for_sheet` + `per_sheet_extract_title_task`) was the first instance and was removed with the rest of the title-block code; it will return inside AI-02b.

---

## Provider abstraction

Three protocols cover every external model call in the pipeline. Swapping providers is a config change, never a code change.

| Protocol | Use cases | Default provider | Default model |
|---|---|---|---|
| `VisionModel` | Sheet classification fallback, lineless schedule extraction, ambiguous-symbol regions | `anthropic` | `claude-sonnet-4-5` |
| `EmbeddingModel` | Condition resolver text vectorization | `openai` | `text-embedding-3-small` (1536-dim) |
| `LLMModel` | Condition name summarization, assembly enrichment | `anthropic` | `claude-sonnet-4-5` |

All three are obtained via factory functions (`get_vision_model()`, `get_embedding_model()`, `get_llm_model()`) that read the active settings at call time.

### Cost attribution

Every concrete model call is wrapped in `with_cost_tracking()`. The wrapper reads two `ContextVar`s set at the top of each Celery stage:

- `_active_ai_run_id` -- the run to bill the cost against.
- `_sync_session_factory` -- the SQLAlchemy `sessionmaker` to write through.

When both are set, an `UPDATE ai_runs SET cost_cents = cost_cents + ?, tokens_used = tokens_used + ?` runs after each model call. When either is missing (unit tests, ad-hoc scripts, dev probes) the wrapper is a no-op -- this keeps tests free of side effects and prevents runtime crashes outside the worker.

A model snapshot (`{"vision": "anthropic:claude-sonnet-4-5", ...}`) is captured into `ai_runs.model_versions` at run start, so a cache hit or re-run can detect provider/model drift.

---

## Stage cache

Stage outputs are deterministic in their inputs, so we cache them in `ai_stage_cache` keyed by `(org_id, content_hash, stage, model_version)`.

`compute_sheet_content_hash(sheet, pdf_bytes=...)` produces a 64-char SHA-256 over:

- The sheet's PDF page bytes.
- Scale calibration (`scale_value`, `scale_unit`).
- Page geometry (`width_px`, `height_px`).
- Any `extra` inputs the stage cares about.

A cache hit short-circuits the stage body. The stage still records a timing entry with `cache_hit: true`, so re-run analytics show what fraction of the pipeline is "free".

Cache writes use a unique constraint and tolerate the race -- if two workers compute the same payload simultaneously, the second write loses the unique-key conflict, rolls back, and the next read finds the first row.

---

## Per-plan advisory lock

Concurrent runs on the same plan are rejected at two layers:

1. **API layer (`assert_no_active_run_for_plan`):** Before INSERT, look for any `queued` or `running` run on the same `(org_id, plan_id)`. Return `409 AI_RUN_LOCKED` if one exists.
2. **Worker layer (`acquire_sheet_lock_sync`):** `pg_try_advisory_lock(hash(plan_id))` at the start of `start_ai_run`. The lock auto-releases when the session closes, so a worker crash never leaves a permanent lock. Failure here transitions the run to `failed` immediately.

There is currently no in-pipeline pause path (the AI-02 `awaiting_title_block` pause was removed when the detector was reset; see [Pause / resume](#pause--resume)). When AI-02b reintroduces a pause-style status, this section will be updated to describe how the lock is held across the pause.

Sprint AI-02 still uses one plan-scoped lock per run. When AI-06+ parallelizes detection by sheet, the key will move to `(plan_id, sheet_id)`.

---

## Abuse circuit breaker

`AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG` (default `5000` = $50) is the 24h per-org spend cap. Before creating a new run, the API sums `cost_cents` across the org's runs in the last 24 hours and rejects with `429 AI_COST_LIMIT` if the cap is hit.

This is **abuse protection**, not a customer-facing usage cap. The default is intentionally far above any legitimate per-org daily cost. Setting it to `0` disables the check entirely (useful for ops debugging, never for production).

---

## Telemetry

Every stage emits a structured log line via `_log_ai_event`:

```
stage_completed ai_run_id=... stage=title_block duration_ms=42 cache_hit=False tag=ai_pipeline
```

Failures route through `_log_ai_failure` with the stage name and exception type. Sentry is not wired in AI-01; when it is, this is the single place to add `sentry_sdk.capture_exception`.

The `ai_runs.summary_jsonb` shape (post-AI-02, with Stage 1 as no-op) is:

```json
{
  "stages": {
    "title_block":       { "duration_ms": 0,    "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "classification":    { "duration_ms": 820,  "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "schedules_legends": { "duration_ms": 0,    "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "element_detection": { "duration_ms": 0,    "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "resolver_and_layer_write": { "duration_ms": 0, "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "finalize":          { "duration_ms": 12,   "cache_hit": false, "started_at": "...", "finished_at": "..." }
  },
  "classification": {
    "by_discipline": { "architectural": 18, "structural": 6, "general": 2 },
    "by_sheet_type": { "plan": 14, "section": 4, "detail": 6, "cover": 2 },
    "low_confidence_count": 1
  },
  "counters": {
    "stage_2_total_sheets": 26,
    "stage_2_lexical": 23,
    "stage_2_vision": 3,
    "stage_2_low_confidence": 1,
    "stage_2_cache_hits": 0
  },
  "lock_state": "released"
}
```

`summary_jsonb.title_block` and `summary_jsonb.counters.stage_1_*` are intentionally absent in the current chain (no Stage 1 work runs). They will return as part of AI-02b. `summary_jsonb.pause` is also unused — the only producer was the removed Stage 1 detector.

---

## Real-time collaboration integration

The Celery worker has no async loop and no Liveblocks WebSocket connection -- it broadcasts via the REST API instead. `liveblocks_service.broadcast_event_sync(room_id, event_type, data)` POSTs to `https://api.liveblocks.io/v2/rooms/{room}/broadcast-event`, and Liveblocks fans the event out to every connected client.

Broadcast failures are intentionally non-fatal: the run state is persisted in Postgres and the frontend polls as a backstop, so a missed broadcast just delays the UI update by one poll interval.

The frontend listens via `useEventListener` and merges the broadcast into a polling state from `useActiveAiRun`, giving every collaborator the same live status pill.

---

## Operational runbook

- **Start the AI worker:** `celery -A app.tasks.celery_app worker -Q ai_pipeline -n ai-worker@%h` (one process per machine; the queue isolates AI workloads from PDF/export).
- **Inspect a run's stages:** `SELECT id, status, cost_cents, summary_jsonb FROM ai_runs WHERE id = '...';`
- **Force-clear a stuck advisory lock:** advisory locks are session-scoped and disappear when the worker session closes. If a worker is hung, restarting the worker process releases its locks.
- **Disable AI for an org:** set `status = 'failed'` on any in-flight run for the org and kill the worker; future starts will succeed once you re-enable. (A formal "AI disabled" flag is a future sprint.)

---

## Out of scope for AI-02

Title-block detection / manual override (deferred to [AI-02b](../../sprints/ai/sprint-ai-02b.md)), schedule + legend extraction (AI-03), the condition resolver (AI-04), the AI Layer overlays + review panel (AI-05), and element detection itself (AI-06 through AI-08). Stages 1 and 3-5 in the chain still have no-op bodies that future sprints will fill in without touching the chain wiring.
