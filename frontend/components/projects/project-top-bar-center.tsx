"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Loader2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTopBarCenter } from "@/providers/top-bar-center-provider";
import { useTakeoffToolbarSlot } from "@/providers/takeoff-toolbar-slot-provider";
import { cn, formatFileSize } from "@/lib/utils";
import type { PlanInfo } from "@/types/project";

import { PlanUploadZone } from "@/components/projects/plan-upload-zone";

export function PlanStatusBadge({ status }: { status: PlanInfo["status"] }) {
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

export interface ProjectTopBarCenterProps {
  plans: PlanInfo[];
  activePlanId: string | null;
  onSelectPlan: (planId: string) => void;
  canUpload: boolean;
  pendingFile: File | null;
  onPendingFile: (file: File | null) => void;
  uploadProgress: number | null;
  uploadError: string | null;
  onConfirmUpload: () => void | Promise<void>;
}

function ProjectTopBarCenterInner({
  plans,
  activePlanId,
  onSelectPlan,
  canUpload,
  pendingFile,
  onPendingFile,
  uploadProgress,
  uploadError,
  onConfirmUpload,
}: ProjectTopBarCenterProps) {
  const { slot: takeoffSlot } = useTakeoffToolbarSlot();
  const [uploadOpen, setUploadOpen] = useState(false);

  const current = plans.find((p) => p.id === activePlanId) ?? null;

  const showPlanUploadBar = plans.length > 0 || canUpload;

  return (
    <div className="flex max-w-full min-w-0 items-center justify-center gap-2 px-1">
      {takeoffSlot && (
        <div className="min-w-0 shrink">{takeoffSlot}</div>
      )}

      {takeoffSlot && showPlanUploadBar && (
        <div className="h-8 w-0.5 shrink-0 bg-border" aria-hidden />
      )}

      {showPlanUploadBar && (
        <div
          className={cn(
            "flex min-w-0 max-w-[min(100vw-12rem,28rem)] shrink-0 items-center gap-0.5 rounded-2xl border border-border bg-card/80 p-0.5",
            "shadow-sm"
          )}
        >
          {plans.length > 0 ? (
            <DropdownMenu>
              <DropdownMenuTrigger
                type="button"
                className={cn(
                  "flex h-8 min-w-0 max-w-[min(100%,14rem)] items-center gap-1 rounded-2xl px-2 text-left text-xs font-medium",
                  "text-foreground outline-none hover:bg-surface-overlay",
                  "focus-visible:ring-2 focus-visible:ring-primary/40"
                )}
                title="Current plan"
              >
                <span className="min-w-0 truncate">
                  {current?.filename ?? "Select plan"}
                </span>
                <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-[min(calc(100vw-2rem),20rem)]">
                <DropdownMenuGroup>
                  <DropdownMenuLabel className="text-[11px] uppercase tracking-wide">
                    Plans in this project
                  </DropdownMenuLabel>
                  {plans.map((plan) => {
                    const active = plan.id === activePlanId;
                    return (
                      <DropdownMenuItem
                        key={plan.id}
                        onClick={() => onSelectPlan(plan.id)}
                        className={cn(
                          "flex flex-col items-start gap-0.5 py-2",
                          active && "bg-accent/50"
                        )}
                      >
                        <div className="flex w-full items-center justify-between gap-2">
                          <span className="min-w-0 truncate font-medium">{plan.filename}</span>
                          <PlanStatusBadge status={plan.status} />
                        </div>
                        <span className="text-[11px] text-muted-foreground">
                          {plan.page_count ?? "?"} page{plan.page_count === 1 ? "" : "s"} ·{" "}
                          {formatFileSize(plan.file_size)}
                        </span>
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <span className="px-2 py-1.5 text-xs text-muted-foreground">No plans yet</span>
          )}

          {canUpload && (
            <>
              {plans.length > 0 && (
                <div className="mx-0.5 h-5 w-px shrink-0 bg-border/80" aria-hidden />
              )}
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="shrink-0 rounded-md"
                title="Add plan (PDF)"
                aria-label="Add plan PDF"
                onClick={() => setUploadOpen(true)}
              >
                <Upload className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      )}

      {canUpload && (
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Add plan</DialogTitle>
              <DialogDescription>
                Upload a PDF plan set. Vector PDFs are recommended. Files are processed in the
                background.
              </DialogDescription>
            </DialogHeader>
            <PlanUploadZone
              file={pendingFile}
              onFile={onPendingFile}
              disabled={uploadProgress !== null}
            />
            {uploadProgress !== null && (
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="truncate">Uploading {pendingFile?.name}</span>
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
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {uploadError}
              </div>
            )}
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setUploadOpen(false)}>
                {uploadProgress !== null ? "Close" : "Cancel"}
              </Button>
              <Button
                type="button"
                onClick={() => {
                  void (async () => {
                    try {
                      await onConfirmUpload();
                      setUploadOpen(false);
                    } catch {
                      /* error shown above */
                    }
                  })();
                }}
                disabled={!pendingFile || uploadProgress !== null}
              >
                {uploadProgress !== null ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading…
                  </>
                ) : (
                  <>
                    <Upload className="mr-2 h-4 w-4" />
                    Upload plan
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

/** Renders plan picker + upload in the app top bar; takeoff tools slot comes from context (viewer). */
export function ProjectTopBarCenter(props: ProjectTopBarCenterProps) {
  return <ProjectTopBarCenterInner {...props} />;
}

/** Registers {@link ProjectTopBarCenter} in the top bar while mounted. */
export function ProjectTopBarRegistrar({
  plans,
  activePlanId,
  onSelectPlan,
  canUpload,
  pendingFile,
  onPendingFile,
  uploadProgress,
  uploadError,
  onConfirmUpload,
}: ProjectTopBarCenterProps) {
  const { setCenter } = useTopBarCenter();
  useEffect(() => {
    setCenter(
      <ProjectTopBarCenter
        plans={plans}
        activePlanId={activePlanId}
        onSelectPlan={onSelectPlan}
        canUpload={canUpload}
        pendingFile={pendingFile}
        onPendingFile={onPendingFile}
        uploadProgress={uploadProgress}
        uploadError={uploadError}
        onConfirmUpload={onConfirmUpload}
      />
    );
    return () => setCenter(null);
  }, [
    setCenter,
    plans,
    activePlanId,
    onSelectPlan,
    canUpload,
    pendingFile,
    onPendingFile,
    uploadProgress,
    uploadError,
    onConfirmUpload,
  ]);
  return null;
}
