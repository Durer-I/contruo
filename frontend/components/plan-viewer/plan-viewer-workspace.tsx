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
import { useStatusBarSlot } from "@/providers/status-bar-slot-provider";
import { useConditions } from "@/hooks/use-conditions";
import { ConditionManagerPanel } from "@/components/conditions/condition-manager-panel";

import {
  PlanPdfCanvas,
  type PlanPdfCanvasHandle,
  type PdfPoint,
  type AreaOverlaySaved,
} from "@/components/plan-viewer/plan-pdf-canvas";
import { viewportStorageKey } from "@/components/plan-viewer/sheet-viewport-storage";
import { TakeoffToolbar, type TakeoffTool } from "@/components/plan-viewer/takeoff-toolbar";
import { ScaleCalibrationDialog } from "@/components/plan-viewer/scale-calibration-dialog";
import { ScaleIntroDialog } from "@/components/plan-viewer/scale-intro-dialog";
import { PlanSearchPanel } from "@/components/plan-viewer/plan-search-panel";
import type { LineStyleDash } from "@/components/plan-viewer/plan-pdf-canvas";
import type {
  AreaGeometry,
  CountGeometry,
  LinearGeometry,
  MeasurementAggregatesResponse,
  MeasurementInfo,
} from "@/types/measurement";
import {
  distancePointToPolyline,
  formatLength,
  polylineLengthPdf,
  realLengthFromPdf,
} from "@/lib/linear-geometry";
import {
  distancePointToPolygonEdge,
  formatAreaQuantity,
  pointInPolygon,
  polygonAreaAbs,
  realAreaFromPdfSq,
} from "@/lib/area-geometry";
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
  canManageConditions: boolean;
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
  canManageConditions,
}: PlanViewerWorkspaceProps) {
  const canvasRef = useRef<PlanPdfCanvasHandle>(null);
  const skipSheetResetOnPlanChangeRef = useRef(false);
  const { setTakeoffSlot } = useTakeoffToolbarSlot();
  const { setStatusBarSlot } = useStatusBarSlot();
  const {
    conditions,
    loading: conditionsLoading,
    error: conditionsError,
    load: loadConditions,
  } = useConditions(projectId);
  const [activeConditionId, setActiveConditionId] = useState<string | null>(null);
  /** After first non-empty load, keep null when user clears selection (don't force-select first on refetch). */
  const conditionSelectionInitializedRef = useRef(false);
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

  const activeSheetId = useMemo(() => {
    if (planSheets.length === 0) return null;
    if (userSheetId && planSheets.some((s) => s.id === userSheetId)) return userSheetId;
    return planSheets[0]!.id;
  }, [planSheets, userSheetId]);

  const activeSheet = useMemo(
    () => planSheets.find((s) => s.id === activeSheetId) ?? null,
    [planSheets, activeSheetId]
  );

  useEffect(() => {
    void loadConditions();
  }, [loadConditions]);

  useEffect(() => {
    if (conditions.length === 0) {
      setActiveConditionId(null);
      conditionSelectionInitializedRef.current = false;
      return;
    }
    setActiveConditionId((prev) => {
      if (prev && conditions.some((c) => c.id === prev)) return prev;
      if (prev && !conditions.some((c) => c.id === prev)) {
        conditionSelectionInitializedRef.current = true;
        return conditions[0]!.id;
      }
      if (prev === null) {
        if (!conditionSelectionInitializedRef.current) {
          conditionSelectionInitializedRef.current = true;
          return conditions[0]!.id;
        }
        return null;
      }
      return prev;
    });
  }, [conditions]);

  const activeCondition = useMemo(
    () => conditions.find((c) => c.id === activeConditionId) ?? null,
    [conditions, activeConditionId]
  );

  const [sheetMeasurements, setSheetMeasurements] = useState<MeasurementInfo[]>([]);
  const [linearDraft, setLinearDraft] = useState<PdfPoint[]>([]);
  const [linearHoverPdf, setLinearHoverPdf] = useState<PdfPoint | null>(null);
  const [selectedMeasurementId, setSelectedMeasurementId] = useState<string | null>(null);
  const [measurementUndoStack, setMeasurementUndoStack] = useState<string[]>([]);
  const [measurementAggregates, setMeasurementAggregates] =
    useState<MeasurementAggregatesResponse | null>(null);

  const [areaRing, setAreaRing] = useState<PdfPoint[]>([]);
  const [areaHoverPdf, setAreaHoverPdf] = useState<PdfPoint | null>(null);
  const [selectedCountIds, setSelectedCountIds] = useState<Set<string>>(() => new Set());
  const [countDragPreview, setCountDragPreview] = useState<{
    id: string;
    x: number;
    y: number;
  } | null>(null);
  const countDragPreviewRef = useRef<{ id: string; x: number; y: number } | null>(null);
  const [countPendingDots, setCountPendingDots] = useState<
    { tempId: string; x: number; y: number }[]
  >([]);

  const loadSheetMeasurements = useCallback(async () => {
    if (!activeSheetId) {
      setSheetMeasurements([]);
      setMeasurementAggregates(null);
      return;
    }
    try {
      const r = await api.get<{
        measurements: MeasurementInfo[];
        aggregates?: MeasurementAggregatesResponse | null;
      }>(
        `/api/v1/projects/${projectId}/measurements?sheet_id=${activeSheetId}&include_aggregates=true`
      );
      setSheetMeasurements(r.measurements);
      setMeasurementAggregates(r.aggregates ?? null);
    } catch {
      setSheetMeasurements([]);
      setMeasurementAggregates(null);
    }
  }, [projectId, activeSheetId]);

  /** After condition CRUD (especially delete), CASCADE removes measurements — refetch both lists. */
  const refreshConditionsAndSheetMeasurements = useCallback(async () => {
    await loadConditions();
    await loadSheetMeasurements();
  }, [loadConditions, loadSheetMeasurements]);

  useEffect(() => {
    void loadSheetMeasurements();
  }, [loadSheetMeasurements]);

  useEffect(() => {
    const ids = new Set(sheetMeasurements.map((m) => m.id));
    setSelectedMeasurementId((prev) => (prev && ids.has(prev) ? prev : null));
    setMeasurementUndoStack((s) => s.filter((id) => ids.has(id)));
  }, [sheetMeasurements]);

  useEffect(() => {
    setLinearDraft([]);
    setLinearHoverPdf(null);
    setAreaRing([]);
    setAreaHoverPdf(null);
    setSelectedCountIds(new Set());
    setCountDragPreview(null);
    countDragPreviewRef.current = null;
    setCountPendingDots([]);
  }, [activeSheetId, activeTool]);

  useEffect(() => {
    setCountPendingDots([]);
  }, [activeConditionId]);

  useEffect(() => {
    setSelectedMeasurementId(null);
    setMeasurementUndoStack([]);
  }, [activeSheetId]);

  useEffect(() => {
    if (activeTool !== "linear") setLinearHoverPdf(null);
  }, [activeTool]);

  useEffect(() => {
    if (skipSheetResetOnPlanChangeRef.current) {
      skipSheetResetOnPlanChangeRef.current = false;
      return;
    }
    setUserSheetId(null);
  }, [activePlanId]);

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

  const linearDraftRef = useRef<PdfPoint[]>([]);
  linearDraftRef.current = linearDraft;
  const areaRingRef = useRef<PdfPoint[]>([]);
  areaRingRef.current = areaRing;

  function conditionDash(ls: string): LineStyleDash {
    if (ls === "dashed") return "dashed";
    if (ls === "dotted") return "dotted";
    return "solid";
  }

  const linearTakeoffEnabled =
    canEditMeasurements &&
    activeTool === "linear" &&
    activeSheet?.scale_value != null &&
    activeCondition?.measurement_type === "linear" &&
    Boolean(activeConditionId);

  const finishLinearMeasurement = useCallback(
    async (verts: PdfPoint[]) => {
      if (verts.length < 2 || !activeSheetId || !activeConditionId) {
        setLinearDraft([]);
        setLinearHoverPdf(null);
        return;
      }
      try {
        const created = await api.post<MeasurementInfo>(
          `/api/v1/projects/${projectId}/measurements`,
          {
            sheet_id: activeSheetId,
            condition_id: activeConditionId,
            measurement_type: "linear",
            geometry: { type: "linear", vertices: verts },
          }
        );
        setMeasurementUndoStack((s) => [...s, created.id]);
        setLinearDraft([]);
        setLinearHoverPdf(null);
        setSheetMeasurements((prev) => [...prev, created]);
        setActiveTool("select");
        void loadSheetMeasurements();
        void loadConditions();
      } catch {
        //
      }
    },
    [activeSheetId, activeConditionId, projectId, loadSheetMeasurements, loadConditions]
  );

  const areaTakeoffEnabled =
    canEditMeasurements &&
    activeTool === "area" &&
    activeSheet?.scale_value != null &&
    activeCondition?.measurement_type === "area" &&
    Boolean(activeConditionId);

  const countTakeoffEnabled =
    canEditMeasurements &&
    activeTool === "count" &&
    activeSheet?.scale_value != null &&
    activeCondition?.measurement_type === "count" &&
    Boolean(activeConditionId);

  const submitAreaPolygonStep = useCallback(() => {
    if (areaRing.length < 3) return;
    const outer = [...areaRing];
    void (async () => {
      if (!activeSheetId || !activeConditionId) return;
      try {
        const created = await api.post<MeasurementInfo>(`/api/v1/projects/${projectId}/measurements`, {
          sheet_id: activeSheetId,
          condition_id: activeConditionId,
          measurement_type: "area",
          geometry: {
            type: "area",
            shape: "polygon",
            outer,
            holes: [],
          },
        });
        setMeasurementUndoStack((s) => [...s, created.id]);
        setAreaRing([]);
        setAreaHoverPdf(null);
        setSheetMeasurements((prev) => [...prev, created]);
        setActiveTool("select");
        void loadSheetMeasurements();
        void loadConditions();
      } catch {
        //
      }
    })();
  }, [areaRing, activeSheetId, activeConditionId, projectId, loadSheetMeasurements, loadConditions]);

  const placeCountMarker = useCallback(
    async (pt: PdfPoint) => {
      if (!activeSheetId || !activeConditionId) return;
      const tempId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? `pending:${crypto.randomUUID()}`
          : `pending:${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setCountPendingDots((p) => [...p, { tempId, x: pt.x, y: pt.y }]);
      try {
        const created = await api.post<MeasurementInfo>(
          `/api/v1/projects/${projectId}/measurements`,
          {
            sheet_id: activeSheetId,
            condition_id: activeConditionId,
            measurement_type: "count",
            geometry: { type: "count", position: { x: pt.x, y: pt.y } },
          }
        );
        setCountPendingDots((p) => p.filter((d) => d.tempId !== tempId));
        setMeasurementUndoStack((s) => [...s, created.id]);
        setSheetMeasurements((prev) => [...prev, created]);
        void loadSheetMeasurements();
        void loadConditions();
      } catch {
        setCountPendingDots((p) => p.filter((d) => d.tempId !== tempId));
      }
    },
    [activeSheetId, activeConditionId, projectId, loadSheetMeasurements, loadConditions]
  );

  const handleSelectPdfPoint = useCallback(
    (
      pt: PdfPoint,
      modifiers: { ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }
    ) => {
      const tol = 10;
      let best: { id: string; d: number } | null = null;

      for (const m of sheetMeasurements) {
        if (m.measurement_type !== "count" || m.geometry.type !== "count") continue;
        const pos = m.geometry.position;
        const d = Math.hypot(pt.x - pos.x, pt.y - pos.y);
        if (d <= tol * 1.5 && (!best || d < best.d)) best = { id: m.id, d };
      }
      if (best) {
        if (modifiers.ctrlKey || modifiers.metaKey) {
          setSelectedCountIds((prev) => {
            const next = new Set(prev);
            if (next.has(best!.id)) next.delete(best!.id);
            else next.add(best!.id);
            const primary =
              next.size === 0
                ? null
                : next.has(best!.id)
                  ? best!.id
                  : [...next][0] ?? null;
            queueMicrotask(() => setSelectedMeasurementId(primary));
            return next;
          });
          return;
        }
        setSelectedMeasurementId(best.id);
        setSelectedCountIds(new Set([best.id]));
        return;
      }

      best = null;
      for (const m of sheetMeasurements) {
        if (m.measurement_type !== "area" || m.geometry.type !== "area") continue;
        const outer = m.geometry.outer.map((v) => ({ x: v.x, y: v.y }));
        if (outer.length < 3) continue;
        if (pointInPolygon(pt.x, pt.y, outer)) {
          setSelectedMeasurementId(m.id);
          setSelectedCountIds(new Set());
          return;
        }
        const d = distancePointToPolygonEdge(pt.x, pt.y, outer, true);
        if (d <= tol && (!best || d < best.d)) best = { id: m.id, d };
      }
      if (best) {
        setSelectedMeasurementId(best.id);
        setSelectedCountIds(new Set());
        return;
      }

      best = null;
      for (const m of sheetMeasurements) {
        if (m.measurement_type !== "linear" || m.geometry.type !== "linear") continue;
        const verts = m.geometry.vertices;
        const d = distancePointToPolyline(pt.x, pt.y, verts);
        if (d <= tol && (!best || d < best.d)) best = { id: m.id, d };
      }
      setSelectedMeasurementId(best ? best.id : null);
      setSelectedCountIds(new Set());
    },
    [sheetMeasurements]
  );

  const onCountMarkerPointerDown = useCallback(
    (measurementId: string, e: React.PointerEvent<SVGCircleElement>) => {
      if (!canEditMeasurements || activeTool !== "select") return;
      e.preventDefault();
      e.stopPropagation();
      const m = sheetMeasurements.find((x) => x.id === measurementId);
      if (!m || m.measurement_type !== "count" || m.geometry.type !== "count") return;
      const pos = m.geometry.position;
      const pt0 = canvasRef.current?.clientToPdfPoint(e.clientX, e.clientY);
      if (!pt0) return;
      const offset = { x: pos.x - pt0.x, y: pos.y - pt0.y };
      const el = e.currentTarget;
      el.setPointerCapture(e.pointerId);

      const onMove = (ev: PointerEvent) => {
        if (ev.pointerId !== e.pointerId) return;
        const pdf = canvasRef.current?.clientToPdfPoint(ev.clientX, ev.clientY);
        if (!pdf) return;
        const next = { id: measurementId, x: pdf.x + offset.x, y: pdf.y + offset.y };
        countDragPreviewRef.current = next;
        setCountDragPreview(next);
      };
      const onUp = async (ev: PointerEvent) => {
        if (ev.pointerId !== e.pointerId) return;
        el.removeEventListener("pointermove", onMove);
        el.removeEventListener("pointerup", onUp);
        el.removeEventListener("pointercancel", onUp);
        try {
          el.releasePointerCapture(e.pointerId);
        } catch {
          //
        }
        const final = countDragPreviewRef.current;
        countDragPreviewRef.current = null;
        setCountDragPreview(null);
        if (!final || final.id !== measurementId) return;
        const dist = Math.hypot(final.x - pos.x, final.y - pos.y);
        if (dist < 0.5) return;
        try {
          await api.patch(`/api/v1/measurements/${measurementId}`, {
            geometry: { type: "count", position: { x: final.x, y: final.y } },
          });
          setSheetMeasurements((prev) =>
            prev.map((m) =>
              m.id === measurementId
                ? {
                    ...m,
                    geometry: { type: "count" as const, position: { x: final.x, y: final.y } },
                  }
                : m
            )
          );
          void loadSheetMeasurements();
          void loadConditions();
        } catch {
          //
        }
      };
      countDragPreviewRef.current = { id: measurementId, x: pos.x, y: pos.y };
      setCountDragPreview({ id: measurementId, x: pos.x, y: pos.y });
      el.addEventListener("pointermove", onMove);
      el.addEventListener("pointerup", onUp);
      el.addEventListener("pointercancel", onUp);
    },
    [canEditMeasurements, activeTool, sheetMeasurements, loadSheetMeasurements, loadConditions]
  );

  const linearTakeoff = useMemo(() => {
    if (!linearTakeoffEnabled) return null;
    return {
      active: true,
      onPdfPoint: (pt: PdfPoint) => {
        setLinearDraft((d) => {
          if (d.length > 0) {
            const last = d[d.length - 1]!;
            if (Math.hypot(pt.x - last.x, pt.y - last.y) < 0.25) return d;
          }
          return [...d, pt];
        });
      },
      onHoverPdf: setLinearHoverPdf,
      onComplete: () => void finishLinearMeasurement(linearDraftRef.current),
    };
  }, [linearTakeoffEnabled, finishLinearMeasurement]);

  const areaPolygonTakeoff = useMemo(() => {
    if (
      !canEditMeasurements ||
      activeTool !== "area" ||
      activeSheet?.scale_value == null ||
      activeCondition?.measurement_type !== "area" ||
      !activeConditionId
    ) {
      return null;
    }
    return {
      active: true,
      onPdfPoint: (pt: PdfPoint) => {
        setAreaRing((d) => {
          if (d.length > 0) {
            const last = d[d.length - 1]!;
            if (Math.hypot(pt.x - last.x, pt.y - last.y) < 0.25) return d;
          }
          return [...d, pt];
        });
      },
      onHoverPdf: setAreaHoverPdf,
      onComplete: () => void submitAreaPolygonStep(),
    };
  }, [
    canEditMeasurements,
    activeTool,
    activeSheet?.scale_value,
    activeCondition,
    activeConditionId,
    submitAreaPolygonStep,
  ]);

  const countTakeoff = useMemo(() => {
    if (!countTakeoffEnabled) return null;
    return {
      active: true,
      onPdfClick: (pt: PdfPoint) => void placeCountMarker(pt),
    };
  }, [countTakeoffEnabled, placeCountMarker]);

  const selectToolProbe =
    canEditMeasurements && activeTool === "select"
      ? { active: true, onPdfClick: handleSelectPdfPoint }
      : null;

  const selectedMeasurement = useMemo(
    () => sheetMeasurements.find((m) => m.id === selectedMeasurementId) ?? null,
    [sheetMeasurements, selectedMeasurementId]
  );

  const compatibleConditionsForReassign = useMemo(() => {
    if (!selectedMeasurement) return [];
    return conditions.filter((c) => c.measurement_type === selectedMeasurement.measurement_type);
  }, [conditions, selectedMeasurement]);

  const onReassignMeasurementCondition = useCallback(
    async (newConditionId: string) => {
      if (!selectedMeasurementId || !newConditionId) return;
      try {
        await api.patch(`/api/v1/measurements/${selectedMeasurementId}`, {
          condition_id: newConditionId,
        });
        await loadSheetMeasurements();
        void loadConditions();
      } catch {
        //
      }
    },
    [selectedMeasurementId, loadSheetMeasurements, loadConditions]
  );

  const linearOverlay = useMemo(() => {
    const polylines = sheetMeasurements
      .filter(
        (m): m is MeasurementInfo & { geometry: LinearGeometry } =>
          m.measurement_type === "linear" && m.geometry.type === "linear"
      )
      .map((m) => {
        const c = conditions.find((x) => x.id === m.condition_id);
        const verts = m.geometry.vertices.map((v) => ({ x: v.x, y: v.y }));
        return {
          id: m.id,
          vertices: verts,
          color: c?.color ?? "#888",
          lineWidth: c?.line_width ?? 2,
          dash: conditionDash(c?.line_style ?? "solid"),
          emphasize: m.id === selectedMeasurementId,
        };
      })
      .filter((p) => p.vertices.length >= 2);

    const draft =
      linearTakeoffEnabled && linearDraft.length > 0 && activeCondition
        ? {
            vertices: linearDraft,
            preview: linearHoverPdf,
            color: activeCondition.color,
            lineWidth: activeCondition.line_width,
            dash: conditionDash(activeCondition.line_style),
          }
        : null;

    return { polylines, draft, vertexHandles: null };
  }, [
    sheetMeasurements,
    conditions,
    linearDraft,
    linearHoverPdf,
    activeCondition,
    linearTakeoffEnabled,
    selectedMeasurementId,
  ]);

  const areaOverlay = useMemo(() => {
    const areas: AreaOverlaySaved[] = sheetMeasurements
      .filter(
        (m): m is MeasurementInfo & { geometry: AreaGeometry } =>
          m.measurement_type === "area" && m.geometry.type === "area"
      )
      .map((m) => {
        const c = conditions.find((x) => x.id === m.condition_id);
        const g = m.geometry;
        return {
          id: m.id,
          outer: g.outer.map((v) => ({ x: v.x, y: v.y })),
          holes: (g.holes ?? []).map((ring) => ring.map((v) => ({ x: v.x, y: v.y }))),
          color: c?.color ?? "#888",
          fillOpacity: c?.fill_opacity ?? 0.3,
          lineWidth: c?.line_width ?? 2,
          fillPattern:
            c?.fill_pattern === "crosshatch"
              ? ("crosshatch" as const)
              : c?.fill_pattern === "hatch"
                ? ("hatch" as const)
                : ("solid" as const),
          label:
            c != null
              ? formatAreaQuantity(m.measured_value, c.unit)
              : undefined,
          emphasize: m.id === selectedMeasurementId,
        };
      });

    const polygonDraft =
      areaTakeoffEnabled && activeCondition && areaRing.length > 0
        ? {
            vertices: areaRing,
            preview: areaHoverPdf,
            color: activeCondition.color,
            fillOpacity: activeCondition.fill_opacity,
            lineWidth: activeCondition.line_width,
          }
        : null;

    if (areas.length === 0 && !polygonDraft) return null;
    return { areas, polygonDraft };
  }, [
    sheetMeasurements,
    conditions,
    selectedMeasurementId,
    areaTakeoffEnabled,
    activeCondition,
    areaRing,
    areaHoverPdf,
  ]);

  const countOverlay = useMemo(() => {
    const saved = sheetMeasurements
      .filter(
        (m): m is MeasurementInfo & { geometry: CountGeometry } =>
          m.measurement_type === "count" && m.geometry.type === "count"
      )
      .map((m) => {
        const c = conditions.find((x) => x.id === m.condition_id);
        const p = m.geometry.position;
        const px = countDragPreview?.id === m.id ? countDragPreview.x : p.x;
        const py = countDragPreview?.id === m.id ? countDragPreview.y : p.y;
        return {
          id: m.id,
          x: px,
          y: py,
          color: c?.color ?? "#f43f5e",
          emphasize: selectedCountIds.has(m.id),
          onPointerDown:
            canEditMeasurements && activeTool === "select"
              ? (ev: React.PointerEvent<SVGCircleElement>) =>
                  onCountMarkerPointerDown(m.id, ev)
              : undefined,
        };
      });
    const pending = countPendingDots.map((d) => ({
      id: d.tempId,
      x: d.x,
      y: d.y,
      color: activeCondition?.color ?? "#f43f5e",
      emphasize: false,
      pending: true as const,
    }));
    return [...saved, ...pending];
  }, [
    sheetMeasurements,
    conditions,
    selectedCountIds,
    countDragPreview,
    countPendingDots,
    activeCondition,
    canEditMeasurements,
    activeTool,
    onCountMarkerPointerDown,
  ]);

  const linearRunningDisplay = useMemo(() => {
    if (!activeSheet || activeSheet.scale_value == null || !activeCondition) return null;
    if (linearDraft.length < 2) return null;
    const pdfLen = polylineLengthPdf(linearDraft);
    const r = realLengthFromPdf(pdfLen, activeSheet.scale_value, activeSheet.scale_unit);
    if (r == null) return null;
    return formatLength(r, activeSheet.scale_unit, activeCondition.unit);
  }, [linearDraft, activeSheet, activeCondition]);

  const areaDraftRunningDisplay = useMemo(() => {
    if (
      !activeSheet ||
      activeSheet.scale_value == null ||
      !activeCondition ||
      activeTool !== "area" ||
      areaRing.length < 3
    ) {
      return null;
    }
    const pdfSq = polygonAreaAbs(areaRing);
    const r = realAreaFromPdfSq(pdfSq, activeSheet.scale_value);
    if (r == null) return null;
    return formatAreaQuantity(r, activeCondition.unit);
  }, [activeSheet, activeCondition, activeTool, areaRing]);

  const countAggregateLabel = useMemo(() => {
    if (!activeConditionId || activeCondition?.measurement_type !== "count" || !measurementAggregates) {
      return null;
    }
    const row = measurementAggregates.sheet_by_condition.find(
      (x) => x.condition_id === activeConditionId && x.measurement_type === "count"
    );
    if (!row) return null;
    const n = Math.round(row.sum_measured_value);
    return `${activeCondition?.name ?? "Count"}: ${n}`;
  }, [measurementAggregates, activeConditionId, activeCondition]);

  const projectCountHint = useMemo(() => {
    if (!activeConditionId || activeCondition?.measurement_type !== "count" || !measurementAggregates) {
      return null;
    }
    const row = measurementAggregates.project_by_condition.find(
      (x) => x.condition_id === activeConditionId && x.measurement_type === "count"
    );
    if (!row) return null;
    return `Project: ${Math.round(row.sum_measured_value)}`;
  }, [measurementAggregates, activeConditionId, activeCondition]);

  const areaAggregateSheetLabel = useMemo(() => {
    if (!activeConditionId || activeCondition?.measurement_type !== "area" || !measurementAggregates) {
      return null;
    }
    const row = measurementAggregates.sheet_by_condition.find(
      (x) => x.condition_id === activeConditionId && x.measurement_type === "area"
    );
    if (!row || !activeCondition) return null;
    return `Sheet: ${formatAreaQuantity(row.sum_measured_value, activeCondition.unit)}`;
  }, [measurementAggregates, activeConditionId, activeCondition]);

  const areaAggregateProjectLabel = useMemo(() => {
    if (!activeConditionId || activeCondition?.measurement_type !== "area" || !measurementAggregates) {
      return null;
    }
    const row = measurementAggregates.project_by_condition.find(
      (x) => x.condition_id === activeConditionId && x.measurement_type === "area"
    );
    if (!row || !activeCondition) return null;
    return `Project: ${formatAreaQuantity(row.sum_measured_value, activeCondition.unit)}`;
  }, [measurementAggregates, activeConditionId, activeCondition]);

  const onSearchRectsChange = useCallback((n: number) => {
    setPageMatchCount(n);
  }, []);

  const toolLabel = useCallback((t: TakeoffTool) => {
    const labels: Record<TakeoffTool, string> = {
      select: "Select",
      linear: "Linear",
      area: "Area",
      count: "Count",
      scale: "Scale",
    };
    return labels[t];
  }, []);

  useEffect(() => {
    setTakeoffSlot(
      <TakeoffToolbar
        active={activeTool}
        onChange={setActiveTool}
        onSearchClick={() => setSearchPanelOpen(true)}
        canCalibrateScale={canEditMeasurements}
        conditions={conditions}
        activeConditionId={activeConditionId}
        onConditionChange={(id) => setActiveConditionId(id)}
        conditionPickerDisabled={conditionsLoading || conditions.length === 0}
      />
    );
    return () => setTakeoffSlot(null);
  }, [
    activeTool,
    setTakeoffSlot,
    canEditMeasurements,
    conditions,
    activeConditionId,
    conditionsLoading,
  ]);

  useEffect(() => {
    setStatusBarSlot(
      <>
        <span className="shrink-0 text-muted-foreground">Condition</span>
        {activeCondition ? (
          <>
            <span
              className="h-2 w-2 shrink-0 rounded-full border border-border"
              style={{ backgroundColor: activeCondition.color }}
            />
            <span className="min-w-0 truncate font-medium text-foreground">
              {activeCondition.name}
            </span>
          </>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
        <span className="mx-2 text-border">|</span>
        <span className="shrink-0 text-muted-foreground">Tool</span>
        <span className="font-medium text-foreground">{toolLabel(activeTool)}</span>
        {conditionsError ? (
          <>
            <span className="mx-2 text-border">|</span>
            <span className="truncate text-destructive">{conditionsError}</span>
          </>
        ) : null}
      </>
    );
    return () => setStatusBarSlot(null);
  }, [
    activeCondition,
    activeTool,
    conditionsError,
    setStatusBarSlot,
    toolLabel,
  ]);

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
      void loadSheetMeasurements();
      void loadConditions();
      setScaleDraft(null);
      setActiveTool("select");
    },
    [activeSheetId, pendingPdfLength, onSheetsRefresh, loadSheetMeasurements, loadConditions]
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

      if (e.key === "Escape") {
        if (areaRingRef.current.length > 0) {
          e.preventDefault();
          setAreaRing([]);
          setAreaHoverPdf(null);
          return;
        }
        if (linearDraftRef.current.length > 0) {
          e.preventDefault();
          setLinearDraft([]);
          setLinearHoverPdf(null);
          return;
        }
        if (activeTool === "count") {
          e.preventDefault();
          setActiveTool("select");
          return;
        }
      }
      if ((e.key === "Delete" || e.key === "Backspace") && canEditMeasurements) {
        const idsToDelete =
          selectedCountIds.size > 0
            ? [...selectedCountIds]
            : selectedMeasurementId
              ? [selectedMeasurementId]
              : [];
        if (idsToDelete.length === 0) return;
        e.preventDefault();
        void (async () => {
          try {
            await Promise.all(
              idsToDelete.map((mid) => api.delete(`/api/v1/measurements/${mid}`))
            );
            setSelectedMeasurementId(null);
            setSelectedCountIds(new Set());
            setMeasurementUndoStack((s) => s.filter((x) => !idsToDelete.includes(x)));
            await loadSheetMeasurements();
            void loadConditions();
          } catch {
            //
          }
        })();
        return;
      }
      if (e.key === "Enter" && activeTool === "linear" && linearDraftRef.current.length >= 2) {
        e.preventDefault();
        void finishLinearMeasurement(linearDraftRef.current);
        return;
      }
      if (e.key === "Enter" && activeTool === "area" && areaRingRef.current.length >= 3) {
        e.preventDefault();
        submitAreaPolygonStep();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        if (activeTool === "area" && areaRingRef.current.length > 0) {
          e.preventDefault();
          setAreaRing((d) => d.slice(0, -1));
          return;
        }
        if (linearDraftRef.current.length > 0) {
          e.preventDefault();
          setLinearDraft((d) => d.slice(0, -1));
          return;
        }
        if (measurementUndoStack.length > 0 && canEditMeasurements) {
          e.preventDefault();
          const id = measurementUndoStack[measurementUndoStack.length - 1]!;
          void (async () => {
            try {
              await api.delete(`/api/v1/measurements/${id}`);
              setMeasurementUndoStack((s) => s.slice(0, -1));
              await loadSheetMeasurements();
              void loadConditions();
            } catch {
              //
            }
          })();
          return;
        }
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
        if (/^[1-9]$/.test(e.key) && conditions.length > 0) {
          const idx = parseInt(e.key, 10) - 1;
          if (idx < conditions.length && idx < 9) {
            e.preventDefault();
            const c = conditions[idx]!;
            if (activeTool === "linear" || activeTool === "area" || activeTool === "count") {
              if (c.measurement_type !== activeTool) {
                setActiveTool(c.measurement_type as TakeoffTool);
              }
            }
            setActiveConditionId(c.id);
            return;
          }
        }
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
      conditions,
      activeTool,
      finishLinearMeasurement,
      submitAreaPolygonStep,
      measurementUndoStack,
      loadSheetMeasurements,
      loadConditions,
      selectedMeasurementId,
      selectedCountIds,
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

          {activeTool === "linear" &&
            activeCondition &&
            activeCondition.measurement_type !== "linear" && (
              <div className="flex shrink-0 items-center gap-2 border-b border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-100">
                <span>
                  Select a <strong className="font-semibold">linear</strong> condition in the panel
                  (or create one) to draw linear takeoff.
                </span>
              </div>
            )}

          {activeTool === "area" &&
            activeCondition &&
            activeCondition.measurement_type !== "area" && (
              <div className="flex shrink-0 items-center gap-2 border-b border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-100">
                <span>
                  Select an <strong className="font-semibold">area</strong> condition in the panel (or
                  create one) for area takeoff.
                </span>
              </div>
            )}

          {activeTool === "count" &&
            activeCondition &&
            activeCondition.measurement_type !== "count" && (
              <div className="flex shrink-0 items-center gap-2 border-b border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-100">
                <span>
                  Select a <strong className="font-semibold">count</strong> condition in the panel (or
                  create one) for count takeoff.
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
            linearTakeoff={linearTakeoff}
            linearOverlay={linearOverlay}
            areaPolygonTakeoff={areaPolygonTakeoff}
            countTakeoff={countTakeoff}
            areaOverlay={areaOverlay}
            countOverlay={countOverlay}
            selectToolProbe={selectToolProbe}
            className="min-h-0 flex-1"
          />

          <div
            className="h-0.5 shrink-0"
            style={{
              backgroundColor: activeCondition?.color ?? "transparent",
              opacity: activeCondition ? 0.85 : 0,
            }}
            aria-hidden
          />

          {selectedMeasurementId &&
            selectedMeasurement &&
            canEditMeasurements &&
            activeTool === "select" &&
            compatibleConditionsForReassign.length > 0 ? (
            <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-border bg-surface px-3 py-1.5 text-[11px]">
              <span className="text-muted-foreground">Change condition</span>
              <select
                className="max-w-[200px] rounded-md border border-border bg-background px-2 py-0.5 text-[11px]"
                value={selectedMeasurement.condition_id}
                onChange={(e) => void onReassignMeasurementCondition(e.target.value)}
              >
                {compatibleConditionsForReassign.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

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
            {linearRunningDisplay && (
              <>
                <span className="mx-2 text-border">|</span>
                <span className="font-mono text-[11px] text-primary">
                  Draft: {linearRunningDisplay}
                </span>
              </>
            )}
            {areaDraftRunningDisplay && (
              <>
                <span className="mx-2 text-border">|</span>
                <span className="font-mono text-[11px] text-primary">
                  Draft area: {areaDraftRunningDisplay}
                </span>
              </>
            )}
            {countAggregateLabel && (
              <>
                <span className="mx-2 text-border">|</span>
                <span className="font-mono text-[11px] text-foreground/90">
                  {countAggregateLabel}
                  {projectCountHint ? ` · ${projectCountHint}` : ""}
                </span>
              </>
            )}
            {activeCondition?.measurement_type === "area" && areaAggregateSheetLabel && (
              <>
                <span className="mx-2 text-border">|</span>
                <span className="min-w-0 truncate font-mono text-[11px] text-foreground/90">
                  {areaAggregateSheetLabel}
                  {areaAggregateProjectLabel ? ` · ${areaAggregateProjectLabel}` : ""}
                </span>
              </>
            )}
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
          {conditionsLoading ? (
            <div className="flex flex-1 items-center justify-center gap-2 p-4 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading conditions…
            </div>
          ) : (
            <ConditionManagerPanel
              projectId={projectId}
              conditions={conditions}
              activeConditionId={activeConditionId}
              onActiveConditionChange={setActiveConditionId}
              onConditionsChange={refreshConditionsAndSheetMeasurements}
              onSheetMeasurementsRefresh={loadSheetMeasurements}
              canManage={canManageConditions}
            />
          )}
        </Panel>
      </Group>
    </div>
  );
}
