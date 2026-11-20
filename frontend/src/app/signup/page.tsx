"use client";

import { ArrowLeft, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { GoogleButton, OrDivider } from "@/components/auth/google-button";
import { DARK_INPUT, RolePicker } from "@/components/auth/role-picker";
import { BrandMark } from "@/components/shell/brand-mark";
import { api, ApiError } from "@/lib/api";
import { homeFor } from "@/lib/roles";
import type { Role } from "@/types/api";

/** Create an account: pick a role (an admin also names their brand), then land in that portal. */
export default function SignupPage() {
  const { me, signIn } = useAuth();
  const router = useRouter();
  const [role, setRole] = useState<Role | null>(null);
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (me) router.replace(homeFor(me));
  }, [me, router]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!role) {
      setError("Pick a role: admin, manager or creator.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await api("/auth/signup", {
        json: {
          email: email.trim(),
          password,
          display_name: name.trim(),
          role,
          brand_name: role === "admin" ? brand.trim() : null,
        },
      });
      await signIn(email.trim(), password);
    } catch (e) {
      setError(
        e instanceof ApiError || e instanceof Error
          ? e.message
          : "Sign-up failed",
      );
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-black px-4 py-12 text-white">
      <div className="hd-grid-bg absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" />
      <div
        aria-hidden
        className="absolute -top-40 left-1/2 size-[36rem] -translate-x-1/2 rounded-full bg-indigo-500/20 blur-3xl"
      />
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.2, 0.7, 0.2, 1] }}
        className="relative w-full max-w-xl rounded-3xl border border-white/15 bg-white/[0.06] p-6 backdrop-blur-xl sm:p-8"
      >
        <div className="flex items-center justify-between">
          <BrandMark tone="light" size={36} />
          <Link
            href="/"
            className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 hover:text-white"
          >
            <ArrowLeft className="size-4" aria-hidden /> Home
          </Link>
        </div>
        <h1 className="mt-5 text-3xl font-bold tracking-tight">
          Create your Heimdall account
        </h1>
        <p className="mt-2 text-white/65">
          Pick your role. You land in your own portal every time you sign in.
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-5">
          <RolePicker value={role} onChange={setRole} />

          <GoogleButton
            onError={setError}
            className="border-white/20 bg-white"
          />
          <p className="-mt-3 text-center text-xs text-white/50">
            With Google you pick your role on the next screen.
          </p>
          <OrDivider tone="light" />

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="name" className="text-sm font-medium">
                Your name
              </label>
              <input
                id="name"
                required
                maxLength={80}
                autoComplete="name"
                className={DARK_INPUT}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            {role === "admin" && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-1.5"
              >
                <label htmlFor="brand" className="text-sm font-medium">
                  Brand name
                </label>
                <input
                  id="brand"
                  required
                  maxLength={80}
                  placeholder="e.g. Lumen Coffee"
                  className={DARK_INPUT}
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                />
              </motion.div>
            )}
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                className={DARK_INPUT}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="password" className="text-sm font-medium">
                Password{" "}
                <span className="font-normal text-white/50">
                  (6+ characters)
                </span>
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={6}
                maxLength={72}
                autoComplete="new-password"
                className={DARK_INPUT}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-lg border border-red-400/40 bg-red-500/15 px-3 py-2 text-sm text-red-100"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-full bg-white text-sm font-semibold text-black transition-transform hover:scale-[1.01] focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black focus-visible:outline-none active:scale-[0.99] disabled:opacity-60"
          >
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
            Create account
          </button>
          <p className="text-center text-sm text-white/60">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-semibold text-white underline underline-offset-2"
            >
              Sign in
            </Link>
          </p>
        </form>
      </motion.div>
    </div>
  );
}
