"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { homeFor } from "@/lib/roles";

/** Where Google sends people back. The Supabase client reads the session from the URL;
 * first-time Google users pick a role on /onboarding, everyone else goes to their portal. */
export default function AuthCallbackPage() {
  const { me, session, loading, error } = useAuth();
  const router = useRouter();
  const [urlError, setUrlError] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(
      window.location.search || window.location.hash.slice(1),
    );
    const message = params.get("error_description") ?? params.get("error");
    if (message) setUrlError(message);
    const t = window.setTimeout(() => setSlow(true), 8000);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!loading && session && me) router.replace(homeFor(me));
  }, [loading, session, me, router]);

  const problem =
    urlError ??
    error ??
    (slow && !session ? "No session came back from Google." : null);

  return (
    <div className="flex min-h-[100svh] items-center justify-center bg-black px-4 text-white">
      {problem ? (
        <div role="alert" className="max-w-sm space-y-4 text-center">
          <h1 className="text-2xl font-bold">Google sign-in did not finish</h1>
          <p className="text-white/70">{problem}</p>
          <Link
            href="/login"
            className="inline-flex rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-black"
          >
            Back to sign in
          </Link>
        </div>
      ) : (
        <p role="status" className="flex items-center gap-2 text-white/80">
          <Loader2 className="size-5 animate-spin" aria-hidden /> Signing you
          in…
        </p>
      )}
    </div>
  );
}
