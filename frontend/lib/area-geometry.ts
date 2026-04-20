/** PDF-space polygon area (shoelace), hit-testing, formatting. */

import type { PdfPoint } from "@/components/plan-viewer/plan-pdf-canvas";

export function polygonAreaAbs(vertices: PdfPoint[]): number {
  const n = vertices.length;
  if (n < 3) return 0;
  let s = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    s += vertices[i]!.x * vertices[j]!.y - vertices[j]!.x * vertices[i]!.y;
  }
  return Math.abs(s) / 2;
}

export function pointInPolygon(x: number, y: number, vertices: PdfPoint[]): boolean {
  const n = vertices.length;
  if (n < 3) return false;
  let inside = false;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = vertices[i]!.x;
    const yi = vertices[i]!.y;
    const xj = vertices[j]!.x;
    const yj = vertices[j]!.y;
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function distancePointToPolygonEdge(
  x: number,
  y: number,
  vertices: PdfPoint[],
  closed: boolean
): number {
  const n = vertices.length;
  if (n < 2) return Infinity;
  let best = Infinity;
  const segCount = closed ? n : n - 1;
  for (let i = 0; i < segCount; i++) {
    const j = closed ? (i + 1) % n : i + 1;
    const ax = vertices[i]!.x;
    const ay = vertices[i]!.y;
    const bx = vertices[j]!.x;
    const by = vertices[j]!.y;
    const dx = bx - ax;
    const dy = by - ay;
    const len2 = dx * dx + dy * dy;
    if (len2 < 1e-12) continue;
    let t = ((x - ax) * dx + (y - ay) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const px = ax + t * dx;
    const py = ay + t * dy;
    const d = Math.hypot(x - px, y - py);
    if (d < best) best = d;
  }
  return best;
}

export function realAreaFromPdfSq(pdfSq: number, scaleValue: number): number | null {
  if (!Number.isFinite(scaleValue) || scaleValue <= 0 || !Number.isFinite(pdfSq)) return null;
  return pdfSq * scaleValue * scaleValue;
}

export function formatAreaQuantity(value: number, unit: string): string {
  const u = unit.trim().toUpperCase();
  const decimals = u.includes("M2") || u === "SQM" ? 2 : 0;
  return `${value.toLocaleString(undefined, {
    maximumFractionDigits: decimals,
    minimumFractionDigits: 0,
  })} ${unit}`;
}
