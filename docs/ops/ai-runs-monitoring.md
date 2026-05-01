# AI Runs Monitoring

> **Status:** Sprint AI-01 -- query templates only. Dashboards (Grafana / Looker / Metabase) are wired up in a later sprint.

This doc collects copy-pasteable SQL templates that ops uses to monitor the AI Auto-Takeoff pipeline. All queries assume Postgres + the schema introduced by migration `013_ai_runs_layer_and_extractions`.

For the architecture see [docs/architecture/ai-pipeline.md](../architecture/ai-pipeline.md).

---

## Health metrics

### Runs per day per org

```sql
SELECT
  date_trunc('day', created_at) AS day,
  org_id,
  count(*)                                    AS runs,
  count(*) FILTER (WHERE status = 'completed') AS completed,
  count(*) FILTER (WHERE status = 'failed')    AS failed,
  count(*) FILTER (WHERE status = 'running')   AS still_running
FROM ai_runs
WHERE created_at >= now() - interval '14 days'
GROUP BY 1, 2
ORDER BY day DESC, runs DESC;
```

### Median + p95 cost per completed run

```sql
SELECT
  date_trunc('day', finished_at) AS day,
  count(*)                                         AS completed_runs,
  percentile_cont(0.5)  WITHIN GROUP (ORDER BY cost_cents) AS p50_cents,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY cost_cents) AS p95_cents,
  max(cost_cents)                                  AS max_cents
FROM ai_runs
WHERE status = 'completed'
  AND finished_at >= now() - interval '14 days'
GROUP BY 1
ORDER BY 1 DESC;
```

### Stage failure rate

```sql
WITH stage_outcomes AS (
  SELECT
    id,
    status,
    jsonb_object_keys(summary_jsonb -> 'stages') AS stage,
    summary_jsonb -> 'stages' -> jsonb_object_keys(summary_jsonb -> 'stages') -> 'error' IS NOT NULL
      AS errored
  FROM ai_runs
  WHERE created_at >= now() - interval '7 days'
)
SELECT
  stage,
  count(*)                                AS executions,
  count(*) FILTER (WHERE errored)         AS errors,
  ROUND(100.0 * count(*) FILTER (WHERE errored) / NULLIF(count(*), 0), 2) AS error_pct
FROM stage_outcomes
GROUP BY stage
ORDER BY error_pct DESC NULLS LAST;
```

### Per-stage median duration

```sql
SELECT
  stage,
  percentile_cont(0.5)  WITHIN GROUP (ORDER BY duration_ms) AS p50_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,
  count(*) AS executions
FROM (
  SELECT
    id,
    key                          AS stage,
    (value ->> 'duration_ms')::int AS duration_ms
  FROM ai_runs,
       jsonb_each(summary_jsonb -> 'stages')
  WHERE created_at >= now() - interval '7 days'
) s
WHERE duration_ms IS NOT NULL
GROUP BY stage
ORDER BY p95_ms DESC;
```

### Cache hit rate per stage

```sql
SELECT
  stage,
  count(*)                                       AS executions,
  count(*) FILTER (WHERE cache_hit)              AS hits,
  ROUND(100.0 * count(*) FILTER (WHERE cache_hit) / NULLIF(count(*), 0), 2) AS hit_pct
FROM (
  SELECT
    key                          AS stage,
    (value ->> 'cache_hit')::bool AS cache_hit
  FROM ai_runs,
       jsonb_each(summary_jsonb -> 'stages')
  WHERE created_at >= now() - interval '7 days'
) s
GROUP BY stage
ORDER BY hit_pct DESC;
```

---

## Cost / abuse alerts

### Orgs approaching the daily circuit breaker (last 24h)

```sql
SELECT
  org_id,
  sum(cost_cents)                AS spent_cents,
  count(*)                       AS run_count,
  max(created_at)                AS last_run_at
FROM ai_runs
WHERE created_at >= now() - interval '24 hours'
GROUP BY org_id
ORDER BY spent_cents DESC
LIMIT 25;
```

Use this to spot orgs nearing the `AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG` cap before the 429 fires.

### Currently active runs

```sql
SELECT
  r.id,
  r.org_id,
  r.project_id,
  r.plan_id,
  r.status,
  r.started_at,
  EXTRACT(EPOCH FROM (now() - r.started_at)) AS running_for_seconds,
  r.summary_jsonb -> 'stages' AS stages_so_far
FROM ai_runs r
WHERE r.status IN ('queued', 'running')
ORDER BY r.created_at;
```

A run that has been `running` for more than ~5 minutes (in AI-01 the no-op chain finishes in well under 30s) is almost certainly stuck on a hung worker.

---

## Usage / acceptance signals

### Auto-accept rate

```sql
SELECT
  org_id,
  sum(items_total)         AS items,
  sum(items_accepted_auto) AS auto_accepted,
  ROUND(100.0 * sum(items_accepted_auto) / NULLIF(sum(items_total), 0), 2) AS auto_pct
FROM ai_runs
WHERE status = 'completed'
  AND finished_at >= now() - interval '30 days'
GROUP BY org_id
ORDER BY auto_pct DESC NULLS LAST;
```

### Provenance: AI vs user measurements

```sql
SELECT
  source,
  count(*)                                     AS measurements,
  count(DISTINCT project_id)                   AS projects,
  count(DISTINCT org_id)                       AS orgs
FROM measurements
GROUP BY source
ORDER BY measurements DESC;
```

---

## Cleanup / housekeeping

### Stale `ai_stage_cache` rows (no hit in 30 days)

```sql
SELECT count(*), pg_size_pretty(sum(pg_column_size(value_jsonb))) AS approx_bytes
FROM ai_stage_cache
WHERE last_accessed_at < now() - interval '30 days';
```

Wrap in a `DELETE` once we have a real prune policy. Until then, table size is bounded by org count * sheet count * stage count, which is small.
