import type { MeasurementInfo } from "@/types/measurement";
import type { PdfFocusBounds } from "@/components/plan-viewer/plan-pdf-canvas";

/** Compute PDF-space bounds for pan/zoom-to-measurement. */
export function getMeasurementPdfBounds(m: MeasurementInfo): PdfFocusBounds | null {
  if (m.measurement_type === "linear" && m.geometry.type === "linear") {
    const v = m.geometry.vertices;
    if (v.length < 2) return null;
    let minX = v[0]!.x;
    let maxX = v[0]!.x;
    let minY = v[0]!.y;
    let maxY = v[0]!.y;
    for (const p of v) {
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y);
      maxY = Math.max(maxY, p.y);
    }
    const pad = 12;
    return { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad };
  }
  if (m.measurement_type === "area" && m.geometry.type === "area") {
    const outer = m.geometry.outer;
    if (outer.length < 3) return null;
    let minX = outer[0]!.x;
    let maxX = outer[0]!.x;
    let minY = outer[0]!.y;
    let maxY = outer[0]!.y;
    for (const p of outer) {
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y);
      maxY = Math.max(maxY, p.y);
    }
    const pad = 8;
    return { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad };
  }
  if (m.measurement_type === "count" && m.geometry.type === "count") {
    const { x, y } = m.geometry.position;
    const pad = 28;
    return { minX: x - pad, minY: y - pad, maxX: x + pad, maxY: y + pad };
  }
  return null;
}
