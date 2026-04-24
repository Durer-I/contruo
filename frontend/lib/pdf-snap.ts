export type SnapPdfPoint = { x: number; y: number };

export type SnapSegment = { x1: number; y1: number; x2: number; y2: number };

function closestOnSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number
): { x: number; y: number; dist: number } {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  if (len2 < 1e-18) {
    const dist = Math.hypot(px - x1, py - y1);
    return { x: x1, y: y1, dist };
  }
  let t = ((px - x1) * dx + (py - y1) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const x = x1 + t * dx;
  const y = y1 + t * dy;
  return { x, y, dist: Math.hypot(px - x, py - y) };
}

/** Snap a PDF point to the nearest vector segment if within tolerance (PDF points). */
export function snapPdfPointToSegments(
  p: SnapPdfPoint,
  segments: SnapSegment[],
  tolerancePdf: number
): SnapPdfPoint {
  if (!segments.length || tolerancePdf <= 0) return p;
  let best: { x: number; y: number; dist: number } | null = null;
  for (const s of segments) {
    const c = closestOnSegment(p.x, p.y, s.x1, s.y1, s.x2, s.y2);
    if (!best || c.dist < best.dist) best = c;
  }
  if (best && best.dist <= tolerancePdf) {
    return { x: best.x, y: best.y };
  }
  return p;
}
