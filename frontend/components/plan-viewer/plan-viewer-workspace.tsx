"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Group,
  Panel,
  Separator,
  useDefaultLayout,
} from "react-resizable-panels";
import {
  AlertTriangle,
  Loader2,
  Maximize2,
  Minus,
  Plus,
  StretchHorizontal,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  PlanDocumentUrlResponse,
  PlanInfo,
  ProjectSearchResponse,
  SheetInfo,
} from "@/types/project";
import { useTakeoffToolbarSlot } from "@/providers/takeoff-toolbar-slot-provider";

import {
  PlanPdfCanvas,
  type PlanPdfCanvasHandle,
  type PdfPoint,
} from "@/components/plan-viewer/plan-pdf-canvas";
import { viewportStorageKey } from "@/components/plan-viewer/sheet-viewport-storage";
import { TakeoffToolbar, type TakeoffTool } from "@/components/plan-viewer/takeoff-toolbar";
import { ScaleCalibrationDialog } from "@/components/plan-viewer/scale-calibration-dialog";
import { ScaleIntroDialog } from "@/components/plan-viewer/scale-intro-dialog";
import { PlanSearchPanel } from "@/components/plan-viewer/plan-search-panel";

interface PlanViewerWorkspaceProps {
  projectId: string;
  projectName: string;
  plans: PlanInfo[];
  activePlanId: string;
  onActivePlanChange: (planId: string) => void;
  /** All sheets in the project (filtered to `activePlanId` for the index + viewer). */
  sheets: SheetInfo[];
  onSheetsRefresh: () => Promise<void>;
  /** Parent silent refetch in progress (e.g. after saving scale). */
  sheetsRefreshing?: boolean;
  canEditMeasurements: boolean;
}

const PANEL_IDS = ["sheet-index", "viewer", "quantities"] as const;

type ScaleFlowStep = "idle" | "intro" | "picking" | "input";

