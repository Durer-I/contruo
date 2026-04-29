"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import { useRouter } from "next/navigation";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase";
import { api } from "@/lib/api";
import { syncSupabaseSessionCookies } from "@/lib/sync-supabase-session";
import type { UserInfo, AuthResponse } from "@/types/user";

interface AuthState {
  session: Session | null;
  user: UserInfo | null;
  loading: boolean;
  signUp: (
    fullName: string,
    email: string,
    password: string,
    orgName: string
  ) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  /** Re-fetch `/auth/me` into context (e.g. after profile PATCH). */
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const supabaseRef = useRef<SupabaseClient | null>(null);

  // Lazily create Supabase client (only on client side where env vars exist)
  function getSupabase(): SupabaseClient {
    if (!supabaseRef.current) {
      supabaseRef.current = createClient();
    }
    return supabaseRef.current;
  }

  const fetchUser = useCallback(async (accessToken: string) => {
    try {
      const data = await api.get<{ user: UserInfo }>("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      setUser(data.user);
    } catch (e) {
      // Don't clear the existing user — a transient /me failure shouldn't kick the
      // user back to a viewer-shaped UI — but log so engineers can see flakiness.
      if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.warn("[auth] /auth/me failed (kept previous user):", e);
      }
    }
  }, []);

  const refreshMe = useCallback(async () => {
    const supabase = getSupabase();
    const {
      data: { session: s },
    } = await supabase.auth.getSession();
    if (s?.access_token) {
      await fetchUser(s.access_token);
    }
  }, [fetchUser]);

  useEffect(() => {
    let supabase: SupabaseClient;
    try {
      supabase = getSupabase();
    } catch {
      setLoading(false);
      return;
    }

    const initSession = async () => {
      try {
        const {
          data: { session: currentSession },
        } = await supabase.auth.getSession();
        setSession(currentSession);
        if (currentSession?.access_token) {
          await fetchUser(currentSession.access_token);
        }
      } catch {
        // No session
      } finally {
        setLoading(false);
      }
    };

    initSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, newSession) => {
      setSession(newSession);
      if (newSession?.access_token) {
        await fetchUser(newSession.access_token);
      } else {
        setUser(null);
      }
    });

    return () => subscription.unsubscribe();
  }, [fetchUser]);

  const signUp = useCallback(
    async (
      fullName: string,
      email: string,
      password: string,
      orgName: string
    ) => {
      const data = await api.post<AuthResponse>("/api/v1/auth/register", {
        full_name: fullName,
        email,
        password,
        org_name: orgName,
      });

      await syncSupabaseSessionCookies(data.access_token, data.refresh_token);
      const supabase = getSupabase();
      await supabase.auth.setSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      });

      setUser(data.user);
      if (data.user.needs_subscription) {
        router.push("/settings/billing?checkout=1");
      } else if (data.user.reactivation_required) {
        router.push("/settings/billing");
      } else {
        router.push("/dashboard");
      }
    },
    [router]
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      const supabase = getSupabase();
      const { error: priorSessionErr } = await supabase.auth.signOut({
        scope: "local",
      });
      if (priorSessionErr) {
        // Stale or missing session; continue with fresh login
      }
      const data = await api.post<AuthResponse>("/api/v1/auth/login", {
        email,
        password,
      });
      await syncSupabaseSessionCookies(data.access_token, data.refresh_token);
      await supabase.auth.setSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      });
      setUser(data.user);
      if (data.user.needs_subscription) {
        router.push("/settings/billing?checkout=1");
      } else if (data.user.reactivation_required) {
        router.push("/settings/billing");
      } else {
        router.push("/dashboard");
      }
    },
    [router]
  );

  const signOut = useCallback(async () => {
    try {
      const supabase = getSupabase();
      // Single GoTrue logout (revokes refresh + clears storage). Do not also call our API:
      // backend admin.sign_out would revoke first and the second logout returns session_not_found.
      await supabase.auth.signOut();
    } catch {
      // Non-fatal (e.g. session already revoked server-side)
    }
    setSession(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  const resetPassword = useCallback(async (email: string) => {
    await api.post("/api/v1/auth/reset-password", { email });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        session,
        user,
        loading,
        signUp,
        signIn,
        signOut,
        resetPassword,
        refreshMe,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
