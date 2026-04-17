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

import type { PDFDocumentProxy } from "pdfjs-dist";
import type { PageViewport } from "pdfjs-dist";

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
    },
    ref
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const pdfRef = useRef<PDFDocumentProxy | null>(null);
    const viewportRef = useRef<PageViewport | null>(null);
    const renderTokenRef = useRef(0);
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
    const [searchRects, setSearchRects] = useState<ViewportRect[]>([]);

    useEffect(() => {
      liveRef.current = { zoomMultiplier, pan, fitMode };
    }, [zoomMultiplier, pan, fitMode]);

    useEffect(() => {
      pdfRef.current = null;
      setPdfError(null);
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

      setPageCssSize({ w: viewport.width, h: viewport.height });

      const dpr = Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 2);
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      const transform =
        dpr !== 1 ? ([dpr, 0, 0, dpr, 0, 0] as [number, number, number, number, number, number]) : undefined;

      await page
        .render({
          canvas,
          viewport,
          transform,
        })
        .promise;

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
        setSearchRects([]);
        onSearchRectsChange?.(0);
      }
    }, [pageNumber, onDisplayZoomPercent, searchQuery, onSearchRectsChange]);

    useEffect(() => {
      void renderPage();
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
      const p = panningRef.current;
      if (!p || p.pointerId !== e.pointerId) return;
      const dx = e.clientX - p.lastX;
      const dy = e.clientY - p.lastY;
      p.lastX = e.clientX;
      p.lastY = e.clientY;
      setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
    };

    const onPointerUp = (e: React.PointerEvent) => {
      const p = panningRef.current;
      if (p && p.pointerId === e.pointerId) {
        panningRef.current = null;
      }
    };

    const vp = viewportRef.current;
    let scaleLine: { x1: number; y1: number; x2: number; y2: number } | null = null;
    if (scaleDraftPdf?.a && vp) {
      const v1 = vp.convertToViewportPoint(scaleDraftPdf.a.x, scaleDraftPdf.a.y);
      const b = scaleDraftPdf.b ?? scaleDraftPdf.a;
      const v2 = vp.convertToViewportPoint(b.x, b.y);
      scaleLine = { x1: v1[0], y1: v1[1], x2: v2[0], y2: v2[1] };
    }

    return (
      <div
        ref={containerRef}
        className={`relative min-h-[200px] flex-1 overflow-hidden bg-muted/20 ${
          calibrationMode ? "cursor-crosshair" : ""
        } ${className ?? ""}`}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
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
              className="pointer-events-none absolute left-0 top-0"
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
              />
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
        </div>
      </div>
    );
  }
);
