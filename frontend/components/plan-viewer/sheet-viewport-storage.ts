/** Persist zoom / pan per sheet in localStorage (Sprint 05). */

export type FitMode = "width" | "page";

export interface SheetViewportState {
  fitMode: FitMode;
  /** Extra zoom on top of fit scale (1 = none). */
  zoomMultiplier: number;
  panX: number;
  panY: number;
}

const KEY_PREFIX = "contruo:sheetViewport:v1:";

export function viewportStorageKey(projectId: string, sheetId: string): string {
  return `${KEY_PREFIX}${projectId}:${sheetId}`;
}

export function loadViewport(key: string): SheetViewportState | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const v = JSON.parse(raw) as Partial<SheetViewportState>;
    if (v.fitMode !== "width" && v.fitMode !== "page") return null;
    if (typeof v.zoomMultiplier !== "number" || typeof v.panX !== "number" || typeof v.panY !== "number") {
      return null;
    }
    return {
      fitMode: v.fitMode,
      zoomMultiplier: Math.min(8, Math.max(0.15, v.zoomMultiplier)),
      panX: v.panX,
      panY: v.panY,
    };
  } catch {
    return null;
  }
}

export function saveViewport(key: string, state: SheetViewportState): void {
  try {
    localStorage.setItem(key, JSON.stringify(state));
  } catch {
    /* quota or private mode */
  }
}
