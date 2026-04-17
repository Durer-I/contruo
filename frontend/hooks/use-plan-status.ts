"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { PlanInfo } from "@/types/project";

interface UsePlanStatusState {
  plan: PlanInfo | null;
  loading: boolean;
  error: string | null;
}

interface InternalState {
  planId: string | null;
  plan: PlanInfo | null;
  error: string | null;
  loading: boolean;
}

/** Poll `/plans/:id` until the plan reaches a terminal state ('ready' or 'error'). */
export function usePlanStatus(planId: string | null, intervalMs = 1500): UsePlanStatusState {
  const [state, setState] = useState<InternalState>({
    planId: null,
    plan: null,
    error: null,
    loading: false,
  });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  // Reset derived state when the target planId changes. Using the
  // "adjusting state while rendering" pattern is preferred over resetting
  // inside an effect (avoids the react-hooks/set-state-in-effect warning).
  if (state.planId !== planId) {
    setState({ planId, plan: null, error: null, loading: planId !== null });
  }

  useEffect(() => {
    cancelledRef.current = false;
    if (!planId) return;

    const tick = async () => {
      if (cancelledRef.current) return;
      try {
        const p = await api.get<PlanInfo>(`/api/v1/plans/${planId}`);
        if (cancelledRef.current) return;
        const isTerminal = p.status === "ready" || p.status === "error";
        setState({ planId, plan: p, error: null, loading: !isTerminal });
        if (isTerminal) return;
      } catch (e) {
        if (cancelledRef.current) return;
        setState((prev) => ({
          ...prev,
          error: e instanceof ApiError ? e.message : "Failed to fetch plan status",
        }));
      }
      timerRef.current = setTimeout(tick, intervalMs);
    };

    void tick();

    return () => {
      cancelledRef.current = true;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [planId, intervalMs]);

  return { plan: state.plan, loading: state.loading, error: state.error };
}
