"use client";

import { useMemo } from "react";
import { LiveblocksProvider, RoomProvider } from "@liveblocks/react";

import { createLiveblocksAuthEndpoint } from "@/lib/liveblocks-auth";
import { collaborationRoomId } from "@/lib/collaboration-room";

const initialPresence = () => ({
  name: "",
  color: "#64748b",
  sheetId: null as string | null,
  pageNumber: null as number | null,
  cursor: null as { x: number; y: number } | null,
  cursorAt: null as number | null,
  lockedMeasurementId: null as string | null,
  lockedAt: null as number | null,
});

export function ProjectCollaborationRoom({
  orgId,
  projectId,
  children,
}: {
  orgId: string;
  projectId: string;
  children: React.ReactNode;
}) {
  const roomId = useMemo(() => collaborationRoomId(orgId, projectId), [orgId, projectId]);
  const authEndpoint = useMemo(() => createLiveblocksAuthEndpoint(), []);

  return (
    <LiveblocksProvider authEndpoint={authEndpoint}>
      <RoomProvider id={roomId} initialPresence={initialPresence}>
        {children}
      </RoomProvider>
    </LiveblocksProvider>
  );
}
