/** Liveblocks room id for a project (must match backend `parse_collaboration_room`). */
export function collaborationRoomId(orgId: string, projectId: string): string {
  return `contruo:${orgId}:${projectId}`;
}
