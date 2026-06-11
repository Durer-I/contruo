# AI Auto-Takeoff Pipeline

> **Status:** Sprints AI-01, AI-02, AI-02b, and AI-03 shipped. Stage 2 (sheet classification) and Stage 3a (schedule + legend extraction) run for real. Title-block extraction lives outside the counted chain as a best-effort `pipeline_prep_auto_name` hook (Sprint AI-02b). Stage 3b (element detection) and Stage 4 (resolver + layer write) remain no-ops until AI-04 / AI-06+.
> **Stack:** Celery + dedicated `ai_pipeline` queue, PostgreSQL advisory locks, Liveblocks REST broadcasts, swappable model providers (Anthropic + OpenAI), Tesseract for OCR fallback, pdfplumber + PyMuPDF + PIL for schedule + legend extraction, Supabase Storage for legend symbol PNGs.

This doc describes the runtime shape of the AI Auto-Takeoff feature: how a user click becomes a multi-stage Celery DAG, how stages share state, how costs are attributed, and how the system protects itself from runaway spend or concurrent runs.

For the product spec see [features/ai/ai-auto-takeoff.md](../../features/ai/ai-auto-takeoff.md). For monitoring queries see [docs/ops/ai-runs-monitoring.md](../ops/ai-runs-monitoring.md). For the title-block / auto-name flow see [sprints/ai/sprint-ai-02b.md](../../sprints/ai/sprint-ai-02b.md). For the schedule + legend stage see [sprints/ai/sprint-ai-03.md](../../sprints/ai/sprint-ai-03.md).

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
                                       ┌──────────────────────────────────────────────────┐
                                       │ Celery worker on `ai_pipeline` queue             │
                                       │                                                  │
                                       │  pipeline_prep_auto_name (AI-02b, best-effort)   │
                                       │    └─ reextract_plan_titles_task (suppressed     │
                                       │       on failure; respects manual rename guard)  │
                                       │  start_ai_run                                    │
                                       │    └─ pg_try_advisory_lock(plan)                 │
                                       │    └─ status -> running                          │
                                       │    └─ broadcast ai_run.status_changed            │
                                       │  stage_classification    (AI-02)                 │
                                       │    └─ lexical pass + vision fallback             │
                                       │  stage_schedules_legends (AI-03)                 │
                                       │    ├─ schedule extractor on schedule sheets      │
                                       │    │  (lines_strict → lines → text → vision)     │
                                       │    │  + tag-column scorer (heuristic + LLM)      │
                                       │    └─ legend detector + extractor on legend      │
                                       │       sheets (5 scales × 4 rotations to Storage) │
                                       │  stage_element_detection (no-op AI-06+)          │
                                       │  stage_resolver_and_layer_write (no-op AI-04)    │
                                       │  finalize_ai_run                                 │
                                       │    └─ release lock                               │
                                       │    └─ status -> completed                        │
                                       │    └─ broadcast ai_run.status_changed            │
                                       └──────────────────────────────────────────────────┘
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

As of Sprint AI-03:

- **Pre-stage prep (`pipeline_prep_auto_name`)** -- **AI-02b.** Best-effort task that runs the same `reextract_plan_titles_task` body as the standalone "Auto-name sheets" button. Manual sheet renames are protected (`sheets.sheet_name_source = 'manual'`). Failures are logged + swallowed; the run still proceeds. Disabled when `AI_AUTO_NAME_ENABLED=false`. There is no `stage_title_block` in the counted chain — the prep hook is the only title-block work the worker performs.
- **Stage 2 (`stage_classification`)** -- **AI-02.** Lexical/regex pass over `sheets.sheet_name`, then escalates only the *low-lexical-confidence + interesting* bucket (e.g. floor plans whose names are unparseable) to a batched vision call. Cover/index/spec sheets never escalate. Result is stored on `sheets.discipline` / `sheets.sheet_type` / `sheets.classification_confidence` / `sheets.classification_method`.
- **Stage 3a (`stage_schedules_legends`)** -- **AI-03.** Two parallel sub-flows on the relevant subset of sheets:
  - **Schedules:** `ai_sheet_filter.select_schedule_sheets(sheets)` keyword-filters by `sheets.sheet_name` (`%schedule%`, etc.). For each match, `ai_schedule_extractor` walks `pdfplumber.lines_strict` -> `pdfplumber.lines` -> `pdfplumber.text` -> `AnthropicVisionModel.extract_structured` (vision fallback) until a quality-scored table comes back. `ai_tag_column.score_columns` then runs a 4-feature heuristic to tag each column (tag / description / quantity / dimension / material); the tag-column role gets an LLM tie-break (`get_schedules_llm`) when the score margin is below threshold. One row per schedule -> `extracted_schedules`.
  - **Legends:** `select_legend_sheets(sheets)` keyword-filters (`%legend%`, `%symbol%`, etc.). `ai_legend_detector` ports the standalone prototype (group rects by rounded `x0` / `x1` -> filter to the most common size -> drop rects with text inside -> find adjacent label) plus an additive multi-direction label search and per-symbol confidence scoring. For each accepted symbol, `ai_legend_extractor` renders the primary PNG, generates a 5-scales x 4-rotations variant grid via PIL transforms, uploads each variant to a deterministic Supabase Storage path (`{org_id}/legends/{plan_id}/{template_hash}_s{scale}_r{rotation}.png`), and writes one `extracted_legends` row + 20 `extracted_legend_variants` rows per symbol.
  - **Caching:** Per-sheet content-hash cache (`ai_stage_cache`, stages `schedules_v1` and `legends_v1`). Schedule cache stores serialized table + column metadata. Legend cache stores `template_hash` + `primary_storage_path` (no PNG bytes); on a hit, `persist_from_cached_metadata` re-inserts DB rows without re-rendering or re-uploading.
