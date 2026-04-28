"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import { hasPermission, type Role } from "@/lib/permissions";
import type { PlanInfo, ProjectInfo, SheetInfo } from "@/types/project";

import { PlanProcessingStatus } from "@/components/projects/plan-processing-status";
import {
  ProjectTopBarRegistrar,
} from "@/components/projects/project-top-bar-center";
import { PlanViewerWorkspace } from "@/components/plan-viewer/plan-viewer-workspace";
import { ProjectCollaborationRoom } from "@/components/collaboration/project-collaboration-room";

/** Dedupe concurrent fetches per key (e.g. React Strict Mode double mount in dev). */
function dedupePromise<T>(map: Map<string, Promise<T>>, key: string, factory: () => Promise<T>): Promise<T> {
  let existing = map.get(key);
  if (!existing) {
    existing = factory();
    map.set(key, existing);
    void existing.finally(() => {
      if (map.get(key) === existing) {
        map.delete(key);
      }
    });
  }
  return existing;
}

const projectLoadInflight = new Map<string, Promise<ProjectInfo>>();
const plansSheetsLoadInflight = new Map<
  string,
  Promise<{ plans: PlanInfo[]; sheets: SheetInfo[] }>
>();

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const rawId = params.id;
  const projectId = Array.isArray(rawId) ? rawId[0] : rawId;
  const { user } = useAuth();

  /** Latest project route id — ignore stale async completions after navigation. */
  const activeProjectIdRef = useRef(projectId);
  activeProjectIdRef.current = projectId;

  const role = (user?.role ?? "viewer") as Role;
  const canUpload = hasPermission(role, "upload_plans");
  const canEditMeasurements = hasPermission(role, "edit_measurements");
  const canManageConditions = hasPermission(role, "manage_conditions");
  const canExport = hasPermission(role, "export_data");
  const [project, setProject] = useState<ProjectInfo | null>(null);
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [plansSheetsError, setPlansSheetsError] = useState<string | null>(null);
  const [projectLoading, setProjectLoading] = useState(true);
  const [plansSheetsLoading, setPlansSheetsLoading] = useState(true);

  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  /** User / URL selection; falls back via `resolvedPlanId` when unset or invalid. */
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(() =>
    searchParams.get("plan")
  );

  /** True while silent refetch runs (e.g. after scale save) — shows inline loader in viewer. */
  const [sheetsRefreshing, setSheetsRefreshing] = useState(false);

  const loadAll = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true;
    const forId = projectId;
    if (!forId) {
      if (!silent) {
        setProjectLoading(false);
        setPlansSheetsLoading(false);
      }
      return;
    }

    const stillHere = () => activeProjectIdRef.current === forId;

    if (!silent) {
      setLoadError(null);
      setPlansSheetsError(null);
      setProjectLoading(true);
      setPlansSheetsLoading(true);
    } else {
      setPlansSheetsError(null);
    }

    const fail = (msg: string, phase: "project" | "plans_sheets") => {
      if (!stillHere()) return;
      if (!silent) {
        setProjectLoading(false);
        setPlansSheetsLoading(false);
      }
      if (phase === "project") {
        setLoadError(msg);
        setProject(null);
      } else {
        setPlansSheetsError(msg);
      }
    };

    try {
      if (!silent) {
        let p: ProjectInfo;
        try {
          p = await dedupePromise(projectLoadInflight, forId, () =>
            api.get<ProjectInfo>(`/api/v1/projects/${forId}`)
          );
        } catch (e) {
          const msg = e instanceof ApiError ? e.message : "Failed to load project";
          fail(msg, "project");
          return;
        }
        if (!stillHere()) return;
        setProject(p);
        setProjectLoading(false);

        try {
          const bundle = await dedupePromise(plansSheetsLoadInflight, forId, async () => {
            const [plansResp, sheetsResp] = await Promise.all([
              api.get<{ plans: PlanInfo[] }>(`/api/v1/projects/${forId}/plans`),
              api.get<{ sheets: SheetInfo[] }>(`/api/v1/projects/${forId}/sheets`),
            ]);
            return { plans: plansResp.plans, sheets: sheetsResp.sheets };
          });
          if (!stillHere()) return;
          setPlans(bundle.plans);
          setSheets(bundle.sheets);
          setPlansSheetsError(null);
        } catch (e) {
          const msg = e instanceof ApiError ? e.message : "Failed to load plans or sheets";
          fail(msg, "plans_sheets");
          return;
        }
        if (!stillHere()) return;
        setPlansSheetsLoading(false);
      } else {
        const [p, plansResp, sheetsResp] = await Promise.all([
          api.get<ProjectInfo>(`/api/v1/projects/${forId}`),
          api.get<{ plans: PlanInfo[] }>(`/api/v1/projects/${forId}/plans`),
          api.get<{ sheets: SheetInfo[] }>(`/api/v1/projects/${forId}/sheets`),
        ]);
        if (!stillHere()) return;
        setProject(p);
        setPlans(plansResp.plans);
        setSheets(sheetsResp.sheets);
        setPlansSheetsError(null);
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to load project";
      if (!stillHere()) return;
      if (!silent) {
        setProjectLoading(false);
        setPlansSheetsLoading(false);
        setLoadError(msg);
      }
      if (silent) {
        throw e instanceof Error ? e : new Error(msg);
      }
    }
  }, [projectId]);

  /** Refetch project/plans/sheets without full-page spinner (keeps PDF viewer mounted). */
  const refreshSheetsSilently = useCallback(async () => {
    setSheetsRefreshing(true);
    try {
      await loadAll({ silent: true });
    } finally {
      setSheetsRefreshing(false);
    }
  }, [loadAll]);

  useEffect(() => {
    setProject(null);
    setPlans([]);
    setSheets([]);
    setLoadError(null);
    setPlansSheetsError(null);
    setProjectLoading(true);
    setPlansSheetsLoading(true);
  }, [projectId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    const q = searchParams.get("plan");
    if (!q || !plans.some((p) => p.id === q)) return;
    setSelectedPlanId((prev) => (prev !== q ? q : prev));
  }, [searchParams, plans]);

  const resolvedPlanId = useMemo(() => {
    if (selectedPlanId && plans.some((p) => p.id === selectedPlanId)) {
      return selectedPlanId;
    }
    if (plans.length === 0) return null;
    return (
      plans.find(
        (p) => p.status === "ready" && sheets.some((s) => s.plan_id === p.id)
      )?.id ?? plans[0]!.id
    );
  }, [selectedPlanId, plans, sheets]);

  const selectPlan = useCallback(
    (planId: string) => {
      setSelectedPlanId(planId);
      const params = new URLSearchParams(searchParams.toString());
      params.set("plan", planId);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams]
  );

  const qpPlanId = searchParams.get("plan");
  /** Prefer `?plan=` so progress appears before the plans list finishes loading after redirect. */
  const progressPlanId = useMemo(() => {
    if (qpPlanId && (plans.length === 0 || plans.some((p) => p.id === qpPlanId))) {
      return qpPlanId;
    }
    if (resolvedPlanId && plans.some((p) => p.id === resolvedPlanId && p.status !== "ready")) {
      return resolvedPlanId;
    }
    return null;
  }, [qpPlanId, plans, resolvedPlanId]);

  const showPlanProgressUi = useMemo(() => {
    if (!progressPlanId) return false;
    // After redirect with ?plan=, show progress while plans are still loading; otherwise
    // wait for plans so a stale query id does not look like an active processing job.
    if (plans.length === 0) {
      return Boolean(qpPlanId && plansSheetsLoading);
    }
    const p = plans.find((x) => x.id === progressPlanId);
    return Boolean(p && p.status !== "ready");
  }, [progressPlanId, plans, qpPlanId, plansSheetsLoading]);

  const progressPlanLabel =
    plans.find((p) => p.id === progressPlanId)?.filename ?? pendingFile?.name ?? "Plan";

  const handleUpload = useCallback(async () => {
    if (!pendingFile) return;
    setUploadError(null);
    setUploadProgress(0);
    try {
      const plan = await api.uploadFile<PlanInfo>(
        `/api/v1/projects/${projectId}/plans`,
        pendingFile,
        { onProgress: (pct) => setUploadProgress(pct) }
      );
      setPendingFile(null);
      setUploadProgress(null);
      selectPlan(plan.id);
      setPlans((prev) => [plan, ...prev]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Upload failed";
      setUploadError(msg);
      setUploadProgress(null);
      throw e instanceof Error ? e : new Error(msg);
    }
  }, [pendingFile, projectId, selectPlan]);

  const handleDeletePlan = useCallback(
    async (planId: string) => {
      try {
        await api.delete(`/api/v1/plans/${planId}`);
      } catch (e) {
        throw e instanceof ApiError
          ? new Error(e.message)
          : e instanceof Error
            ? e
            : new Error("Failed to delete plan");
      }
      // Drop the plan locally so the next render picks a fallback before refetch lands.
      setPlans((prev) => prev.filter((p) => p.id !== planId));
      setSheets((prev) => prev.filter((s) => s.plan_id !== planId));
      setSelectedPlanId((prev) => (prev === planId ? null : prev));
      try {
        await refreshSheetsSilently();
      } catch {
        /* surfaced through plansSheetsError */
      }
    },
    [refreshSheetsSilently]
  );

  const handlePlanReady = useCallback(() => {
    void loadAll({ silent: true });
  }, [loadAll]);

  if (projectLoading && !project) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading project…
      </div>
    );
  }

  if (loadError || !project) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex max-w-md flex-col items-center gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-6 text-center text-sm text-destructive">
          <AlertTriangle className="h-6 w-6" />
          <p>{loadError ?? "Project not found"}</p>
          <Button variant="outline" onClick={() => router.push("/projects")}>
            Back to projects
          </Button>
        </div>
      </div>
    );
  }

  const hasSheets = sheets.length > 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ProjectTopBarRegistrar
        plans={plans}
        activePlanId={resolvedPlanId}
        onSelectPlan={selectPlan}
        canUpload={canUpload}
        pendingFile={pendingFile}
        onPendingFile={setPendingFile}
        uploadProgress={uploadProgress}
        uploadError={uploadError}
        onConfirmUpload={handleUpload}
        onDeletePlan={canUpload ? handleDeletePlan : undefined}
      />

      {plansSheetsError && !plansSheetsLoading && (
        <div className="flex shrink-0 items-center gap-2 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="min-w-0">{plansSheetsError}</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto h-7 shrink-0 text-xs"
            onClick={() => void loadAll()}
          >
            Retry
          </Button>
        </div>
      )}

      {showPlanProgressUi && progressPlanId && (
        <div className="shrink-0 border-b border-border bg-card px-4 py-3">
          <div className="mb-2 text-sm font-medium">{progressPlanLabel}</div>
          <PlanProcessingStatus planId={progressPlanId} onReady={handlePlanReady} />
        </div>
      )}

      {plansSheetsLoading ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-8 text-sm text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
          <p>Loading viewer data…</p>
        </div>
      ) : hasSheets && resolvedPlanId ? (
        <ProjectCollaborationRoom orgId={project.org_id} projectId={projectId}>
          <PlanViewerWorkspace
            key={projectId}
            projectId={projectId}
            projectName={project.name}
            plans={plans}
            activePlanId={resolvedPlanId}
            onActivePlanChange={selectPlan}
            sheets={sheets}
            onSheetsRefresh={refreshSheetsSilently}
            sheetsRefreshing={sheetsRefreshing}
            canEditMeasurements={canEditMeasurements}
            canManageConditions={canManageConditions}
            canExport={canExport}
          />
        </ProjectCollaborationRoom>
      ) : (
        <div className="flex flex-1 flex-col overflow-auto p-6">
          <div className="mb-4 border-b border-border pb-3">
            <h1 className="text-base font-semibold">{project.name}</h1>
            {project.description && (
              <p className="mt-1 text-xs text-muted-foreground">{project.description}</p>
            )}
          </div>
          <p className="mb-6 text-sm text-muted-foreground">
            {canUpload ? (
              <>
                Use <span className="text-foreground">Add plan</span> in the top bar (upload icon) to
                add a PDF. After processing, the viewer opens here.
              </>
            ) : (
              <>
                No plans uploaded yet. Ask an estimator or admin to upload a PDF. After processing,
                the viewer opens here.
              </>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
