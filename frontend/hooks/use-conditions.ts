"use client";

import { useCallback, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { ConditionInfo } from "@/types/condition";

export function useConditions(projectId: string) {
  const [conditions, setConditions] = useState<ConditionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ conditions: ConditionInfo[] }>(
        `/api/v1/projects/${projectId}/conditions`
      );
      setConditions(res.conditions);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to load conditions";
      setError(msg);
      setConditions([]);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  return { conditions, loading, error, load };
}
