"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ProjectInfo } from "@/types/project";

interface UseProjectsState {
  projects: ProjectInfo[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useProjects(): UseProjectsState {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  return { projects, loading, error, refresh };
}
