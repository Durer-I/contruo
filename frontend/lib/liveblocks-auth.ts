import { api } from "@/lib/api";

/**
 * Liveblocks `authEndpoint` callback: POST the room name to our backend, which
 * verifies project membership and returns a Liveblocks token.
 *
 * Routed through the shared ``api`` client so we get JWT attachment, ApiError
 * handling, and request-id propagation for free.
 */
export function createLiveblocksAuthEndpoint(): (
  room?: string
) => Promise<{ token: string }> {
  return async (room?: string) => {
    if (!room) {
      throw new Error("Missing collaboration room");
    }
    const body = await api.post<{ token?: string }>("/api/v1/liveblocks/auth", {
      room,
    });
    if (!body?.token) {
      throw new Error("Liveblocks auth response missing token");
    }
    return { token: body.token };
  };
}
