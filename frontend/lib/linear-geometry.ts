type Pt = { x: number; y: number };

/** Total PDF-space length (same units as pdf.js user space). */
export function polylineLengthPdf(vertices: Pt[]): number {
  if (vertices.length < 2) return 0;
  let t = 0;
  for (let i = 1; i < vertices.length; i++) {
    const dx = vertices[i]!.x - vertices[i - 1]!.x;
    const dy = vertices[i]!.y - vertices[i - 1]!.y;
    t += Math.hypot(dx, dy);
  }
  return t;
}

/** Real-world length using sheet scale (ft or m per PDF point). */
export function realLengthFromPdf(
  pdfLengthPts: number,
  scaleValue: number | null | undefined,
  scaleUnit: string | null | undefined
): number | null {
  if (scaleValue == null) return null;
  return pdfLengthPts * scaleValue;
}

/** Format length for display (sheet is ft or m). */
function distPointToSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  if (len2 < 1e-12) return Math.hypot(px - x1, py - y1);
  let t = ((px - x1) * dx + (py - y1) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const qx = x1 + t * dx;
  const qy = y1 + t * dy;
  return Math.hypot(px - qx, py - qy);
}

/** Minimum distance from point to polyline (PDF space). */
export function distancePointToPolyline(
  px: number,
  py: number,
  vertices: Array<{ x: number; y: number }>
): number {
  if (vertices.length < 2) return Infinity;
  let min = Infinity;
  for (let i = 0; i < vertices.length - 1; i++) {
    const a = vertices[i]!;
    const b = vertices[i + 1]!;
    min = Math.min(min, distPointToSegment(px, py, a.x, a.y, b.x, b.y));
  }
  return min;
}

export function formatLength(
  value: number | null,
  scaleUnit: string | null | undefined,
  displayUnit: string
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const u = (scaleUnit ?? "ft").toLowerCase();
  const d = displayUnit.toUpperCase();
  if (d === "LF" || d === "FT" || d === "'") {
    const ft = u === "ft" ? value : value * 3.280839895;
    return `${ft.toFixed(2)} LF`;
  }
  if (d === "M") {
    const m = u === "m" ? value : value * 0.3048;
    return `${m.toFixed(3)} m`;
  }
  return `${value.toFixed(2)} ${displayUnit}`;
}
