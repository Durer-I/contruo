"use client";

import { useMemo } from "react";
import { useOthers } from "@liveblocks/react";

const STALE_MS = 120_000;

/** Remote users' lock targets (stale locks ignored). */
export function useRemoteMeasurementLockMap(): ReadonlyMap<
  string,
  { name: string; color: string }
> {
  const others = useOthers();
  return useMemo(() => {
    const m = new Map<string, { name: string; color: string }>();
    const now = Date.now();
    for (const u of others) {
      const id = u.presence.lockedMeasurementId;
      const at = u.presence.lockedAt;
      if (typeof id !== "string" || !id) continue;
      if (typeof at === "number" && now - at > STALE_MS) continue;
      const name = String((u.info as { name?: string } | undefined)?.name ?? "Someone");
      const color = typeof u.presence.color === "string" ? u.presence.color : "#666";
      if (!m.has(id)) m.set(id, { name, color });
    }
    return m;
  }, [others]);
}