export function PlanViewerWorkspace({
  projectId,
  projectName,
  plans,
  activePlanId,
  onActivePlanChange,
  sheets,
  onSheetsRefresh,
  sheetsRefreshing = false,
  canEditMeasurements,
}: PlanViewerWorkspaceProps) {
  const canvasRef = useRef<PlanPdfCanvasHandle>(null);
  const skipSheetResetOnPlanChangeRef = useRef(false);
  const { setTakeoffSlot } = useTakeoffToolbarSlot();
  const [userSheetId, setUserSheetId] = useState<string | null>(null);
  const [docBundle, setDocBundle] = useState<{ planId: string; url: string } | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [zoomPct, setZoomPct] = useState(100);

  const [activeTool, setActiveTool] = useState<TakeoffTool>("select");
  const [scaleDraft, setScaleDraft] = useState<{ a: PdfPoint; b?: PdfPoint } | null>(null);
  const [scaleStep, setScaleStep] = useState<ScaleFlowStep>("idle");
  const [pendingPdfLength, setPendingPdfLength] = useState(0);

  const [searchPanelOpen, setSearchPanelOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchMatches, setSearchMatches] = useState<ProjectSearchResponse["matches"]>([]);
  const [pageMatchCount, setPageMatchCount] = useState(0);
  const [localPageMatchIdx, setLocalPageMatchIdx] = useState(0);

  /** Bump version when default proportions change so users get the new baseline once. */
  const layoutId = `contruo-plan-workspace-${projectId}-v3`;
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    id: layoutId,
    storage: typeof window !== "undefined" ? window.localStorage : undefined,
    panelIds: [...PANEL_IDS],
  });

  const planSheets = useMemo(
    () => sheets.filter((s) => s.plan_id === activePlanId),
    [sheets, activePlanId]
  );

  useEffect(() => {
    if (skipSheetResetOnPlanChangeRef.current) {
      skipSheetResetOnPlanChangeRef.current = false;
      return;
    }
    setUserSheetId(null);
  }, [activePlanId]);

  const activeSheetId = useMemo(() => {
    if (planSheets.length === 0) return null;
    if (userSheetId && planSheets.some((s) => s.id === userSheetId)) return userSheetId;
    return planSheets[0].id;
  }, [planSheets, userSheetId]);

  const activeSheet = useMemo(
    () => planSheets.find((s) => s.id === activeSheetId) ?? null,
    [planSheets, activeSheetId]
  );

  const planId = activeSheet?.plan_id ?? null;

  const docUrl =
    planId && docBundle?.planId === planId ? docBundle.url : null;

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchQuery), 280);
    return () => window.clearTimeout(t);
  }, [searchQuery]);

  useEffect(() => {
    if (debouncedSearch.trim().length < 2) {
      setSearchMatches([]);
      setSearchLoading(false);
      return;
    }
    let alive = true;
    setSearchLoading(true);
    api
      .get<ProjectSearchResponse>(
        `/api/v1/projects/${projectId}/search?q=${encodeURIComponent(debouncedSearch.trim())}`
      )
      .then((r) => {
        if (!alive) return;
        setSearchMatches(r.matches);
      })
      .catch(() => {
        if (!alive) return;
        setSearchMatches([]);
      })
      .finally(() => {
        if (alive) setSearchLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [debouncedSearch, projectId]);

  useEffect(() => {
    setLocalPageMatchIdx(0);
  }, [activeSheetId, debouncedSearch]);

  useEffect(() => {
    if (!planId) {
      return;
    }
    let alive = true;
    api
      .get<PlanDocumentUrlResponse>(`/api/v1/plans/${planId}/document-url`)
      .then((r) => {
        if (!alive) return;
        setDocError(null);
        setDocBundle({ planId, url: r.url });
      })
      .catch((e) => {
        if (!alive) return;
        setDocBundle(null);
        setDocError(e instanceof ApiError ? e.message : "Could not load plan file");
      });
    return () => {
      alive = false;
    };
  }, [planId]);

  const vpKey = activeSheet
    ? viewportStorageKey(projectId, activeSheet.id)
    : null;

  const calibrationMode =
    canEditMeasurements && activeTool === "scale" && scaleStep === "picking";

  const needsScaleWarning =
    ["linear", "area", "count"].includes(activeTool) &&
    activeSheet &&
    activeSheet.scale_value == null;

  const onSearchRectsChange = useCallback((n: number) => {
    setPageMatchCount(n);
  }, []);

  useEffect(() => {
    setTakeoffSlot(
      <TakeoffToolbar
        active={activeTool}
        onChange={setActiveTool}
        onSearchClick={() => setSearchPanelOpen(true)}
        canCalibrateScale={canEditMeasurements}
      />
    );
    return () => setTakeoffSlot(null);
  }, [activeTool, setTakeoffSlot, canEditMeasurements]);

  useEffect(() => {
    if (activeTool !== "scale" || !canEditMeasurements) {
      setScaleStep("idle");
      if (activeTool !== "scale") {
        setScaleDraft(null);
      }
      return;
    }
    setScaleStep("intro");
    setScaleDraft(null);
  }, [activeTool, canEditMeasurements]);

  useEffect(() => {
    if (!canEditMeasurements && activeTool === "scale") {
      setActiveTool("select");
    }
  }, [canEditMeasurements, activeTool]);

  const onCalibrationPdfClick = useCallback(
    (pt: PdfPoint) => {
      if (!scaleDraft) {
        setScaleDraft({ a: pt });
        return;
      }
      if (!scaleDraft.b) {
        const d = canvasRef.current?.pdfPointsDistance(scaleDraft.a, pt) ?? 0;
        if (d < 2) {
          setScaleDraft({ a: pt });
          return;
        }
        setScaleDraft({ a: scaleDraft.a, b: pt });
        setPendingPdfLength(d);
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            setScaleStep("input");
          });
        });
        return;
      }
      setScaleDraft({ a: pt });
    },
    [scaleDraft]
  );

  const handleScaleSubmit = useCallback(
    async (realDistance: number, realUnit: string) => {
      if (!activeSheetId) return;
      await api.patch(`/api/v1/sheets/${activeSheetId}/scale`, {
        pdf_line_length_points: pendingPdfLength,
        real_distance: realDistance,
        real_unit: realUnit,
      });
      await onSheetsRefresh();
      setScaleDraft(null);
      setActiveTool("select");
    },
    [activeSheetId, pendingPdfLength, onSheetsRefresh]
  );

  const nextLocalMatch = useCallback(() => {
    if (pageMatchCount <= 0) return;
    setLocalPageMatchIdx((i) => (i + 1) % pageMatchCount);
  }, [pageMatchCount]);

  const prevLocalMatch = useCallback(() => {
    if (pageMatchCount <= 0) return;
    setLocalPageMatchIdx((i) => (i - 1 + pageMatchCount) % pageMatchCount);
  }, [pageMatchCount]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.isContentEditable)
      ) {
        if (searchPanelOpen && t.tagName === "INPUT") {
          if (e.key === "Escape") {
            e.preventDefault();
            setSearchPanelOpen(false);
            return;
          }
          if (e.key === "Enter") {
            e.preventDefault();
            if (e.shiftKey) prevLocalMatch();
            else nextLocalMatch();
            return;
          }
        }
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setSearchPanelOpen((o) => !o);
        return;
      }

      if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        canvasRef.current?.zoomIn();
      } else if (e.key === "-" || e.key === "_") {
        e.preventDefault();
        canvasRef.current?.zoomOut();
      } else if (e.key === "[") {
        e.preventDefault();
        const idx = planSheets.findIndex((s) => s.id === activeSheetId);
        if (idx > 0) setUserSheetId(planSheets[idx - 1].id);
      } else if (e.key === "]") {
        e.preventDefault();
        const idx = planSheets.findIndex((s) => s.id === activeSheetId);
        if (idx >= 0 && idx < planSheets.length - 1) {
          setUserSheetId(planSheets[idx + 1].id);
        }
      } else if (!e.ctrlKey && !e.metaKey && !e.altKey) {
        const k = e.key.toLowerCase();
        if (["v", "l", "a", "c", "s"].includes(k)) {
          e.preventDefault();
          if (k === "s" && !canEditMeasurements) return;
          const map: Record<string, TakeoffTool> = {
            v: "select",
            l: "linear",
            a: "area",
            c: "count",
            s: "scale",
          };
          setActiveTool(map[k]!);
        }
      }
    },
    [
      planSheets,
      activeSheetId,
      searchPanelOpen,
      nextLocalMatch,
      prevLocalMatch,
      canEditMeasurements,
    ]
  );

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onKeyDown]);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <ScaleIntroDialog
        open={scaleStep === "intro"}
        onContinue={() => setScaleStep("picking")}
        onCancel={() => setActiveTool("select")}
      />

      <ScaleCalibrationDialog
        open={scaleStep === "input"}
        onCancel={() => {
          setActiveTool("select");
          setScaleDraft(null);
        }}
        pdfLineLengthPoints={pendingPdfLength}
        initialDistance=""
        initialUnit="ft"
        onSubmit={handleScaleSubmit}
      />

      {/* react-resizable-panels: numeric minSize/maxSize = pixels; use "25%" / "1px" strings for % / px. */}
      <Group
        id={layoutId}
        orientation="horizontal"
        className="flex min-h-0 flex-1"
        defaultLayout={defaultLayout}
        onLayoutChanged={onLayoutChanged}
      >
        <Panel
          id={PANEL_IDS[0]}
          defaultSize="15%"
          minSize="1px"
          maxSize="100%"
          className="flex min-h-0 min-w-0 flex-col border-r border-border bg-surface"
        >
          <div className="border-b border-border px-2 py-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Sheets ({planSheets.length})
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-2">
            {planSheets.length === 0 ? (
              <p className="p-2 text-xs text-muted-foreground">
                {plans.some((p) => p.id === activePlanId)
                  ? "No sheets for this plan yet. It may still be processing — switch plan in the top bar if needed."
                  : "No sheets yet. Add a plan from the top bar (upload icon)."}
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {planSheets.map((sheet) => {
                  const isActive = sheet.id === activeSheetId;
                  const scaleOk = sheet.scale_value != null;
                  return (
                    <li key={sheet.id}>
                      <button
                        type="button"
                        onClick={() => setUserSheetId(sheet.id)}
                        className={cn(
                          "flex w-full flex-col items-start gap-1 rounded-md border p-2 text-left transition-colors",
                          isActive
                            ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                            : "border-transparent bg-card hover:border-primary/40 hover:bg-surface-overlay"
                        )}
                      >
                        {sheet.thumbnail_url ? (
                          // eslint-disable-next-line @next/next/no-img-element -- signed remote URL
                          <img
                            src={sheet.thumbnail_url}
                            alt=""
                            className="aspect-[4/3] w-full rounded-sm border border-border object-cover"
                          />
                        ) : (
                          <div className="flex aspect-[4/3] w-full items-center justify-center rounded-sm border border-border bg-background text-[10px] text-muted-foreground">
                            {sheet.page_number}
                          </div>
                        )}
                        <span className="line-clamp-2 w-full text-[11px] font-medium leading-tight">
                          {sheet.sheet_name ?? `Page ${sheet.page_number}`}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {scaleOk
                            ? sheet.scale_label ??
                              `${sheet.scale_value?.toPrecision(3)} ${sheet.scale_unit}/pt`
                            : "Not calibrated"}
                          {sheet.scale_source === "auto" ? " · Auto" : ""}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </Panel>

        <Separator
          className={cn(
            "relative z-10 w-2 max-w-2 shrink-0 bg-border",
            "transition-colors hover:bg-primary/35 data-[separator=active]:bg-primary/50 data-[separator=focus]:bg-primary/30"
          )}
        />

        <Panel
          id={PANEL_IDS[1]}
          defaultSize="70%"
          minSize="1px"
          maxSize="100%"
          className="relative flex min-h-0 min-w-0 flex-col bg-background"
        >
          <div className="flex shrink-0 items-center gap-1 border-b border-border bg-surface px-2 py-1">
            <span className="mr-2 min-w-0 truncate text-xs font-medium text-muted-foreground">
              {projectName}
            </span>
            <div className="ml-auto flex items-center gap-0.5">
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                title="Zoom out (−)"
                onClick={() => canvasRef.current?.zoomOut()}
              >
                <Minus className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                title="Zoom in (+)"
                onClick={() => canvasRef.current?.zoomIn()}
              >
                <Plus className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                title="Fit width"
                onClick={() => canvasRef.current?.fitWidth()}
              >
                <StretchHorizontal className="mr-1 h-3.5 w-3.5" />
                Width
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                title="Fit page"
                onClick={() => canvasRef.current?.fitPage()}
              >
                <Maximize2 className="mr-1 h-3.5 w-3.5" />
                Page
              </Button>
            </div>
          </div>

          {sheetsRefreshing && (
            <div
              className="flex shrink-0 items-center gap-2 border-b border-border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground"
              role="status"
              aria-live="polite"
            >
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-hidden />
              <span>Updating sheet data…</span>
            </div>
          )}

          {needsScaleWarning && (
            <div className="flex shrink-0 items-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>
                Calibrate scale (S) before measuring — this sheet is not calibrated.
              </span>
            </div>
          )}

          {docError && (
            <div className="border-b border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {docError}
            </div>
          )}

          <PlanSearchPanel
            open={searchPanelOpen}
            query={searchQuery}
            onQueryChange={setSearchQuery}
            onClose={() => setSearchPanelOpen(false)}
            matches={searchMatches}
            loading={searchLoading}
            activeSheetId={activeSheetId}
            onPickSheet={(id) => {
              const hit = sheets.find((s) => s.id === id);
              if (hit && hit.plan_id !== activePlanId) {
                skipSheetResetOnPlanChangeRef.current = true;
                onActivePlanChange(hit.plan_id);
              }
              setUserSheetId(id);
              setSearchPanelOpen(false);
            }}
            localMatchIndex={localPageMatchIdx}
            localMatchCount={pageMatchCount}
            onPrevLocal={prevLocalMatch}
            onNextLocal={nextLocalMatch}
          />

          <PlanPdfCanvas
            ref={canvasRef}
            documentUrl={docUrl}
            pageNumber={activeSheet?.page_number ?? 1}
            viewportStorageKey={vpKey}
            onDisplayZoomPercent={setZoomPct}
            calibrationMode={calibrationMode}
            onCalibrationPdfClick={canEditMeasurements ? onCalibrationPdfClick : undefined}
            scaleDraftPdf={activeTool === "scale" ? scaleDraft : null}
            searchQuery={debouncedSearch.trim().length >= 2 ? debouncedSearch.trim() : null}
            searchMatchIndex={localPageMatchIdx}
            onSearchRectsChange={onSearchRectsChange}
            className="min-h-0 flex-1"
          />

          <div className="flex h-7 shrink-0 items-center border-t border-border bg-surface px-3 text-xs text-muted-foreground">
            <span className="min-w-0 truncate">
              {activeSheet
                ? activeSheet.sheet_name ?? `Page ${activeSheet.page_number}`
                : "No sheet"}
            </span>
            <span className="mx-2 text-border">|</span>
            <span>{zoomPct}%</span>
            <span className="mx-2 text-border">|</span>
            <span className="min-w-0 truncate font-mono text-[11px] text-foreground/90">
              {activeSheet?.scale_value != null
                ? activeSheet.scale_label ??
                  `${activeSheet.scale_value.toPrecision(4)} ${activeSheet.scale_unit}/pt`
                : "Scale: not calibrated"}
              {activeSheet?.scale_source === "auto" ? " (auto)" : ""}
            </span>
            <span className="mx-2 text-border">|</span>
            <span className="hidden sm:inline">
              Wheel zoom · Middle-click or Space+drag pan · [ ] sheets · Ctrl+F find
            </span>
          </div>
        </Panel>

        <Separator
          className={cn(
            "relative z-10 w-2 max-w-2 shrink-0 bg-border",
            "transition-colors hover:bg-primary/35 data-[separator=active]:bg-primary/50 data-[separator=focus]:bg-primary/30"
          )}
        />

        <Panel
          id={PANEL_IDS[2]}
          defaultSize="15%"
          minSize="1px"
          maxSize="100%"
          className="flex min-h-0 min-w-0 flex-col border-l border-border bg-surface"
        >
          <div className="border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Quantities
          </div>
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center text-xs text-muted-foreground">
            <p>Quantities panel ships in a later sprint.</p>
            <p className="text-[10px]">
              Tree view, overrides, and bidirectional linking will appear here.
            </p>
          </div>
        </Panel>
      </Group>
    </div>
  );
}
