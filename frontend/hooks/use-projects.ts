"use client";

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { ProjectInfo } from "@/types/project";

interface UseProjectsState {
  projects: ProjectInfo[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /** Patch one project in the local list (e.g. after cover upload before refetch completes). */
  mergeProject: (id: string, patch: Partial<ProjectInfo>) => void;
}

export const PROJECTS_QUERY_KEY = ["projects"] as const;

async function fetchProjects(): Promise<ProjectInfo[]> {
  const data = await api.get<{ projects: ProjectInfo[] }>("/api/v1/projects");
  return data.projects;
}

/**
 * `useProjects` keeps its previous imperative API (`projects`, `loading`,
 * `error`, `refresh`, `mergeProject`) but is now backed by React Query so that
 * multiple consumers share a single in-flight request and an LRU cache.
 */
export function useProjects(): UseProjectsState {
  const queryClient = useQueryClient();

  const query = useQuery<ProjectInfo[], ApiError>({
    queryKey: PROJECTS_QUERY_KEY,
    queryFn: fetchProjects,
    staleTime: 30_000,
  });

  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
  }, [queryClient]);

  const mergeProject = useCallback(
    (id: string, patch: Partial<ProjectInfo>) => {
      queryClient.setQueryData<ProjectInfo[]>(PROJECTS_QUERY_KEY, (prev) => {
        if (!prev) return prev;
        return prev.map((p) => (p.id === id ? { ...p, ...patch } : p));
      });
    },
    [queryClient]
  );

  return {
    projects: query.data ?? [],
    loading: query.isLoading,
    error: query.error
      ? query.error instanceof ApiError
        ? query.error.message
        : "Failed to load projects"
      : null,
    refresh,
    mergeProject,
  };
}
