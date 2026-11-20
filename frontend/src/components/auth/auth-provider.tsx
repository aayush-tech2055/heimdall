"use client";

import type { Session } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, ApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { MeRaw } from "@/types/api";

type AuthState = {
  session: Session | null;
  me: MeRaw | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  /** Sign in or sign up with Google; Supabase returns to /auth/callback. */
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  /** Reload `/me` (after onboarding or a team change). */
  refresh: () => Promise<void>;
  /** Switch the brand whose guidelines you work under. */
  switchBrand: (brandId: string) => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<MeRaw | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMe = useCallback(async (s: Session | null) => {
    setSession(s);
    if (!s) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api<MeRaw>("/me"));
      setError(null);
    } catch (e) {
      setMe(null);
      setError(
        e instanceof ApiError ? e.message : "Could not load your profile",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const client = supabase();
    client.auth.getSession().then(({ data }) => loadMe(data.session));
    const { data } = client.auth.onAuthStateChange((event, s) => {
      if (event === "SIGNED_IN" || event === "SIGNED_OUT") void loadMe(s);
      else setSession(s);
    });
    return () => data.subscription.unsubscribe();
  }, [loadMe]);

  const value = useMemo<AuthState>(
    () => ({
      session,
      me,
      loading,
      error,
      signIn: async (email, password) => {
        setLoading(true);
        const { error: signInError } = await supabase().auth.signInWithPassword(
          { email, password },
        );
        if (signInError) {
          setLoading(false);
          throw new Error(signInError.message);
        }
      },
      signInWithGoogle: async () => {
        const { error: oauthError } = await supabase().auth.signInWithOAuth({
          provider: "google",
          options: { redirectTo: `${window.location.origin}/auth/callback` },
        });
        if (oauthError) throw new Error(oauthError.message);
      },
      signOut: async () => {
        await supabase().auth.signOut();
      },
      refresh: async () => {
        setMe(await api<MeRaw>("/me"));
      },
      switchBrand: async (brandId) => {
        setMe(
          await api<MeRaw>("/me/active-brand", { json: { brand_id: brandId } }),
        );
      },
    }),
    [session, me, loading, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
