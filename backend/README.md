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

The worker runs best-effort title-block auto-name on the plan immediately before the counted pipeline stages (same path as Auto-name sheets; failures are logged and the run still proceeds when `AI_AUTO_NAME_ENABLED` is on).

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

#### AI-02b (auto-name sheets)

The "Auto-name sheets" button in the plan viewer runs a standalone Celery task (`ai_pipeline.reextract_plan_titles`) that reads each sheet's title-block region, extracts `sheet_name` + `sheet_number`, and writes them back. Manual renames (`sheets.sheet_name_source = 'manual'`) are always preserved.

| Variable | Default | Notes |
|---|---|---|
| `AI_AUTO_NAME_ENABLED` | `true` | Master kill-switch. `false` makes the API endpoint return `503 AUTO_NAME_DISABLED` and the frontend hides the button. |
| `AI_TITLE_BLOCK_BOX_WIDTH_PTS` | `350.0` | Width (PDF user-space points) of the bottom-right corner box scanned for title-block text. |
| `AI_TITLE_BLOCK_BOX_HEIGHT_PTS` | `350.0` | Height of that corner box. |
| `AI_TITLE_BLOCK_CLIP_DPI` | `200` | DPI for the OCR-fallback render. 200 is the sweet spot for the 6-8pt fonts typical of title blocks. |
| `AI_TITLE_BLOCK_LLM_MIN_CONFIDENCE` | `0.7` | Heuristic confidence below this (or any null field) escalates to the LLM cleanup pass. |
| `AI_TITLE_BLOCK_LLM_PROVIDER` | `openai` | Decoupled from `AI_LLM_PROVIDER`; the title-block parser uses OpenAI strict-JSON mode regardless of the global LLM choice. |
| `AI_TITLE_BLOCK_LLM_MODEL` | `gpt-4o-mini` | OpenAI model id for the cleanup pass. |
| `AI_OPENAI_LLM_INPUT_PER_1K_CENTS` | `0.015` | Per-1K-input-token cost (cents) for OpenAI LLM cost telemetry. |
| `AI_OPENAI_LLM_OUTPUT_PER_1K_CENTS` | `0.06` | Per-1K-output-token cost. |
| `AI_OPENAI_LLM_TIMEOUT_S` | `20.0` | Per-call hard timeout. |
| `AI_OPENAI_LLM_MAX_RETRIES` | `2` | SDK-level retries on transient OpenAI errors. |

**`OPENAI_API_KEY` is required on the worker process** (not just the API process) when the title-block LLM pass is enabled with the `openai` provider. The key is read lazily on first call, so an unset key produces a clean per-sheet `llm_failed` counter rather than crashing the task -- the heuristic answer is still written.

#### AI-03 (schedule + legend extraction)

Stage 3a of the AI Auto-Takeoff pipeline. Schedule and legend sheets are filtered by `sheet_name` keyword (matches the prototype in `AI/controller/title.py`), then pdfplumber extracts schedule tables (heuristic-first: `lines_strict` -> `lines` -> `text` -> vision fallback). Legend symbols use the algorithm from `AI/controller/legends.py` (rect grouping + right-adjacent labels), then an optional OpenAI strict-JSON pass drops false-positive rows (same intent as the commented GPT block in that script). Each detected symbol is cropped at multiple scales / rotations and stored in Supabase Storage so AI-06's symbol detector can template-match without re-rendering at match time.

| Variable | Default | Notes |
|---|---|---|
| `AI_SCHEDULES_LLM_PROVIDER` | `openai` | LLM provider for the tag-column / description-column tie-break. Decoupled from `AI_LLM_PROVIDER` for the same reason as the title-block LLM. |
| `AI_SCHEDULES_LLM_MODEL` | `gpt-4o-mini` | Model id for the schedule LLM. Strict-JSON schema mode is used. |
| `AI_SCHEDULE_VISION_DPI` | `250` | DPI for the vision fallback render of a lineless schedule. Matches `AI/controller/find_tables.py`. |
| `AI_SCHEDULE_TABLE_MIN_QUALITY` | `0.55` | pdfplumber row-width-variance score below which a candidate counts as a real table. Higher = stricter. |
| `AI_TAG_COLUMN_LLM_MARGIN` | `0.15` | When the heuristic top score is within this margin of the runner-up, the LLM breaks the tie. |
| `AI_TAG_COLUMN_LLM_SKIP_ABOVE` | `0.85` | Heuristic scores above this are accepted without LLM regardless of margin. |
| `AI_LEGEND_CROP_DPI` | `300` | DPI for legend symbol PNG crops. AI-06's template matcher expects this. |
| `AI_LEGEND_MERGE_TOLERANCE` | `2.0` | pdfplumber rect grouping tolerance (pts); matches `AI/controller/legends.py` (`tolerance=2`). |
| `AI_LEGEND_CLEANUP_ENABLED` | `true` | When `false`, skips the GPT false-positive filter and uses raw prototype output only (no extra LLM cost). |
| `AI_LEGEND_CLEANUP_LLM_PROVIDER` | `openai` | Legend cleanup uses OpenAI strict JSON-schema mode (same stack as title-block / schedules). Non-OpenAI providers skip cleanup with a warning. |
| `AI_LEGEND_CLEANUP_LLM_MODEL` | `gpt-4o-mini` | Model id for legend cleanup. |
| `AI_LEGEND_MIN_CONFIDENCE` | `0.6` | **Unused** by the current prototype-based detector (candidates use confidence `1.0`). Kept for forward compatibility. |
| `AI_LEGEND_SYMBOL_MIN_PTS` | `8.0` | **Unused** by the detector; the prototype uses a fixed 16 pt minimum. |
| `AI_LEGEND_SYMBOL_MAX_PTS` | `220.0` | **Unused** by the prototype detector. |
| `AI_LEGEND_LABEL_LLM_MIN_CONFIDENCE` | `0.6` | Reserved for future OCR-label cleanup; not used on the text-layer prototype path. |

`AI_LEGEND_VARIANT_SCALES` and `AI_LEGEND_VARIANT_ROTATIONS` are defined in code for a future multi-scale template grid (AI-06). Stage 3a only persists the primary (1.00x / 0°) PNG per symbol; the table `extracted_legend_variants` is unused until that work lands.

The Stage 3a output (rows in `extracted_schedules` and `extracted_legends` with one primary template PNG per symbol in storage) feeds AI-04 (resolver) and future AI-06 (symbol detector). Re-runs on unchanged sheets hit `ai_stage_cache` and cost zero.

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