- **Stage 3b (`stage_element_detection`)** -- **no-op** until AI-06+.
- **Stage 4 (`stage_resolver_and_layer_write`)** -- **no-op** until AI-04 / AI-05.

Stages 3b and 4 are filled in by later sprints without touching the chain wiring.

### Pause / resume

**Not present.** The original AI-02 had Stage 1 pause `ai_runs.status` to `'awaiting_title_block'` on low-confidence bbox detection. The pause path and the resume endpoint were both removed when the AI-02 detector was reset, and the AI-02b auto-name redesign chose not to re-introduce them (auto-name runs as a non-blocking pre-prep hook instead). The `ai_runs.status` column stays widened to `VARCHAR(40)` (migration `014`) so a future flow can re-introduce a pause-style status without a new migration.

### Per-sheet groundwork

The per-sheet pure-function pattern (a stage body that loops one open `fitz.Document` over each sheet, with content-hash caching and per-sheet failure isolation) is the working template across Stages 2 and 3a, and is the canonical shape for AI-06+. Stage 3a (`_stage_schedules_legends_body`) is the most complete current example: it iterates schedule-eligible sheets, then legend-eligible sheets, swallows per-sheet exceptions into `summary_jsonb.errors`, and emits per-stage cache-hit + cost counters into `summary_jsonb.schedules_legends`.

---

## Provider abstraction

Three protocols cover every external model call in the pipeline. Swapping providers is a config change, never a code change.

| Protocol | Use cases | Default provider | Default model |
|---|---|---|---|
| `VisionModel` | Sheet classification fallback (Stage 2), schedule extraction vision fallback (Stage 3a), ambiguous-symbol regions (AI-06+) | `anthropic` | `claude-sonnet-4-5` |
| `EmbeddingModel` | Condition resolver text vectorization (AI-04) | `openai` | `text-embedding-3-small` (1536-dim) |
| `LLMModel` | Title-block cleanup (AI-02b), schedule tag-column tie-break (AI-03), condition name summarization, assembly enrichment | `anthropic` (default `LLMModel`) / `openai` (title-block + schedules) | `claude-sonnet-4-5` / `gpt-4o-mini` |

Factories that read active settings at call time:

- `get_vision_model()` — sheet classification + Stage 3a vision fallback.
- `get_embedding_model()` — AI-04.
- `get_llm_model()` — generic Anthropic LLM.
- `get_title_block_llm()` (AI-02b) — defaults to OpenAI `gpt-4o-mini`; gated by `AI_TITLE_BLOCK_LLM_PROVIDER`.
- `get_schedules_llm()` (AI-03) — defaults to OpenAI `gpt-4o-mini`; gated by `AI_SCHEDULES_LLM_PROVIDER` / `AI_SCHEDULES_LLM_MODEL`.

`AnthropicVisionModel.extract_structured(image_bytes, schema, prompt)` is the structured-output entry point used by Stage 3a's vision fallback (was a stub before AI-03).

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

Stage 3a (AI-03) caches at the per-sheet granularity under two stage keys:

