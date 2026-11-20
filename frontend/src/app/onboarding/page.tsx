"use client";

import { Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { DARK_INPUT, RolePicker } from "@/components/auth/role-picker";
import { BrandMark } from "@/components/shell/brand-mark";
import { api, ApiError } from "@/lib/api";
import { homeFor } from "@/lib/roles";
import type { Role } from "@/types/api";

/** First sign-in with Google: pick a role (an admin also names their brand). */
export default function OnboardingPage() {
  const { session, me, loading, refresh, signOut } = useAuth();
  const router = useRouter();
  const [role, setRole] = useState<Role | null>(null);
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!session) router.replace("/login");
    else if (me && !me.needs_onboarding) router.replace(homeFor(me));
  }, [loading, session, me, router]);

  useEffect(() => {
    const meta = session?.user.user_metadata as
      { full_name?: string; name?: string } | undefined;
    const suggested = meta?.full_name ?? meta?.name;
    if (suggested) setName((n) => n || suggested);
  }, [session]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!role) {
      setError("Pick a role: admin, manager or creator.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api("/me/onboard", {
        json: {
          display_name: name.trim(),
          role,
          brand_name: role === "admin" ? brand.trim() : null,
        },
      });
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That did not work");
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-black px-4 py-12 text-white">
      <div className="hd-grid-bg absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" />
      <motion.form
        onSubmit={onSubmit}
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: [0.2, 0.7, 0.2, 1] }}
        className="relative w-full max-w-xl space-y-5 rounded-3xl border border-white/15 bg-white/[0.06] p-6 backdrop-blur-xl sm:p-8"
      >
        <BrandMark tone="light" size={36} />
        <div>
          <h1 className="text-3xl font-bold tracking-tight">One last step</h1>
          <p className="mt-2 text-white/65">
            Signed in as {session?.user.email}. Choose how you will use
            Heimdall.
          </p>
        </div>
        <RolePicker value={role} onChange={setRole} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="name" className="text-sm font-medium">
              Your name
            </label>
            <input
              id="name"
              required
              maxLength={80}
              className={DARK_INPUT}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          {role === "admin" && (
            <div className="space-y-1.5">
              <label htmlFor="brand" className="text-sm font-medium">
                Brand name
              </label>
              <input
                id="brand"
                required
                maxLength={80}
                className={DARK_INPUT}
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
              />
            </div>
          )}
        </div>
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-red-400/40 bg-red-500/15 px-3 py-2 text-sm text-red-100"
          >
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={busy}
            className="flex h-11 flex-1 items-center justify-center gap-2 rounded-full bg-white px-6 text-sm font-semibold text-black focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black focus-visible:outline-none disabled:opacity-60"
          >
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
            Continue
          </button>
          <button
            type="button"
            onClick={() => void signOut()}
            className="h-11 rounded-full border border-white/25 px-5 text-sm font-semibold hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
          >
            Use another account
          </button>
        </div>
      </motion.form>
    </div>
  );
}
