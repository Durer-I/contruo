"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { configurePdfWorker } from "@/lib/pdf-worker";
import {
  loadViewport,
  saveViewport,
  type FitMode,
  type SheetViewportState,
} from "@/components/plan-viewer/sheet-viewport-storage";
import {
  findTextMatchRects,
  type ViewportRect,
} from "@/components/plan-viewer/pdf-text-search";

import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";
import type { PageViewport } from "pdfjs-dist";

/** Return type of ``PDFPageProxy.render`` — cancel in-flight work before starting another render on the same canvas. */
type PdfPageRenderTask = ReturnType<PDFPageProxy["render"]>;

const MIN_ZOOM_MULT = 0.15;
const MAX_ZOOM_MULT = 8;
const WHEEL_FACTOR = 1.08;

function clampZoomMult(n: number): number {
  return Math.min(MAX_ZOOM_MULT, Math.max(MIN_ZOOM_MULT, n));
}

function computeFitScale(
  fitMode: FitMode,
  cw: number,
  ch: number,
  pw: number,
  ph: number
): number {
  if (fitMode === "width") return cw / pw;
  return Math.min(cw / pw, ch / ph);
}

export interface PdfPoint {
  x: number;
  y: number;
}

export interface PlanPdfCanvasHandle {
  fitWidth: () => void;
  fitPage: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  clientToPdfPoint: (clientX: number, clientY: number) => PdfPoint | null;
  pdfPointsDistance: (a: PdfPoint, b: PdfPoint) => number;
  /** Map PDF user-space point to viewport pixels (same space as canvas/CSS overlay). */
  pdfToViewportPixel: (p: PdfPoint) => { x: number; y: number } | null;
}

export type LineStyleDash = "solid" | "dashed" | "dotted";

export interface LinearOverlayPolyline {
  id: string;
  vertices: PdfPoint[];
  color: string;
  lineWidth: number;
  dash: LineStyleDash;
  /** Thicker stroke when measurement is selected (select tool). */
  emphasize?: boolean;
}

export interface LinearTakeoffHandlers {
  active: boolean;
  onPdfPoint: (pt: PdfPoint) => void;
  onHoverPdf: (pt: PdfPoint | null) => void;
  onComplete: () => void;
}

export interface AreaOverlaySaved {
  id: string;
  outer: PdfPoint[];
  holes: PdfPoint[][];
  color: string;
  fillOpacity: number;
  lineWidth: number;
  fillPattern: "solid" | "hatch" | "crosshatch";
  label?: string;
  emphasize?: boolean;
}

export interface CountMarkerOverlay {
  id: string;
  /** PDF user-space coordinates (same as geometry.position). */
  x: number;
  y: number;
  color: string;
  emphasize?: boolean;
  /** True while POST is in flight — shown immediately on click. */
  pending?: boolean;
  onPointerDown?: (e: React.PointerEvent<SVGCircleElement>) => void;
}

function dashPattern(d: LineStyleDash): string | undefined {
  if (d === "solid") return undefined;
  if (d === "dashed") return "8 6";
  return "2 5";
}

function pdfRingsToViewPath(vp: PageViewport, rings: PdfPoint[][]): string {
  const parts: string[] = [];
  for (const ring of rings) {
    if (ring.length < 2) continue;
    const pts = ring.map((p) => {
      const [vx, vy] = vp.convertToViewportPoint(p.x, p.y);
      return [vx, vy] as const;
    });
    let d = `M ${pts[0]![0]} ${pts[0]![1]}`;
    for (let i = 1; i < pts.length; i++) {
      d += ` L ${pts[i]![0]} ${pts[i]![1]}`;
    }
    d += " Z";
    parts.push(d);
  }
  return parts.join(" ");
}

