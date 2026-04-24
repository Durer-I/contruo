/**
 * Writes Supabase auth cookies via a Route Handler so Next `proxy.ts` sees
 * the session on the following navigation (see `app/api/auth/sync-session`).
 */
export async function syncSupabaseSessionCookies(
  access_token: string,
  refresh_token: string
): Promise<void> {
  const res = await fetch("/api/auth/sync-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token, refresh_token }),
    credentials: "same-origin",
  });
  if (!res.ok) {
    let message = "Failed to sync session";
    try {
      const data = (await res.json()) as { error?: string };
      if (data.error) message = data.error;
    } catch {
      //
    }
    throw new Error(message);
  }
}
