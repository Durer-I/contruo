import { createClient } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Liveblocks `authEndpoint` callback: POST token with Supabase JWT. */
export function createLiveblocksAuthEndpoint(): (
  room?: string
) => Promise<{ token: string }> {
  return async (room?: string) => {
    if (!room) {
      throw new Error("Missing collaboration room");
    }
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (!token) {
      throw new Error("Not signed in");
    }
    const res = await fetch(`${API_URL}/api/v1/liveblocks/auth`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ room }),
    });
    const body = (await res.json().catch(() => ({}))) as {
      token?: string;
      error?: { message?: string };
    };
    if (!res.ok) {
      throw new Error(body?.error?.message ?? res.statusText);
    }
    if (!body.token) {
      throw new Error("Liveblocks auth response missing token");
    }
    return { token: body.token };
  };
}