interface PlanPdfCanvasProps {
  documentUrl: string | null;
  pageNumber: number;
  viewportStorageKey: string | null;
  className?: string;
  onDisplayZoomPercent?: (percent: number) => void;
  /** Scale tool: first click / second click in PDF space (for draft line). */
  calibrationMode?: boolean;
  onCalibrationPdfClick?: (pt: PdfPoint) => void;
  scaleDraftPdf?: { a: PdfPoint; b?: PdfPoint } | null;
  /** Highlight search matches on this page (same viewport as rendered canvas). */
  searchQuery?: string | null;
  /** Which match to center on (0-based). */
  searchMatchIndex?: number;
  onSearchRectsChange?: (count: number) => void;
  /** Linear takeoff: click adds vertices; double-click / parent completes. */
  linearTakeoff?: LinearTakeoffHandlers | null;
  /** Select tool: left-click in PDF space (e.g. hit-test measurements). */
  selectToolProbe?: {
    active: boolean;
    onPdfClick: (
      pt: PdfPoint,
      modifiers: { ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }
    ) => void;
  } | null;
  /** Draw saved measurements + in-progress draft (PDF coordinates). */
  linearOverlay?: {
    polylines: LinearOverlayPolyline[];
    draft?: {
      vertices: PdfPoint[];
      preview: PdfPoint | null;
      color: string;
      lineWidth: number;
      dash: LineStyleDash;
    } | null;
    vertexHandles?: {
      vertices: PdfPoint[];
      onVertexPointerDown: (index: number, e: React.PointerEvent<SVGCircleElement>) => void;
    } | null;
  } | null;
  /** Area polygon: same interaction model as linear (click chain + double-click / Enter completes). */
  areaPolygonTakeoff?: LinearTakeoffHandlers | null;
  /** Count takeoff: each full primary-button click (pointer up) places one marker — no Enter. */
  countTakeoff?: { active: boolean; onPdfClick: (pt: PdfPoint) => void } | null;
  /** Filled polygons + optional polygon draft (outer or hole stroke). */
  areaOverlay?: {
    areas: AreaOverlaySaved[];
    polygonDraft?: {
      vertices: PdfPoint[];
      preview: PdfPoint | null;
      color: string;
      fillOpacity: number;
      lineWidth: number;
      dashed?: boolean;
    } | null;
  } | null;
  /** Count markers (viewport draws on top). */
  countOverlay?: CountMarkerOverlay[] | null;
}

