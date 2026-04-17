"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Loader2, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import { hasPermission, type Role } from "@/lib/permissions";
import { cn, formatFileSize } from "@/lib/utils";
import type { PlanInfo, ProjectInfo, SheetInfo } from "@/types/project";

import { PlanUploadZone } from "@/components/projects/plan-upload-zone";
import { PlanProcessingStatus } from "@/components/projects/plan-processing-status";
import { PlanViewerWorkspace } from "@/components/plan-viewer/plan-viewer-workspace";

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
  const canDeleteProject = hasPermission(role, "create_projects");

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

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
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
      setLoadError(e instanceof ApiError ? e.message : "Failed to load project");
    } finally {
      setLoading(false);
    }
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

  const currentPlan = plans.find((p) => p.id === resolvedPlanId) ?? null;

  async function handleUpload() {
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
      setUploadError(e instanceof ApiError ? e.message : "Upload failed");
      setUploadProgress(null);
    }
  }

  const handlePlanReady = useCallback(() => {
    void loadAll();
  }, [loadAll]);

  function handleDeleteDialogOpen(next: boolean) {
    if (!next) {
      setDeleteConfirmName("");
      setDeleteError(null);
    }
    setDeleteDialogOpen(next);
  }

  async function handleDeleteProject() {
    if (!project || deleteConfirmName !== project.name) return;
    setDeleteError(null);
    setDeleteBusy(true);
    try {
      await api.delete(`/api/v1/projects/${projectId}`);
      handleDeleteDialogOpen(false);
      router.push("/projects");
    } catch (e) {
      setDeleteError(
        e instanceof ApiError ? e.message : "Could not delete project"
      );
    } finally {
      setDeleteBusy(false);
    }
  }

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
      {resolvedPlanId && currentPlan?.status !== "ready" && (
        <div className="shrink-0 border-b border-border bg-card px-4 py-3">
          <div className="mb-2 text-sm font-medium">
            {pendingFile?.name ?? currentPlan?.filename ?? "Plan"}
          </div>
          <PlanProcessingStatus planId={resolvedPlanId} onReady={handlePlanReady} />
        </div>
      )}

      {hasSheets && resolvedPlanId ? (
        <PlanViewerWorkspace
          key={projectId}
          projectId={projectId}
          projectName={project.name}
          plans={plans}
          activePlanId={resolvedPlanId}
          onActivePlanChange={selectPlan}
          sheets={sheets}
          onSheetsRefresh={loadAll}
          canEditMeasurements={canEditMeasurements}
        />
      ) : (
        <div className="flex flex-1 flex-col overflow-auto p-6">
          <div className="mb-4 border-b border-border pb-3">
            <h1 className="text-base font-semibold">{project.name}</h1>
            {project.description && (
              <p className="mt-1 text-xs text-muted-foreground">{project.description}</p>
            )}
          </div>
          <p className="mb-6 text-sm text-muted-foreground">
            Upload a PDF plan set to extract sheets. After processing, the viewer opens here.
          </p>
        </div>
      )}

      {plans.length > 0 && (
        <div className="shrink-0 border-t border-border bg-card px-4 py-3">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Plans in this project
          </h3>
          <ul className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {plans.map((plan) => {
              const active = plan.id === resolvedPlanId;
              return (
                <li key={plan.id} className="min-w-0 sm:max-w-[min(100%,20rem)] sm:flex-1">
                  <button
                    type="button"
                    onClick={() => selectPlan(plan.id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                      active
                        ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                        : "border-border bg-surface hover:border-primary/40 hover:bg-surface-overlay"
                    )}
                  >
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate font-medium">{plan.filename}</span>
                      <span className="text-xs text-muted-foreground">
                        {plan.page_count ?? "?"} page
                        {plan.page_count === 1 ? "" : "s"} · {formatFileSize(plan.file_size)}
                      </span>
                    </div>
                    <PlanStatusBadge status={plan.status} />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {canUpload && (
        <div
          className={`shrink-0 border-t border-border bg-card ${hasSheets ? "max-h-[40vh] overflow-auto" : ""}`}
        >
          <div className={`p-4 ${hasSheets ? "py-3" : ""}`}>
            <div className="mb-3">
              <h2 className="text-sm font-medium">
                {hasSheets ? "Add another plan" : "Upload a plan"}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Vector PDF recommended. Files are stored securely and processed in the background.
              </p>
            </div>

            <PlanUploadZone
              file={pendingFile}
              onFile={setPendingFile}
              disabled={uploadProgress !== null}
            />

            {uploadProgress !== null && (
              <div className="mt-3 flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Uploading {pendingFile?.name}</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-surface-overlay">
                  <div
                    className="h-full bg-primary transition-[width] duration-150"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}

            {uploadError && (
              <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {uploadError}
              </div>
            )}

            <div className="mt-4 flex justify-end">
              <Button
                onClick={handleUpload}
                disabled={!pendingFile || uploadProgress !== null}
              >
                {uploadProgress !== null ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                Upload Plan
              </Button>
            </div>
          </div>
        </div>
      )}

      {!canUpload && !hasSheets && (
        <div className="border-t border-border p-6 text-center text-sm text-muted-foreground">
          No plans uploaded yet. Ask an estimator or admin to upload.
        </div>
      )}

      {canDeleteProject && (
        <div className="shrink-0 border-t border-destructive/20 bg-destructive/5 px-4 py-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium text-destructive">Delete project</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Permanently removes this project, all plans and sheets, and stored files. This
                cannot be undone.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="shrink-0 border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={() => handleDeleteDialogOpen(true)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete project…
            </Button>
          </div>
        </div>
      )}

      <Dialog open={deleteDialogOpen} onOpenChange={handleDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete this project?</DialogTitle>
            <DialogDescription>
              All plans, sheets, and related data for{" "}
              <span className="font-medium text-foreground">{project.name}</span> will be removed
              from the database and file storage.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label htmlFor="delete-project-confirm" className="text-sm font-medium">
              Type the project name to confirm
            </label>
            <Input
              id="delete-project-confirm"
              value={deleteConfirmName}
              onChange={(e) => setDeleteConfirmName(e.target.value)}
              placeholder={project.name}
              autoComplete="off"
              disabled={deleteBusy}
              aria-invalid={deleteConfirmName.length > 0 && deleteConfirmName !== project.name}
            />
          </div>
          {deleteError && (
            <p className="text-xs text-destructive" role="alert">
              {deleteError}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => handleDeleteDialogOpen(false)}
              disabled={deleteBusy}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={
                deleteBusy || deleteConfirmName !== project.name || !project.name
              }
              onClick={() => void handleDeleteProject()}
            >
              {deleteBusy ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting…
                </>
              ) : (
                "Delete permanently"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PlanStatusBadge({ status }: { status: PlanInfo["status"] }) {
  if (status === "ready") {
    return (
      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
        Ready
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-medium text-destructive">
        Error
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
      <Loader2 className="h-3 w-3 animate-spin" />
      Processing
    </span>
  );
}
