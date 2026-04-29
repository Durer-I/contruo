"use client";

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { ConditionInfo } from "@/types/condition";

export const conditionsQueryKey = (projectId: string) =>
  ["conditions", projectId] as const;

async function fetchConditions(projectId: string): Promise<ConditionInfo[]> {
  const res = await api.get<{ conditions: ConditionInfo[] }>(
    `/api/v1/projects/${projectId}/conditions`
  );
  return res.conditions;
}

/**
 * `useConditions` mirrors the previous imperative shape (`conditions`,
 * `loading`, `error`, `load`) but uses React Query under the hood so that the
 * plan viewer, condition manager and quantities panel all dedupe a single
 * fetch per project.
 */
export function useConditions(projectId: string) {
  const queryClient = useQueryClient();

  const query = useQuery<ConditionInfo[], ApiError>({
    queryKey: conditionsQueryKey(projectId),
    queryFn: () => fetchConditions(projectId),
    enabled: Boolean(projectId),
    staleTime: 30_000,
  });

  const load = useCallback(async () => {
    if (!projectId) return;
    await queryClient.invalidateQueries({
      queryKey: conditionsQueryKey(projectId),
    });
  }, [queryClient, projectId]);

  return {
    conditions: query.data ?? [],
    loading: query.isLoading,
    error: query.error
      ? query.error instanceof ApiError
        ? query.error.message
        : "Failed to load conditions"
      : null,
    load,
  };
}
