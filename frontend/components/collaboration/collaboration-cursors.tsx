"use client";

import { useMemo, useRef } from "react";
import { useOthers } from "@liveblocks/react";
import type { PageViewport } from "pdfjs-dist";

const IDLE_MS = 5000;
const LERP = 0.42;

/**
 * Other users' cursors in PDF viewport space (same transform as measurement overlays).
 */
export function CollaborationCursorsLayer({
  vp,
  cssW,
  cssH,
  sheetId,
  pageNumber,
}: {
  vp: PageViewport;
  cssW: number;
  cssH: number;
  sheetId: string | null;
  pageNumber: number;
}) {
  const others = useOthers();
  const smoothedRef = useRef<Record<number, { x: number; y: number }>>({});

  const items = useMemo(() => {
    if (!sheetId || cssW <= 0 || cssH <= 0) return null;
    const out: React.ReactNode[] = [];
    const now = Date.now();

    for (const u of others) {
      if (u.presence.sheetId !== sheetId) continue;
      if (u.presence.pageNumber !== pageNumber) continue;
      const raw = u.presence.cursor;
      const cur =
        raw &&
        typeof raw === "object" &&
        !Array.isArray(raw) &&
        typeof (raw as { x?: unknown }).x === "number" &&
        typeof (raw as { y?: unknown }).y === "number"
          ? { x: (raw as { x: number }).x, y: (raw as { y: number }).y }
          : null;
      if (!cur) continue;
      const at = typeof u.presence.cursorAt === "number" ? u.presence.cursorAt : 0;
      if (now - at > IDLE_MS) continue;
      const cid = u.connectionId;
      const prev = smoothedRef.current[cid] ?? cur;
      const nx = prev.x + (cur.x - prev.x) * LERP;
      const ny = prev.y + (cur.y - prev.y) * LERP;
      smoothedRef.current[cid] = { x: nx, y: ny };
      const [vx, vy] = vp.convertToViewportPoint(nx, ny);
      const name = String((u.info as { name?: string } | undefined)?.name ?? "Guest");
      const color = typeof u.presence.color === "string" ? u.presence.color : "#64748b";
      out.push(
        <g key={cid} style={{ pointerEvents: "none" }}>
          <polygon
            points="0,0 -10,-4 -6,-14 -3,-4"
            transform={`translate(${vx},${vy}) rotate(-28)`}
            fill={color}
            stroke="hsl(var(--background))"
            strokeWidth={1.5}
          />
          <text
            x={vx + 12}
            y={vy + 4}
            fontSize={11}
            fontWeight={600}
            fill="hsl(var(--foreground))"
            stroke="hsl(var(--background))"
            strokeWidth={3}
            paintOrder="stroke"
          >
            {name}
          </text>
        </g>
      );
    }

    return out.length ? out : null;
  }, [others, vp, cssW, cssH, sheetId, pageNumber]);

  if (!items) return null;

  return (
    <svg className="absolute left-0 top-0 z-[6]" width={cssW} height={cssH} aria-hidden>
      {items}
    </svg>
  );
}
