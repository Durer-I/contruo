import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

/**
 * Persists Supabase session cookies from the Next server so `proxy.ts` /
 * `getUser()` see the same session as the browser after custom login
 * (backend `sign_in_with_password` + tokens returned to the client).
 *
 * Client-only `createBrowserClient().auth.setSession()` does not always
 * propagate cookies in time for the next RSC/proxy request.
 */
export async function POST(request: Request) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    return NextResponse.json({ error: "Supabase is not configured" }, { status: 503 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (
    !body ||
    typeof body !== "object" ||
    typeof (body as { access_token?: unknown }).access_token !== "string" ||
    typeof (body as { refresh_token?: unknown }).refresh_token !== "string"
  ) {
    return NextResponse.json(
      { error: "Expected { access_token, refresh_token }" },
      { status: 400 }
    );
  }

  const { access_token, refresh_token } = body as {
    access_token: string;
    refresh_token: string;
  };

  const cookieStore = await cookies();

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // ignore — can occur if called outside a mutable cookie context
        }
      },
    },
  });

  const { error } = await supabase.auth.setSession({
    access_token,
    refresh_token,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 401 });
  }

  return NextResponse.json({ ok: true });
}
