import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !key) {
    return supabaseResponse;
  }

  const supabase = createServerClient(
    url,
    key,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;

  // Public routes that don't require auth
  const isAuthRoute =
    pathname.startsWith("/login") ||
    pathname.startsWith("/signup") ||
    pathname.startsWith("/reset-password") ||
    pathname.startsWith("/accept-invite");

  /** Lets unauthenticated clients persist Supabase cookies after API login. */
  const isSyncSessionApi = pathname === "/api/auth/sync-session";

  const allowWithoutSession = isAuthRoute || isSyncSessionApi;

  // If on a protected route without a session, redirect to login
  if (!user && !allowWithoutSession) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    const destination = `${pathname}${request.nextUrl.search || ""}`;
    loginUrl.search = "";
    loginUrl.searchParams.set("redirect", destination);
    return NextResponse.redirect(loginUrl);
  }

  // If authenticated and on an auth page, redirect to dashboard
  if (user && isAuthRoute) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
