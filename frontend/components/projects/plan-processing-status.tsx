"use client";

import { useEffect } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { PlanInfo, PlanProcessingSubstep } from "@/types/project";
import { usePlanStatus } from "@/hooks/use-plan-status";
interface PlanProcessingStatusProps {
  planId: string;
  /** Invoked once the plan reaches 'ready'. */
  onReady?: (plan: PlanInfo) => void;
}

function phaseCopy(
  sub: PlanProcessingSubstep | null | undefined,
  processed: number,
  total: number
): { title: string; hint: string } {
  if (total <= 0) {
    return {
      title: "Starting PDF processing…",
      hint: "Preparing the file and page count.",
    };
  }
  if (sub === "persist") {
    return {
      title: `Saving sheets (${processed} of ${total})`,
      hint: "Writing pages and thumbnails to the database. Almost there.",
    };
  }
  return {
    title: `Extracting PDF (${processed} of ${total} pages)`,
    hint: "Reading text, vectors, and previews from each page.",
  };
}

export function PlanProcessingStatus({ planId, onReady }: PlanProcessingStatusProps) {
  const { plan, error } = usePlanStatus(planId);

  useEffect(() => {
    if (plan?.status === "ready" && onReady) {
      onReady(plan);
    }
  }, [plan, onReady]);

  if (error && !plan) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        {error}
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading plan…
      </div>
    );
  }

  if (plan.status === "ready") {
    return (
      <div className="flex items-center gap-2 text-sm text-foreground">
        <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" aria-hidden />
        {plan.filename} ready ({plan.page_count ?? 0} page
        {plan.page_count === 1 ? "" : "s"})
      </div>
    );
  }

  if (plan.status === "error") {
    return (
      <div className="flex flex-col gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
          Processing failed{plan.error_message ? `: ${plan.error_message}` : ""}
        </div>
        <div>
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              try {
                await api.post<PlanInfo>(`/api/v1/plans/${plan.id}/retry`, {});
              } catch (e) {
                if (!(e instanceof ApiError)) throw e;
              }
            }}
          >
            <RotateCw className="mr-2 h-3.5 w-3.5" aria-hidden />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const total = plan.page_count ?? 0;
  const processed = plan.processed_pages ?? 0;
  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  /** Keep a visible sliver so 0% and low values do not look broken. */
  const barWidth = total > 0 ? Math.max(pct, processed > 0 ? 2 : 0) : 0;

  const sub = plan.processing_substep;
  const { title, hint } = phaseCopy(sub, processed, total);

  return (
    <div className="flex flex-col gap-2.5" role="status" aria-live="polite" aria-busy="true">
      <div className="flex items-start gap-2.5">
        <Loader2
          className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary"
          aria-hidden
        />
        <div className="min-w-0 flex-1 space-y-0.5">
          <p className="text-sm font-medium text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        {total > 0 && (
          <span className="shrink-0 tabular-nums text-xs font-medium text-muted-foreground">
            {pct}%
          </span>
        )}
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-surface-overlay ring-1 ring-inset ring-border/40"
        aria-label="Processing progress"
      >
        <div
          className="h-full rounded-full bg-primary/90 shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] transition-[width] duration-500 ease-out dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
          style={{ width: `${barWidth}%` }}
        />
      </div>
    </div>
  );
}
