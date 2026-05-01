"use client";

import { useCallback, useMemo, useState } from "react";
import { Loader2, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  cancelAiRun,
  createAiRun,
  type AiRun,
  type AiRunStatus,
} from "@/lib/ai-runs";

/** Count of entries in ``PIPELINE_STAGES`` (backend); keep in sync for progress text. */
const PIPELINE_STAGE_COUNT = 5;

const STAGE_PILL_LABELS: Record<string, string> = {
  start: "Starting",
  classification: "Stage 1 of 5 (classification)",
  schedules_legends: "Stage 2 of 5 (schedules & legends)",
  element_detection: "Stage 3 of 5 (elements)",
  resolver_and_layer_write: "Stage 4 of 5 (resolver)",
  finalize: "Stage 5 of 5 (finalize)",
};

interface PillState {
  label: string;
  variant: "idle" | "running" | "completed" | "failed";
}

function pillFromRun(
  run: AiRun | null,
  liveBroadcast: { stage?: string; status?: AiRunStatus } | null
): PillState {
  // DB terminal states win over a stale Liveblocks "running" payload.
  if (run?.status === "completed")
    return { label: "Completed", variant: "completed" };
  if (run?.status === "failed") return { label: "Failed", variant: "failed" };
  if (run?.status === "cancelled")
    return { label: "Cancelled", variant: "failed" };

  // Live broadcast wins for transient states so the pill is smoother than
  // the polling cadence.
  if (liveBroadcast?.status === "running" && liveBroadcast.stage) {
    const lbl = STAGE_PILL_LABELS[liveBroadcast.stage] ?? "Running";
    return { label: lbl, variant: "running" };
  }
  if (!run) return { label: "Idle", variant: "idle" };
  if (run.status === "queued") return { label: "Queued", variant: "running" };
  if (run.status === "running") {
    const stages = run.summary_jsonb?.stages ?? {};
    const completedCount = Object.keys(stages).length;
    return {
      label:
        completedCount > 0
          ? `Running (${completedCount}/${PIPELINE_STAGE_COUNT})`
          : "Running",
      variant: "running",
    };
  }
  return { label: "Idle", variant: "idle" };
}

export interface RunAutoTakeoffButtonProps {
  projectId: string;
  /** Active plan id; the button operates on this plan. Disabled when null. */
  planId: string | null;
  /** Latest AiRun for this plan (from useActiveAiRun). */
  run: AiRun | null;
  /** Re-fetch the latest run after we trigger one. */
  refresh: () => Promise<void>;
  /** Latest Liveblocks broadcast (used for the smooth stage label). */
  liveBroadcast: { stage?: string; status?: AiRunStatus } | null;
  /** Hide entirely when the user can't trigger runs. */
  visible: boolean;
  /** Disable when the plan isn't ready (still processing) or there's no plan. */
  disabledReason?: string | null;
}

export function RunAutoTakeoffButton({
  projectId,
  planId,
  run,
  refresh,
  liveBroadcast,
  visible,
  disabledReason,
}: RunAutoTakeoffButtonProps) {
  const [submitting, setSubmitting] = useState(false);

  const pill = useMemo(() => pillFromRun(run, liveBroadcast), [run, liveBroadcast]);
  const runActive =
    run !== null &&
    (run.status === "queued" || run.status === "running");

  const handleClick = useCallback(async () => {
    if (!planId) return;
    setSubmitting(true);
    try {
      if (runActive && run?.id) {
        await cancelAiRun(projectId, run.id);
        await refresh();
        toast.success("AI Auto-Takeoff cancelled");
      } else {
        await createAiRun(projectId, { plan_id: planId });
        await refresh();
        toast.success("AI Auto-Takeoff started");
      }
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === "AI_RUN_LOCKED") {
          toast.warning("An AI run is already in progress for this plan.");
          await refresh();
        } else if (e.code === "AI_RUN_NOT_CANCELLABLE") {
          toast.warning(
            e.message || "This run can no longer be cancelled (it may have finished)."
          );
          await refresh();
        } else if (e.code === "AI_COST_LIMIT") {
          toast.error(
            "AI is paused for your organization. Please contact support."
          );
        } else if (e.code === "PLAN_NOT_READY") {
          toast.warning("This plan is still processing. Try again shortly.");
        } else {
          toast.error(e.message || "AI Auto-Takeoff request failed");
        }
      } else {
        toast.error("AI Auto-Takeoff request failed");
      }
    } finally {
      setSubmitting(false);
    }
  }, [planId, projectId, refresh, run?.id, runActive]);

  if (!visible) return null;

  const buttonDisabled =
    submitting || planId === null || Boolean(disabledReason);

  const tooltip = disabledReason
    ? disabledReason
    : runActive
      ? "Cancel AI Auto-Takeoff"
      : "Run AI Auto-Takeoff on this plan";

  return (
    <div className="flex items-center gap-1 rounded-3xl border border-border bg-card/80 p-0.5">
      <Button
        type="button"
        size="sm"
        variant={runActive ? "ghost" : "default"}
        className={cn(
          "h-8 shrink-0 gap-1.5 rounded-3xl px-3 text-xs font-medium",
          runActive && "text-foreground hover:bg-surface-overlay"
        )}
        disabled={buttonDisabled}
        onClick={() => {
          void handleClick();
        }}
        title={tooltip}
        aria-label={runActive ? "Cancel AI Auto-Takeoff" : "Run AI Auto-Takeoff"}
      >
        {submitting || pill.variant === "running" ? (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />
        ) : runActive ? (
          <X className="h-3.5 w-3.5 shrink-0" aria-hidden />
        ) : (
          <Sparkles className="h-3.5 w-3.5 shrink-0" aria-hidden />
        )}
        <span className="truncate">{runActive ? "Stop" : "Velox"}</span>
      </Button>
      <span
        className={cn(
          "shrink-0 rounded-2xl px-2 py-0.5 text-[11px] font-medium",
          pill.variant === "idle" && "bg-muted text-muted-foreground",
          pill.variant === "running" && "bg-primary/15 text-primary",
          pill.variant === "completed" && "bg-emerald-500/15 text-emerald-500",
          pill.variant === "failed" && "bg-destructive/15 text-destructive"
        )}
        title={
          pill.variant === "failed" && run?.error_message
            ? run.error_message
            : pill.label
        }
      >
        {pill.label}
      </span>
    </div>
  );
}
