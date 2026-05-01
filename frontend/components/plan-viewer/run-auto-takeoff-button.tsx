"use client";

import { useCallback, useMemo, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  createAiRun,
  type AiRun,
  type AiRunStatus,
} from "@/lib/ai-runs";

const STAGE_PILL_LABELS: Record<string, string> = {
  start: "Starting",
  title_block: "Stage 1 of 6 (title block)",
  classification: "Stage 2 of 6 (classification)",
  schedules_legends: "Stage 3 of 6 (schedules & legends)",
  element_detection: "Stage 4 of 6 (elements)",
  resolver_and_layer_write: "Stage 5 of 6 (resolver)",
  finalize: "Stage 6 of 6 (finalize)",
};

interface PillState {
  label: string;
  variant: "idle" | "running" | "completed" | "failed";
}

function pillFromRun(
  run: AiRun | null,
  liveBroadcast: { stage?: string; status?: AiRunStatus } | null
): PillState {
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
      label: completedCount > 0 ? `Running (${completedCount}/6)` : "Running",
      variant: "running",
    };
  }
  if (run.status === "completed") return { label: "Completed", variant: "completed" };
  if (run.status === "failed") return { label: "Failed", variant: "failed" };
  if (run.status === "cancelled") return { label: "Cancelled", variant: "failed" };
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
  const isActive =
    run?.status === "running" ||
    run?.status === "queued" ||
    liveBroadcast?.status === "running" ||
    liveBroadcast?.status === "queued";

  const handleClick = useCallback(async () => {
    if (!planId) return;
    setSubmitting(true);
    try {
      await createAiRun(projectId, { plan_id: planId });
      await refresh();
      toast.success("AI Auto-Takeoff started");
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === "AI_RUN_LOCKED") {
          toast.warning("An AI run is already in progress for this plan.");
          await refresh();
        } else if (e.code === "AI_COST_LIMIT") {
          toast.error(
            "AI is paused for your organization. Please contact support."
          );
        } else if (e.code === "PLAN_NOT_READY") {
          toast.warning("This plan is still processing. Try again shortly.");
        } else {
          toast.error(e.message || "Failed to start AI Auto-Takeoff");
        }
      } else {
        toast.error("Failed to start AI Auto-Takeoff");
      }
    } finally {
      setSubmitting(false);
    }
  }, [planId, projectId, refresh]);

  if (!visible) return null;

  const buttonDisabled =
    submitting || isActive || planId === null || Boolean(disabledReason);
  const tooltip =
    disabledReason ??
    (isActive ? "An AI run is already in progress" : "Run AI Auto-Takeoff on this plan");

  return (
    <div className="flex items-center gap-1 rounded-3xl border border-border bg-card/80 p-0.5">
      <Button
        type="button"
        size="sm"
        variant={isActive ? "ghost" : "default"}
        className={cn(
          "h-8 shrink-0 gap-1.5 rounded-3xl px-3 text-xs font-medium",
          isActive && "text-foreground hover:bg-surface-overlay"
        )}
        disabled={buttonDisabled}
        onClick={() => {
          void handleClick();
        }}
        title={tooltip}
        aria-label="Run AI Auto-Takeoff"
      >
        {submitting || pill.variant === "running" ? (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />
        ) : (
          <Sparkles className="h-3.5 w-3.5 shrink-0" aria-hidden />
        )}
        <span className="truncate">Velox</span>
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
