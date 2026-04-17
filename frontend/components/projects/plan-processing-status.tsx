"use client";

import { useEffect } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { PlanInfo } from "@/types/project";
import { usePlanStatus } from "@/hooks/use-plan-status";

interface PlanProcessingStatusProps {
  planId: string;
  /** Invoked once the plan reaches 'ready'. */
  onReady?: (plan: PlanInfo) => void;
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
        <AlertTriangle className="h-4 w-4" />
        {error}
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading plan...
      </div>
    );
  }

  if (plan.status === "ready") {
    return (
      <div className="flex items-center gap-2 text-sm text-foreground">
        <CheckCircle2 className="h-4 w-4 text-primary" />
        {plan.filename} ready ({plan.page_count ?? 0} page
        {plan.page_count === 1 ? "" : "s"})
      </div>
    );
  }

  if (plan.status === "error") {
    return (
      <div className="flex flex-col gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
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
            <RotateCw className="mr-2 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const total = plan.page_count ?? 0;
  const processed = plan.processed_pages ?? 0;
  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-sm">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-foreground">
          {total > 0
            ? `Processing page ${processed} of ${total}...`
            : "Starting PDF processing..."}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-overlay">
        <div
          className="h-full bg-primary transition-[width] duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