export const PlanPdfCanvas = forwardRef<PlanPdfCanvasHandle, PlanPdfCanvasProps>(
  function PlanPdfCanvas(
    {
      documentUrl,
      pageNumber,
      viewportStorageKey,
      className,
      onDisplayZoomPercent,
      calibrationMode,
      onCalibrationPdfClick,
      scaleDraftPdf,
      searchQuery,
      searchMatchIndex = 0,
      onSearchRectsChange,
      linearTakeoff = null,
      linearOverlay = null,
      selectToolProbe = null,
      areaPolygonTakeoff = null,
      countTakeoff = null,
      areaOverlay = null,
      countOverlay = null,
    },
    ref
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const pdfRef = useRef<PDFDocumentProxy | null>(null);
    const viewportRef = useRef<PageViewport | null>(null);
    const renderTokenRef = useRef(0);
    const activeRenderTaskRef = useRef<PdfPageRenderTask | null>(null);
    const panningRef = useRef<{
      pointerId: number;
      lastX: number;
      lastY: number;
    } | null>(null);
    const spaceDownRef = useRef(false);
    const centeredForKeyRef = useRef<string | null>(null);

    const liveRef = useRef({
      zoomMultiplier: 1,
      pan: { x: 0, y: 0 },
      fitMode: "width" as FitMode,
    });

    const [pdfError, setPdfError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [fitMode, setFitMode] = useState<FitMode>("width");
    const [zoomMultiplier, setZoomMultiplier] = useState(1);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [pageCssSize, setPageCssSize] = useState({ w: 0, h: 0 });
    const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });
    /** Mirrors the last rendered page viewport so scale overlay re-renders when ref alone updates. */
    const [pageViewport, setPageViewport] = useState<PageViewport | null>(null);
    const [searchRects, setSearchRects] = useState<ViewportRect[]>([]);

    useEffect(() => {
      liveRef.current = { zoomMultiplier, pan, fitMode };
    }, [zoomMultiplier, pan, fitMode]);

    useEffect(() => {
      pdfRef.current = null;
      setPdfError(null);
      setPageViewport(null);
      if (!documentUrl) return;

      let cancelled = false;
      setLoading(true);

      (async () => {
        try {
          await configurePdfWorker();
          const pdfjs = await import("pdfjs-dist");
          const task = pdfjs.getDocument({ url: documentUrl, withCredentials: false });
          const pdf = await task.promise;
          if (cancelled) return;
          pdfRef.current = pdf;
        } catch (e) {
          if (!cancelled) {
            setPdfError(e instanceof Error ? e.message : "Failed to load PDF");
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();

      return () => {
        cancelled = true;
      };
    }, [documentUrl]);

    useEffect(() => {
      centeredForKeyRef.current = null;
      if (!viewportStorageKey) {
        setFitMode("width");
        setZoomMultiplier(1);
        setPan({ x: 0, y: 0 });
        return;
      }
      const saved = loadViewport(viewportStorageKey);
      if (saved) {
        setFitMode(saved.fitMode);
        setZoomMultiplier(saved.zoomMultiplier);
        setPan({ x: saved.panX, y: saved.panY });
      } else {
        setFitMode("width");
        setZoomMultiplier(1);
        setPan({ x: 0, y: 0 });
      }
    }, [viewportStorageKey]);

    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;
      const ro = new ResizeObserver(() => {
        setContainerSize({ w: el.clientWidth, h: el.clientHeight });
      });
      ro.observe(el);
      setContainerSize({ w: el.clientWidth, h: el.clientHeight });
      return () => ro.disconnect();
    }, []);

    useEffect(() => {
      if (!viewportStorageKey) return;
      const t = window.setTimeout(() => {
        const state: SheetViewportState = {
          fitMode,
          zoomMultiplier,
          panX: pan.x,
          panY: pan.y,
        };
        saveViewport(viewportStorageKey, state);
      }, 400);
      return () => window.clearTimeout(t);
    }, [viewportStorageKey, fitMode, zoomMultiplier, pan.x, pan.y]);

    const clientToPdfPoint = useCallback(
      (clientX: number, clientY: number): PdfPoint | null => {
        const canvas = canvasRef.current;
        const vp = viewportRef.current;
        if (!canvas || !vp) return null;
        const r = canvas.getBoundingClientRect();
        const x = clientX - r.left;
        const y = clientY - r.top;
        const [px, py] = vp.convertToPdfPoint(x, y);
        return { x: px, y: py };
      },
      []
    );

    const renderPage = useCallback(async () => {
      const pdf = pdfRef.current;
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!pdf || !canvas || !container) return;

      activeRenderTaskRef.current?.cancel();
      activeRenderTaskRef.current = null;

      const token = ++renderTokenRef.current;
      const page = await pdf.getPage(pageNumber);
      if (token !== renderTokenRef.current) return;

      const base = page.getViewport({ scale: 1 });
      const cw = container.clientWidth;
      const ch = container.clientHeight;
      if (cw < 8 || ch < 8) return;

      const { zoomMultiplier: zm, fitMode: fm } = liveRef.current;
      const fitScale = computeFitScale(fm, cw, ch, base.width, base.height);
      const effectiveScale = fitScale * zm;
      const viewport = page.getViewport({ scale: effectiveScale });
      viewportRef.current = viewport;
      setPageViewport(viewport);

      setPageCssSize({ w: viewport.width, h: viewport.height });

      const dpr = Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 2);
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      const transform =
        dpr !== 1 ? ([dpr, 0, 0, dpr, 0, 0] as [number, number, number, number, number, number]) : undefined;

      if (token !== renderTokenRef.current) return;

      const renderTask = page.render({
        canvas,
        viewport,
        transform,
      });
      activeRenderTaskRef.current = renderTask;

      try {
        await renderTask.promise;
      } catch (e) {
        if (token !== renderTokenRef.current) return;
        if (e instanceof Error && e.name === "RenderingCancelledException") return;
        throw e;
      } finally {
        if (activeRenderTaskRef.current === renderTask) {
          activeRenderTaskRef.current = null;
        }
      }

      if (token !== renderTokenRef.current) return;

      const baseline = computeFitScale("width", cw, ch, base.width, base.height);
      const displayPct = Math.round((effectiveScale / baseline) * 100);
      onDisplayZoomPercent?.(displayPct);

      const q = searchQuery?.trim();
      if (q) {
        const rects = await findTextMatchRects(page, viewport, q);
        if (token === renderTokenRef.current) {
          setSearchRects(rects);
          onSearchRectsChange?.(rects.length);
        }
      } else {
        if (token === renderTokenRef.current) {
          setSearchRects([]);
          onSearchRectsChange?.(0);
        }
      }
    }, [pageNumber, onDisplayZoomPercent, searchQuery, onSearchRectsChange]);

    useEffect(() => {
      void renderPage();
      return () => {
        activeRenderTaskRef.current?.cancel();
        activeRenderTaskRef.current = null;
        renderTokenRef.current += 1;
      };
    }, [renderPage, documentUrl, loading, containerSize.w, containerSize.h, fitMode, zoomMultiplier]);

    // Center once per sheet when no saved viewport
    useEffect(() => {
      if (!viewportStorageKey) return;
      if (loadViewport(viewportStorageKey)) {
        centeredForKeyRef.current = viewportStorageKey;
        return;
      }
      if (centeredForKeyRef.current === viewportStorageKey) return;
      const cw = containerSize.w;
      const ch = containerSize.h;
      const { w, h } = pageCssSize;
      if (cw < 8 || ch < 8 || w < 8 || h < 8) return;
      setPan({ x: (cw - w) / 2, y: (ch - h) / 2 });
      centeredForKeyRef.current = viewportStorageKey;
    }, [viewportStorageKey, containerSize, pageCssSize]);

    // Pan to center active search match (not on every zoom/re-render of rects).
    useEffect(() => {
      if (searchRects.length === 0) return;
      const container = containerRef.current;
      if (!container) return;
      const idx =
        ((searchMatchIndex % searchRects.length) + searchRects.length) % searchRects.length;
      const r = searchRects[idx];
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const cw = container.clientWidth;
      const ch = container.clientHeight;
      setPan({ x: cw / 2 - cx, y: ch / 2 - cy });
    }, [searchMatchIndex, searchQuery, searchRects.length]);

    const runWheelZoom = useCallback(
      (clientX: number, clientY: number, deltaY: number) => {
        const pdf = pdfRef.current;
        const container = containerRef.current;
        if (!pdf || !container) return;

        const factor = deltaY < 0 ? WHEEL_FACTOR : 1 / WHEEL_FACTOR;
        const rect = container.getBoundingClientRect();
        const mx = clientX - rect.left;
        const my = clientY - rect.top;

        void (async () => {
          const page = await pdf.getPage(pageNumber);
          const base = page.getViewport({ scale: 1 });
          const cw = container.clientWidth;
          const ch = container.clientHeight;
          const s = liveRef.current;
          const oldMult = s.zoomMultiplier;
          const newMult = clampZoomMult(oldMult * factor);
          const fs = computeFitScale(s.fitMode, cw, ch, base.width, base.height);
          const oldVp = page.getViewport({ scale: fs * oldMult });
          const newVp = page.getViewport({ scale: fs * newMult });
          const u = (mx - s.pan.x) / oldVp.width;
          const v = (my - s.pan.y) / oldVp.height;
          setZoomMultiplier(newMult);
          setPan({
            x: mx - u * newVp.width,
            y: my - v * newVp.height,
          });
        })();
      },
      [pageNumber]
    );

    useImperativeHandle(
      ref,
      () => ({
        fitWidth: () => {
          void (async () => {
            const pdf = pdfRef.current;
            const container = containerRef.current;
            if (!pdf || !container) return;
            const page = await pdf.getPage(pageNumber);
            const base = page.getViewport({ scale: 1 });
            const cw = container.clientWidth;
            const ch = container.clientHeight;
            setFitMode("width");
            setZoomMultiplier(1);
            const fs = computeFitScale("width", cw, ch, base.width, base.height);
            const vp = page.getViewport({ scale: fs });
            setPan({ x: (cw - vp.width) / 2, y: (ch - vp.height) / 2 });
          })();
        },
        fitPage: () => {
          void (async () => {
            const pdf = pdfRef.current;
            const container = containerRef.current;
            if (!pdf || !container) return;
            const page = await pdf.getPage(pageNumber);
            const base = page.getViewport({ scale: 1 });
            const cw = container.clientWidth;
            const ch = container.clientHeight;
            setFitMode("page");
            setZoomMultiplier(1);
            const fs = computeFitScale("page", cw, ch, base.width, base.height);
            const vp = page.getViewport({ scale: fs });
            setPan({ x: (cw - vp.width) / 2, y: (ch - vp.height) / 2 });
          })();
        },
        zoomIn: () => {
          const el = containerRef.current;
          if (!el) return;
          const r = el.getBoundingClientRect();
          runWheelZoom(r.left + r.width / 2, r.top + r.height / 2, -48);
        },
        zoomOut: () => {
          const el = containerRef.current;
          if (!el) return;
          const r = el.getBoundingClientRect();
          runWheelZoom(r.left + r.width / 2, r.top + r.height / 2, 48);
        },
        clientToPdfPoint,
        pdfPointsDistance: (a: PdfPoint, b: PdfPoint) =>
          Math.hypot(a.x - b.x, a.y - b.y),
        pdfToViewportPixel: (p: PdfPoint) => {
          const vp = viewportRef.current;
          if (!vp) return null;
          const [vx, vy] = vp.convertToViewportPoint(p.x, p.y);
          return { x: vx, y: vy };
        },
      }),
      [pageNumber, runWheelZoom, clientToPdfPoint]
    );

    const onWheel = useCallback(
      (e: React.WheelEvent) => {
        if (!pdfRef.current) return;
        e.preventDefault();
        if (e.ctrlKey || !e.shiftKey) {
          runWheelZoom(e.clientX, e.clientY, e.deltaY);
        }
      },
      [runWheelZoom]
    );

    useEffect(() => {
      const onKeyDown = (e: KeyboardEvent) => {
        if (e.code === "Space") spaceDownRef.current = true;
      };
      const onKeyUp = (e: KeyboardEvent) => {
        if (e.code === "Space") spaceDownRef.current = false;
      };
      window.addEventListener("keydown", onKeyDown);
      window.addEventListener("keyup", onKeyUp);
      return () => {
        window.removeEventListener("keydown", onKeyDown);
        window.removeEventListener("keyup", onKeyUp);
      };
    }, []);

    const onPointerDown = (e: React.PointerEvent) => {
      if (calibrationMode && e.button === 0 && !spaceDownRef.current) {
        const pt = clientToPdfPoint(e.clientX, e.clientY);
        if (pt) {
          e.preventDefault();
          onCalibrationPdfClick?.(pt);
          return;
        }
      }

      if (
        areaPolygonTakeoff?.active &&
        e.button === 0 &&
        !spaceDownRef.current
      ) {
        const pt = clientToPdfPoint(e.clientX, e.clientY);
        if (pt) {
          e.preventDefault();
          areaPolygonTakeoff.onPdfPoint(pt);
          return;
        }
      }

      if (
        linearTakeoff?.active &&
        e.button === 0 &&
        !spaceDownRef.current
      ) {
        const pt = clientToPdfPoint(e.clientX, e.clientY);
        if (pt) {
          e.preventDefault();
          linearTakeoff.onPdfPoint(pt);
          return;
        }
      }

      if (
        selectToolProbe?.active &&
        e.button === 0 &&
        !spaceDownRef.current
      ) {
        const pt = clientToPdfPoint(e.clientX, e.clientY);
        if (pt) {
          e.preventDefault();
          selectToolProbe.onPdfClick(pt, {
            ctrlKey: e.ctrlKey,
            metaKey: e.metaKey,
            shiftKey: e.shiftKey,
          });
          return;
        }
      }

      const isMiddle = e.button === 1;
      const isLeftSpace = e.button === 0 && spaceDownRef.current;
      if (!isMiddle && !isLeftSpace) return;
      e.preventDefault();
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      panningRef.current = {
        pointerId: e.pointerId,
        lastX: e.clientX,
        lastY: e.clientY,
      };
    };

    const onPointerMove = (e: React.PointerEvent) => {
      if (areaPolygonTakeoff?.active) {
        const pt = clientToPdfPoint(e.clientX, e.clientY);
        areaPolygonTakeoff.onHoverPdf(pt);
      }
      if (linearTakeoff?.active) {
        const pt = clientToPdfPoint(e.clientX, e.clientY);
        linearTakeoff.onHoverPdf(pt);
      }
      const p = panningRef.current;
      if (!p || p.pointerId !== e.pointerId) return;
      const dx = e.clientX - p.lastX;
      const dy = e.clientY - p.lastY;
      p.lastX = e.clientX;
      p.lastY = e.clientY;
      setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
    };

    const onPointerUp = (e: React.PointerEvent) => {
      if (
        countTakeoff?.active &&
        e.button === 0 &&
        !spaceDownRef.current
      ) {
        const pt = clientToPdfPoint(e.clientX, e.clientY);
        if (pt) {
          e.preventDefault();
          countTakeoff.onPdfClick(pt);
        }
      }
      const p = panningRef.current;
      if (p && p.pointerId === e.pointerId) {
        panningRef.current = null;
      }
    };

    const vp = pageViewport;
    let scaleLine: { x1: number; y1: number; x2: number; y2: number } | null = null;
    let scalePoints: { x: number; y: number }[] = [];
    if (scaleDraftPdf?.a && vp && pageCssSize.w > 0 && pageCssSize.h > 0) {
      const v1 = vp.convertToViewportPoint(scaleDraftPdf.a.x, scaleDraftPdf.a.y);
      const b = scaleDraftPdf.b ?? scaleDraftPdf.a;
      const v2 = vp.convertToViewportPoint(b.x, b.y);
      scaleLine = { x1: v1[0], y1: v1[1], x2: v2[0], y2: v2[1] };
      scalePoints = [{ x: v1[0], y: v1[1] }];
      if (scaleDraftPdf.b) {
        scalePoints.push({ x: v2[0], y: v2[1] });
      }
    }

    return (
      <div
        ref={containerRef}
        className={`relative min-h-[200px] flex-1 overflow-hidden bg-muted/20 ${
          calibrationMode ||
          linearTakeoff?.active ||
          areaPolygonTakeoff?.active ||
          countTakeoff?.active
            ? "cursor-crosshair"
            : selectToolProbe?.active
              ? "cursor-default"
              : ""
        } ${className ?? ""}`}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={(e) => {
          if (areaPolygonTakeoff?.active) {
            e.preventDefault();
            areaPolygonTakeoff.onComplete();
            return;
          }
          if (linearTakeoff?.active) {
            e.preventDefault();
            linearTakeoff.onComplete();
          }
        }}
        role="application"
        aria-label="Plan PDF viewport"
      >
        {loading && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-background/40 text-sm text-muted-foreground">
            Loading PDF…
          </div>
        )}
        {pdfError && (
          <div className="absolute inset-0 z-10 flex items-center justify-center p-4 text-center text-sm text-destructive">
            {pdfError}
          </div>
        )}
        <div
          className="absolute inset-0"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px)`,
            willChange: "transform",
          }}
        >
          <canvas ref={canvasRef} className="block bg-white shadow-sm" />
          {scaleLine && (
            <svg
              className="pointer-events-none absolute left-0 top-0 z-[1]"
              width={pageCssSize.w}
              height={pageCssSize.h}
              aria-hidden
            >
              <line
                x1={scaleLine.x1}
                y1={scaleLine.y1}
                x2={scaleLine.x2}
                y2={scaleLine.y2}
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                strokeLinecap="round"
              />
              {scalePoints.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={5}
                  fill="hsl(var(--primary))"
                  stroke="hsl(var(--background))"
                  strokeWidth={2}
                />
              ))}
            </svg>
          )}
          {searchRects.map((r, i) => {
            const active =
              searchRects.length > 0 &&
              ((searchMatchIndex % searchRects.length) + searchRects.length) %
                searchRects.length ===
                i;
            return (
              <div
                key={`${r.left}-${r.top}-${i}`}
                className={`pointer-events-none absolute border-2 ${
                  active
                    ? "border-amber-300 bg-amber-300/25"
                    : "border-amber-500/50 bg-amber-400/10"
                }`}
                style={{
                  left: r.left,
                  top: r.top,
                  width: r.width,
                  height: r.height,
                }}
              />
            );
          })}
          {vp && pageCssSize.w > 0 && areaOverlay ? (
            <svg
              className="absolute left-0 top-0 z-[1]"
              width={pageCssSize.w}
              height={pageCssSize.h}
              aria-hidden
              style={{ pointerEvents: "none" }}
            >
              {(areaOverlay?.areas ?? []).map((ar) => {
                const rings = [ar.outer, ...ar.holes];
                const d = pdfRingsToViewPath(vp, rings);
                if (!d) return null;
                const fillOp =
                  ar.fillPattern === "solid"
                    ? ar.fillOpacity * 0.35
                    : ar.fillOpacity * 0.28;
                return (
                  <g key={ar.id}>
                    <path
                      d={d}
                      fill={ar.color}
                      fillOpacity={fillOp}
                      fillRule="evenodd"
                      stroke={ar.color}
                      strokeWidth={ar.emphasize ? ar.lineWidth + 2 : ar.lineWidth}
                      strokeOpacity={0.95}
                    />
                    {ar.label ? (() => {
                      let cx = 0;
                      let cy = 0;
                      for (const p of ar.outer) {
                        cx += p.x;
                        cy += p.y;
                      }
                      cx /= ar.outer.length;
                      cy /= ar.outer.length;
                      const [vx, vy] = vp.convertToViewportPoint(cx, cy);
                      return (
                        <text
                          x={vx}
                          y={vy}
                          textAnchor="middle"
                          dominantBaseline="middle"
                          fill="hsl(var(--foreground))"
                          fontSize={11}
                          fontWeight={600}
                          stroke="hsl(var(--background))"
                          strokeWidth={3}
                          paintOrder="stroke"
                          style={{ pointerEvents: "none" }}
                        >
                          {ar.label}
                        </text>
                      );
                    })() : null}
                  </g>
                );
              })}
              {areaOverlay?.polygonDraft && areaOverlay.polygonDraft.vertices.length > 0
                ? (() => {
                    const dr = areaOverlay.polygonDraft;
                    const pts = dr.vertices
                      .map((p) => {
                        const [vx, vy] = vp.convertToViewportPoint(p.x, p.y);
                        return `${vx},${vy}`;
                      })
                      .join(" ");
                    const last = dr.vertices[dr.vertices.length - 1]!;
                    const [lx, ly] = vp.convertToViewportPoint(last.x, last.y);
                    return (
                      <>
                        <polyline
                          fill="none"
                          stroke={dr.color}
                          strokeWidth={dr.lineWidth}
                          strokeDasharray={dr.dashed ? "6 4" : undefined}
                          strokeOpacity={0.95}
                          points={pts}
                        />
                        {dr.preview ? (
                          <line
                            x1={lx}
                            y1={ly}
                            x2={vp.convertToViewportPoint(dr.preview.x, dr.preview.y)[0]}
                            y2={vp.convertToViewportPoint(dr.preview.x, dr.preview.y)[1]}
                            stroke={dr.color}
                            strokeWidth={Math.max(1, dr.lineWidth - 0.5)}
                            strokeOpacity={0.65}
                            strokeDasharray="4 4"
                          />
                        ) : null}
                      </>
                    );
                  })()
                : null}
            </svg>
          ) : null}
          {vp && pageCssSize.w > 0 && linearOverlay ? (
            <svg
              className="absolute left-0 top-0 z-[2]"
              width={pageCssSize.w}
              height={pageCssSize.h}
              aria-hidden
              style={{ pointerEvents: "none" }}
            >
              {linearOverlay.polylines.map((pl) => {
                if (pl.vertices.length < 2) return null;
                const pts = pl.vertices
                  .map((p) => {
                    const [vx, vy] = vp.convertToViewportPoint(p.x, p.y);
                    return `${vx},${vy}`;
                  })
                  .join(" ");
                const dash = dashPattern(pl.dash);
                return (
                  <polyline
                    key={pl.id}
                    fill="none"
                    stroke={pl.color}
                    strokeWidth={pl.emphasize ? pl.lineWidth + 2 : pl.lineWidth}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeOpacity={0.92}
                    strokeDasharray={dash}
                    points={pts}
                    style={{ pointerEvents: "none" }}
                  />
                );
              })}
              {linearOverlay.draft && linearOverlay.draft.vertices.length > 0
                ? (() => {
                    const d = linearOverlay.draft;
                    const pts = d.vertices
                      .map((p) => {
                        const [vx, vy] = vp.convertToViewportPoint(p.x, p.y);
                        return `${vx},${vy}`;
                      })
                      .join(" ");
                    const dash = dashPattern(d.dash);
                    const last = d.vertices[d.vertices.length - 1]!;
                    const [lx, ly] = vp.convertToViewportPoint(last.x, last.y);
                    return (
                      <>
                        <polyline
                          fill="none"
                          stroke={d.color}
                          strokeWidth={d.lineWidth}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeOpacity={0.95}
                          strokeDasharray={dash}
                          points={pts}
                          style={{ pointerEvents: "none" }}
                        />
                        {d.preview ? (
                          <line
                            x1={lx}
                            y1={ly}
                            x2={vp.convertToViewportPoint(d.preview.x, d.preview.y)[0]}
                            y2={vp.convertToViewportPoint(d.preview.x, d.preview.y)[1]}
                            stroke={d.color}
                            strokeWidth={Math.max(1, d.lineWidth - 0.5)}
                            strokeOpacity={0.65}
                            strokeDasharray="4 4"
                            style={{ pointerEvents: "none" }}
                          />
                        ) : null}
                      </>
                    );
                  })()
                : null}
              {linearOverlay.vertexHandles
                ? linearOverlay.vertexHandles.vertices.map((v, i) => {
                    const [cx, cy] = vp.convertToViewportPoint(v.x, v.y);
                    return (
                      <circle
                        key={`vh-${i}`}
                        cx={cx}
                        cy={cy}
                        r={7}
                        fill="hsl(var(--background))"
                        stroke="hsl(var(--primary))"
                        strokeWidth={2}
                        className="cursor-grab active:cursor-grabbing"
                        style={{ pointerEvents: "auto" }}
                        onPointerDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          linearOverlay.vertexHandles?.onVertexPointerDown(i, e);
                        }}
                      />
                    );
                  })
                : null}
            </svg>
          ) : null}
          {vp && pageCssSize.w > 0 && countOverlay && countOverlay.length > 0 ? (
            <svg
              className="absolute left-0 top-0 z-[3]"
              width={pageCssSize.w}
              height={pageCssSize.h}
              aria-hidden
              style={{
                pointerEvents: countOverlay.some((m) => m.onPointerDown)
                  ? "auto"
                  : "none",
              }}
            >
              {countOverlay.map((m) => {
                const [vx, vy] = vp.convertToViewportPoint(m.x, m.y);
                return (
                  <circle
                    key={m.id}
                    cx={vx}
                    cy={vy}
                    r={m.emphasize ? 10 : 8}
                    fill={m.color}
                    fillOpacity={m.pending ? 0.72 : 0.92}
                    stroke="hsl(var(--background))"
                    strokeWidth={m.emphasize ? 2.5 : 1.5}
                    strokeDasharray={m.pending ? "4 3" : undefined}
                    className={m.onPointerDown ? "cursor-grab active:cursor-grabbing" : undefined}
                    style={{ pointerEvents: m.onPointerDown ? "auto" : "none" }}
                    onPointerDown={m.onPointerDown}
                  />
                );
              })}
            </svg>
          ) : null}
        </div>
      </div>
    );
  }
);
