import type { MeasurementGeometry } from "@/types/measurement";

/** True when keyboard shortcuts should not run (typing in a field). */
export function isEditableTarget(el: EventTarget | null): boolean {
  if (!el || !(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  return false;
}

export function isInsideDialogContent(el: EventTarget | null): boolean {
  if (!el || !(el instanceof HTMLElement)) return false;
  return Boolean(el.closest('[data-slot="dialog-content"]'));
}

/** Clone geometry for POST; drop server-computed fields the API may ignore or reject. */
export function geometryForRecreate(geometry: MeasurementGeometry): MeasurementGeometry {
  const g = structuredClone(geometry) as MeasurementGeometry & { metrics?: unknown };
  if (g.type === "area" && "metrics" in g) {
    delete g.metrics;
  }
  return g as MeasurementGeometry;
}

export interface MeasurementRedoSnapshot {
  sheet_id: string;
  condition_id: string;
  measurement_type: "linear" | "area" | "count";
  geometry: MeasurementGeometry;
}
