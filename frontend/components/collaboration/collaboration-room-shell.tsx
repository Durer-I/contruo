"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useUpdateMyPresence } from "@liveblocks/react";

import { collaborationColorForUserId } from "@/lib/collaboration-color";
import { SetCollaborationPdfCursorContext } from "@/providers/collaboration-cursor-context";
import type { SheetInfo } from "@/types/project";

import { CollaborationTopBarRegistrar } from "./collaboration-top-bar-registrar";

const CURSOR_THROTTLE_MS = 66;

export interface CollaborationRoomShellProps {
  sheets: SheetInfo[];
  activeSheetId: string | null;
  pageNumber: number;
  selectedIds: Set<string>;
  activeTool: string;
  canEditMeasurements: boolean;
  userId: string;
  userName: string;
  children: React.ReactNode;
}

export function CollaborationRoomShell({
  sheets,
  activeSheetId,
  pageNumber,
  selectedIds,
  activeTool,
  canEditMeasurements,
  userId,
  userName,
  children,
}: CollaborationRoomShellProps) {
  const updateMyPresence = useUpdateMyPresence();
  const lastCursorSend = useRef(0);

  const color = useMemo(() => collaborationColorForUserId(userId), [userId]);

  useEffect(() => {
    updateMyPresence({
      name: userName || "Member",
      color,
    });
  }, [userName, color, updateMyPresence]);

  useEffect(() => {
    updateMyPresence({
      sheetId: activeSheetId,
      pageNumber,
    });
  }, [activeSheetId, pageNumber, updateMyPresence]);

  useEffect(() => {
    const only =
      canEditMeasurements && activeTool === "select" && selectedIds.size === 1
        ? [...selectedIds][0]!
        : null;
    updateMyPresence({
      lockedMeasurementId: only,
      lockedAt: only ? Date.now() : null,
    });
  }, [selectedIds, activeTool, canEditMeasurements, updateMyPresence]);

  useEffect(() => {
    const only =
      canEditMeasurements && activeTool === "select" && selectedIds.size === 1
        ? [...selectedIds][0]!
        : null;
    if (!only) return;
    const t = window.setInterval(() => {
      updateMyPresence({ lockedAt: Date.now() });
    }, 25_000);
    return () => window.clearInterval(t);
  }, [selectedIds, activeTool, canEditMeasurements, updateMyPresence]);

  const setPdfCursor = useCallback(
    (pt: { x: number; y: number } | null) => {
      const now = Date.now();
      if (pt && now - lastCursorSend.current < CURSOR_THROTTLE_MS) return;
      lastCursorSend.current = now;
      updateMyPresence({
        cursor: pt,
        cursorAt: pt ? now : null,
      });
    },
    [updateMyPresence]
  );

  return (
    <SetCollaborationPdfCursorContext.Provider value={setPdfCursor}>
      <CollaborationTopBarRegistrar sheets={sheets} />
      {children}
    </SetCollaborationPdfCursorContext.Provider>
  );
}