- `schedules_v1` — the cached payload is the serialized list of extracted tables (rows, headers, column-role indices, extraction strategy). On a hit, `extracted_schedules` rows are re-inserted directly with no PDF re-parse.
- `legends_v1` — the cached payload is the list of `(template_hash, primary_storage_path)` pairs for accepted symbols. On a hit, `ai_legend_extractor.persist_from_cached_metadata` re-inserts the `extracted_legends` + `extracted_legend_variants` rows without re-rendering or re-uploading PNGs (the same Storage objects are still pinned because their paths are deterministic on `template_hash`).

Cache writes use a unique constraint and tolerate the race -- if two workers compute the same payload simultaneously, the second write loses the unique-key conflict, rolls back, and the next read finds the first row.

---

## Per-plan advisory lock

Concurrent runs on the same plan are rejected at two layers:

1. **API layer (`assert_no_active_run_for_plan`):** Before INSERT, look for any `queued` or `running` run on the same `(org_id, plan_id)`. Return `409 AI_RUN_LOCKED` if one exists.
2. **Worker layer (`acquire_sheet_lock_sync`):** `pg_try_advisory_lock(hash(plan_id))` at the start of `start_ai_run`. The lock auto-releases when the session closes, so a worker crash never leaves a permanent lock. Failure here transitions the run to `failed` immediately.

There is currently no in-pipeline pause path (the AI-02 `awaiting_title_block` pause was removed when the detector was reset; see [Pause / resume](#pause--resume)). The AI-02b auto-name flow runs as a non-blocking pre-prep hook rather than re-introducing a pause.

The standalone `reextract_plan_titles_task` (AI-02b's "Auto-name sheets" button) acquires the same plan-scoped advisory lock so it cannot race a concurrent AI run; lock-busy retries with backoff up to ~1 minute, then fails the task.

The pipeline still uses one plan-scoped lock per run. When AI-06+ parallelizes detection by sheet, the key will move to `(plan_id, sheet_id)`.

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

The `ai_runs.summary_jsonb` shape (post-AI-03) is:

```json
{
  "stages": {
    "classification":    { "duration_ms": 820,  "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "schedules_legends": { "duration_ms": 4210, "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "element_detection": { "duration_ms": 0,    "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "resolver_and_layer_write": { "duration_ms": 0, "cache_hit": false, "started_at": "...", "finished_at": "..." },
    "finalize":          { "duration_ms": 12,   "cache_hit": false, "started_at": "...", "finished_at": "..." }
  },
  "classification": {
    "by_discipline": { "architectural": 18, "structural": 6, "general": 2 },
    "by_sheet_type": { "plan": 14, "section": 4, "detail": 6, "cover": 2 },
    "low_confidence_count": 1
  },
  "schedules_legends": {
    "schedule_sheets_eligible": 4,
    "schedule_sheets_processed": 4,
    "schedules_extracted": 6,
    "schedules_cache_hits": 1,
    "schedules_vision_fallbacks": 0,
    "tag_column_llm_tiebreaks": 2,
    "legend_sheets_eligible": 2,
    "legend_sheets_processed": 2,
    "legend_symbols_extracted": 18,
    "legend_variants_written": 360,
    "legends_cache_hits": 0,
    "errors": []
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

`summary_jsonb.stages.title_block` is intentionally absent — there is no `stage_title_block` in the counted chain. The `pipeline_prep_auto_name` hook (AI-02b) is best-effort and not represented as a counted stage; its work surfaces via the `sheets.auto_named` Liveblocks broadcast and the per-method counters in `ReextractCounters`. `summary_jsonb.pause` is unused.

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

## Out of scope for AI-03

The condition resolver (AI-04), the AI Layer overlays + review panel (AI-05), and element detection itself (AI-06 through AI-08). `stage_element_detection` and `stage_resolver_and_layer_write` remain no-op bodies that those sprints will fill in without touching the chain wiring.

Optional AI-03 follow-ons: a "Set legend region" manual fallback for sheets where `ai_legend_detector` returns nothing useful (AI-03b), and the sheet classifier accuracy fix + image-only legend OCR + non-rectangular symbol shapes (AI-03c). Both are gated on real-data evidence rather than scheduled today.

The customer-facing UI for inspecting `extracted_schedules` / `extracted_legends` is intentionally limited to the owner+admin internal debug page (`/internal/ai/runs/[runId]/extractions`). The customer-facing review surface lands with AI-05 (the AI Layer overlay).
