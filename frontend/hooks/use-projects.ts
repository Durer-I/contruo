"use client";

import { useCallback, useEffect, useState } from "react";
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

export function useProjects(): UseProjectsState {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const mergeProject = useCallback((id: string, patch: Partial<ProjectInfo>) => {
    setProjects((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ projects: ProjectInfo[] }>("/api/v1/projects");
      setProjects(data.projects);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to load projects";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { projects, loading, error, refresh, mergeProject };
}
