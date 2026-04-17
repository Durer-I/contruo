"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Group,
  Panel,
  Separator,
  useDefaultLayout,
} from "react-resizable-panels";
import { AlertTriangle, Maximize2, Minus, Plus, StretchHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PlanDocumentUrlResponse, ProjectSearchResponse, SheetInfo } from "@/types/project";
import { useTopBarCenter } from "@/providers/top-bar-center-provider";

import {
  PlanPdfCanvas,
  type PlanPdfCanvasHandle,
  type PdfPoint,
} from "@/components/plan-viewer/plan-pdf-canvas";
import { viewportStorageKey } from "@/components/plan-viewer/sheet-viewport-storage";
import { TakeoffToolbar, type TakeoffTool } from "@/components/plan-viewer/takeoff-toolbar";
import { ScaleCalibrationDialog } from "@/components/plan-viewer/scale-calibration-dialog";
import { PlanSearchPanel } from "@/components/plan-viewer/plan-search-panel";

interface PlanViewerWorkspaceProps {
  projectId: string;
  projectName: string;
  sheets: SheetInfo[];
  onSheetsRefresh: () => Promise<void>;
  canEditMeasurements: boolean;
}

const PANEL_IDS = ["sheet-index", "viewer", "quantities"] as const;

export function PlanViewerWorkspace({
  projectId,
  projectName,
  sheets,
  onSheetsRefresh,
  canEditMeasurements,
}: PlanViewerWorkspaceProps) {
  const canvasRef = useRef<PlanPdfCanvasHandle>(null);
  const { setCenter } = useTopBarCenter();
  const [userSheetId, setUserSheetId] = useState<string | null>(null);
  const [docBundle, setDocBundle] = useState<{ planId: string; url: string } | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [zoomPct, setZoomPct] = useState(100);

  const [activeTool, setActiveTool] = useState<TakeoffTool>("select");
  const [scaleDraft, setScaleDraft] = useState<{ a: PdfPoint; b?: PdfPoint } | null>(null);
  const [scaleDialogOpen, setScaleDialogOpen] = useState(false);
  const [pendingPdfLength, setPendingPdfLength] = useState(0);

  const [searchPanelOpen, setSearchPanelOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchMatches, setSearchMatches] = useState<ProjectSearchResponse["matches"]>([]);
  const [pageMatchCount, setPageMatchCount] = useState(0);
  const [localPageMatchIdx, setLocalPageMatchIdx] = useState(0);

  const layoutId = `contruo-project-${projectId}`;
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    id: layoutId,
    storage: typeof window !== "undefined" ? window.localStorage : undefined,
    panelIds: [...PANEL_IDS],
  });

  const activeSheetId = useMemo(() => {
    if (sheets.length === 0) return null;
    if (userSheetId && sheets.some((s) => s.id === userSheetId)) return userSheetId;
    return sheets[0].id;
  }, [sheets, userSheetId]);

  const activeSheet = useMemo(
    () => sheets.find((s) => s.id === activeSheetId) ?? null,
    [sheets, activeSheetId]
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
    canEditMeasurements && activeTool === "scale" && !scaleDialogOpen;

  const needsScaleWarning =
    ["linear", "area", "count"].includes(activeTool) &&
    activeSheet &&
    activeSheet.scale_value == null;

  const onSearchRectsChange = useCallback((n: number) => {
    setPageMatchCount(n);
  }, []);

  useEffect(() => {
    setCenter(
      <TakeoffToolbar
        active={activeTool}
        onChange={setActiveTool}
        onSearchClick={() => setSearchPanelOpen(true)}
        canCalibrateScale={canEditMeasurements}
      />
    );
    return () => setCenter(null);
  }, [activeTool, setCenter, canEditMeasurements]);

  useEffect(() => {
    if (activeTool !== "scale") {
      setScaleDraft(null);
    }
  }, [activeTool]);

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
        setScaleDialogOpen(true);
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
      setScaleDialogOpen(false);
      setScaleDraft(null);
      setActiveTool("select");
      await onSheetsRefresh();
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
        const idx = sheets.findIndex((s) => s.id === activeSheetId);
        if (idx > 0) setUserSheetId(sheets[idx - 1].id);
      } else if (e.key === "]") {
        e.preventDefault();
        const idx = sheets.findIndex((s) => s.id === activeSheetId);
        if (idx >= 0 && idx < sheets.length - 1) {
          setUserSheetId(sheets[idx + 1].id);
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
    [sheets, activeSheetId, searchPanelOpen, nextLocalMatch, prevLocalMatch, canEditMeasurements]
  );

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onKeyDown]);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <ScaleCalibrationDialog
        open={scaleDialogOpen}
        onOpenChange={(o) => {
          setScaleDialogOpen(o);
          if (!o) setScaleDraft(null);
        }}
        pdfLineLengthPoints={pendingPdfLength}
        initialDistance=""
        initialUnit="ft"
        onSubmit={handleScaleSubmit}
      />

      <Group
        orientation="horizontal"
        className="flex min-h-0 flex-1"
        defaultLayout={defaultLayout}
        onLayoutChanged={onLayoutChanged}
      >
        <Panel
          id={PANEL_IDS[0]}
          defaultSize="18%"
          minSize={12}
          maxSize={35}
          collapsible
          className="flex min-h-0 min-w-0 flex-col border-r border-border bg-surface"
        >
          <div className="border-b border-border px-2 py-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Sheets ({sheets.length})
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-2">
            {sheets.length === 0 ? (
              <p className="p-2 text-xs text-muted-foreground">
                No sheets yet. Upload a plan from the project panel below.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {sheets.map((sheet) => {
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

        <Separator className="w-px bg-border" />

        <Panel
          id={PANEL_IDS[1]}
          minSize={40}
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

        <Separator className="w-px bg-border" />

        <Panel
          id={PANEL_IDS[2]}
          defaultSize="22%"
          minSize={14}
          maxSize={40}
          collapsible
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
