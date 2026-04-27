"use client";

import { useLayoutEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useIsInsideRoom, useOthers, useStatus } from "@liveblocks/react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { SheetInfo } from "@/types/project";
import { cn } from "@/lib/utils";

/** Must match the mount point in `components/layout/top-bar.tsx`. */
export const COLLAB_TOPBAR_MOUNT_ID = "contruo-collab-topbar-mount";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";
}

function CollaborationTopBarInner({ sheets }: { sheets: SheetInfo[] }) {
  const status = useStatus();
  const others = useOthers();

  const statusLabel = useMemo(() => {
    if (status === "connected") return "Live";
    if (status === "reconnecting" || status === "connecting") return "Reconnecting…";
    if (status === "disconnected") return "Offline";
    return String(status);
  }, [status]);

  const statusClass =
    status === "connected"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
      : status === "disconnected"
        ? "border-destructive/40 bg-destructive/10 text-destructive"
        : "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200";

  return (
    <div className="flex max-w-[min(40vw,14rem)] items-center gap-1.5">
      <span
        className={cn(
          "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium",
          statusClass
        )}
        title="Collaboration connection"
      >
        {statusLabel}
      </span>
      <div className="flex -space-x-1.5">
        {others.map((u) => {
          const name = String((u.info as { name?: string } | undefined)?.name ?? "Guest");
          const color = typeof u.presence.color === "string" ? u.presence.color : "#64748b";
          const sheetId = typeof u.presence.sheetId === "string" ? u.presence.sheetId : null;
          const sheet = sheetId ? sheets.find((s) => s.id === sheetId) : null;
          const tip = sheet
            ? `${name} · ${sheet.sheet_name ?? `Page ${sheet.page_number}`}`
            : name;
          return (
            <Avatar
              key={u.connectionId}
              className="h-7 w-7 border-2 border-background text-[10px] shadow-sm"
              style={{ borderColor: color }}
              title={tip}
            >
              <AvatarFallback
                className="text-[10px] font-semibold text-white"
                style={{ backgroundColor: color }}
              >
                {initials(name)}
              </AvatarFallback>
            </Avatar>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Renders collaboration avatars + connection pill into the app header via portal.
 * Must stay under Liveblocks `RoomProvider` in the React tree (DOM can be in TopBar).
 */
export function CollaborationTopBarRegistrar({ sheets }: { sheets: SheetInfo[] }) {
  const insideRoom = useIsInsideRoom();
  const [mountEl, setMountEl] = useState<HTMLElement | null>(null);

  useLayoutEffect(() => {
    const el =
      typeof document !== "undefined"
        ? document.getElementById(COLLAB_TOPBAR_MOUNT_ID)
        : null;
    setMountEl(el);
  }, [insideRoom]);

  if (!mountEl) return null;

  return createPortal(<CollaborationTopBarInner sheets={sheets} />, mountEl);
}
