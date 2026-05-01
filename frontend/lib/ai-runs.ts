/**
 * AI Auto-Takeoff client (Sprint AI-01).
 *
 * Wraps the three REST endpoints and a lightweight polling hook the plan
 * viewer header button uses to stay in sync with the worker. The hook is a
 * polling backstop -- the primary status source is the Liveblocks
 * `ai_run.status_changed` broadcast event.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";

export type AiRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/** Statuses the UI should treat as "in progress". */
export const ACTIVE_AI_RUN_STATUSES: ReadonlySet<AiRunStatus> = new Set([
  "queued",
  "running",
]);

/** Stage entry as written to `summary_jsonb["stages"][stage]`. */
export interface AiRunStageEntry {
  duration_ms: number;
  cache_hit: boolean;
  started_at: string;
  finished_at: string;
  error?: string | null;
}

export interface AiRun {
  id: string;
  org_id: string;
  project_id: string;
  plan_id: string;
  triggered_by: string;
  status: AiRunStatus;
  scope: string;
  model_versions: Record<string, string>;
  started_at: string | null;
  finished_at: string | null;
  cost_cents: number;
  tokens_used: number;
  items_total: number;
  items_accepted_auto: number;
  items_pending: number;
  items_low_confidence: number;
  summary_jsonb: {
    stages?: Record<string, AiRunStageEntry>;
    lock_state?: string;
    counters?: Record<string, number>;
    [k: string]: unknown;
  };
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface AiRunListResponse {
  runs: AiRun[];
}

export interface AiRunStatusBroadcast {
  ai_run_id: string;
  status: AiRunStatus;
  total_stages: number;
  stage?: string;
  stage_index?: number;
  error_message?: string;
}

/** Liveblocks broadcast event for AI run status changes. */
export type AiRunBroadcastEvent = {
  type: "ai_run.status_changed";
  data: AiRunStatusBroadcast;
};

export async function createAiRun(
  projectId: string,
  body: { plan_id: string; scope?: "full_plan" }
): Promise<AiRun> {
  return api.post<AiRun>(`/api/v1/projects/${projectId}/ai/runs`, {
    scope: "full_plan",
    ...body,
  });
}

export async function listAiRuns(
  projectId: string,
  opts: { status?: AiRunStatus; limit?: number } = {}
): Promise<AiRunListResponse> {
  const params = new URLSearchParams();
  if (opts.status) params.set("status", opts.status);
  if (opts.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return api.get<AiRunListResponse>(
    `/api/v1/projects/${projectId}/ai/runs${qs ? `?${qs}` : ""}`
  );
}

export async function getAiRun(
  projectId: string,
  aiRunId: string
): Promise<AiRun> {
  return api.get<AiRun>(`/api/v1/projects/${projectId}/ai/runs/${aiRunId}`);
}

/** Polling intent matches `ACTIVE_AI_RUN_STATUSES` exactly. */
const ACTIVE_STATUSES = ACTIVE_AI_RUN_STATUSES;
/** While a run is active, poll every 5s as a Liveblocks-broadcast backstop. */
const ACTIVE_POLL_INTERVAL_MS = 5000;
/** When idle, poll every 30s so a stale "running" pill clears within a minute. */
const IDLE_POLL_INTERVAL_MS = 30_000;

/** Find the most recent run for a given plan id, or null when there is none. */
function findActiveOrLatestForPlan(
  runs: AiRun[],
  planId: string
): AiRun | null {
  const planRuns = runs.filter((r) => r.plan_id === planId);
  if (planRuns.length === 0) return null;
  // Runs are returned newest-first by the API; prefer an active one if any.
  const active = planRuns.find((r) => ACTIVE_STATUSES.has(r.status));
  return active ?? planRuns[0];
}

/**
 * Track the active (or latest-completed) AI run for a plan.
 *
 * Combines initial fetch + interval polling + a manual-refresh entrypoint that
 * the Liveblocks broadcast handler calls when it sees `ai_run.status_changed`.
 *
 * Returns `{ run, refresh, error, loading }`. `run` is null when no AI run has
 * ever been triggered for this plan.
 */
export function useActiveAiRun(
  projectId: string | null,
  planId: string | null
): {
  run: AiRun | null;
  refresh: () => Promise<void>;
  error: ApiError | null;
  loading: boolean;
} {
  const [run, setRun] = useState<AiRun | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const cancelRef = useRef<{ cancelled: boolean }>({ cancelled: false });

  const refresh = useCallback(async () => {
    if (!projectId || !planId) {
      setRun(null);
      return;
    }
    const ticket = cancelRef.current;
    setLoading(true);
    try {
      const resp = await listAiRuns(projectId, { limit: 25 });
      if (ticket.cancelled) return;
      const next = findActiveOrLatestForPlan(resp.runs, planId);
      setRun(next);
      setError(null);
    } catch (e) {
      if (ticket.cancelled) return;
      if (e instanceof ApiError) setError(e);
      else setError(new ApiError("UNKNOWN_ERROR", String(e), 0));
    } finally {
      if (!ticket.cancelled) setLoading(false);
    }
  }, [projectId, planId]);

  useEffect(() => {
    cancelRef.current = { cancelled: false };
    const ticket = cancelRef.current;
    void refresh();
    return () => {
      ticket.cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    if (!projectId || !planId) return;
    const isActive = run !== null && ACTIVE_STATUSES.has(run.status);
    const interval = isActive ? ACTIVE_POLL_INTERVAL_MS : IDLE_POLL_INTERVAL_MS;
    const handle = window.setInterval(() => {
      void refresh();
    }, interval);
    return () => window.clearInterval(handle);
  }, [projectId, planId, run, refresh]);

  return { run, refresh, error, loading };
}
