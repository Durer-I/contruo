/** Douglas–Peucker polyline simplification in PDF user space. */

export interface SimplifyPoint {
  x: number;
  y: number;
}

function perpDist(p: SimplifyPoint, a: SimplifyPoint, b: SimplifyPoint): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  if (dx === 0 && dy === 0) return Math.hypot(p.x - a.x, p.y - a.y);
  const t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy);
  const t2 = Math.max(0, Math.min(1, t));
  const nx = a.x + t2 * dx;
  const ny = a.y + t2 * dy;
  return Math.hypot(p.x - nx, p.y - ny);
}

function simplifyRing(points: SimplifyPoint[], epsilon: number): SimplifyPoint[] {
  if (points.length < 3) return points;
  let maxD = 0;
  let idx = 0;
  for (let i = 1; i < points.length - 1; i++) {
    const d = perpDist(points[i]!, points[0]!, points[points.length - 1]!);
    if (d > maxD) {
      maxD = d;
      idx = i;
    }
  }
  if (maxD <= epsilon) {
    return [points[0]!, points[points.length - 1]!];
  }
  const left = simplifyRing(points.slice(0, idx + 1), epsilon);
  const right = simplifyRing(points.slice(idx), epsilon);
  return [...left.slice(0, -1), ...right];
}

/** Simplify an open polyline; keeps endpoints. */
export function simplifyPolylinePdf(points: SimplifyPoint[], epsilon: number): SimplifyPoint[] {
  if (points.length < 3) return points;
  return simplifyRing(points, epsilon);
}
