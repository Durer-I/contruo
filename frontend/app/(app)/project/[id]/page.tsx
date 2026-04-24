"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const projectId = params.id;
  const { user } = useAuth();

  const role = (user?.role ?? "viewer") as Role;
  const canUpload = hasPermission(role, "upload_plans");
  const canEditMeasurements = hasPermission(role, "edit_measurements");
  const canManageConditions = hasPermission(role, "manage_conditions");
  const canExport = hasPermission(role, "export_data");
  const [project, setProject] = useState<ProjectInfo | null>(null);
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
    if (!silent) {
      setLoading(true);
    }
    setLoadError(null);
    try {
      const [p, plansResp, sheetsResp] = await Promise.all([
        api.get<ProjectInfo>(`/api/v1/projects/${projectId}`),
        api.get<{ plans: PlanInfo[] }>(`/api/v1/projects/${projectId}/plans`),
        api.get<{ sheets: SheetInfo[] }>(`/api/v1/projects/${projectId}/sheets`),
      ]);
      setProject(p);
      setPlans(plansResp.plans);
      setSheets(sheetsResp.sheets);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to load project";
      setLoadError(msg);
      if (silent) {
        throw e instanceof Error ? e : new Error(msg);
      }
    } finally {
      if (!silent) {
        setLoading(false);
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

  const currentPlan = plans.find((p) => p.id === resolvedPlanId) ?? null;

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

  const handlePlanReady = useCallback(() => {
    void loadAll();
  }, [loadAll]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading project...
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
      />

      {resolvedPlanId && currentPlan?.status !== "ready" && (
        <div className="shrink-0 border-b border-border bg-card px-4 py-3">
          <div className="mb-2 text-sm font-medium">
            {pendingFile?.name ?? currentPlan?.filename ?? "Plan"}
          </div>
          <PlanProcessingStatus planId={resolvedPlanId} onReady={handlePlanReady} />
        </div>
      )}

      {hasSheets && resolvedPlanId ? (
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
