import type { PDFPageProxy } from "pdfjs-dist";
import type { PageViewport } from "pdfjs-dist";

/** Bounding boxes in **viewport / canvas CSS pixel** space (same origin as pdf.js canvas). */
export interface ViewportRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Find text items whose string contains ``query`` and return rough highlight rectangles. */
export async function findTextMatchRects(
  page: PDFPageProxy,
  viewport: PageViewport,
  query: string
): Promise<ViewportRect[]> {
  const q = query.trim().toLowerCase();
  if (q.length < 1) return [];

  const content = await page.getTextContent();
  const out: ViewportRect[] = [];

  for (const item of content.items) {
    if (!("str" in item) || typeof item.str !== "string" || !item.str.trim()) {
      continue;
    }
    if (!item.str.toLowerCase().includes(q)) continue;

    const m = item.transform;
    const w = item.width;
    const h = item.height || Math.abs(m[3]) || Math.abs(m[2]) || 12;
    const x = m[4];
    const y = m[5];

    const p1 = viewport.convertToViewportPoint(x, y);
    const p2 = viewport.convertToViewportPoint(x + w, y - h);
    const left = Math.min(p1[0], p2[0]);
    const top = Math.min(p1[1], p2[1]);
    const width = Math.abs(p2[0] - p1[0]) || 4;
    const height = Math.abs(p2[1] - p1[1]) || 4;
    out.push({ left, top, width, height });
  }

  return out;
}
