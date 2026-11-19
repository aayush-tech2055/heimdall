"use client";

import { ArrowLeft, ArrowRight, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";

import { BrandMark } from "@/components/shell/brand-mark";

/** Sign-up entry point. Self-serve sign-up is the next step; until then, accounts are
 * created by the brand admin (and judges have accounts provided). */
export default function SignupPage() {
  return (
    <div className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-black px-4 text-white">
      <div className="hd-grid-bg absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" />
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.2, 0.7, 0.2, 1] }}
        className="relative w-full max-w-md rounded-3xl border border-white/15 bg-white/[0.06] p-8 backdrop-blur-xl"
      >
        <BrandMark tone="light" size={40} />
        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Create your Heimdall workspace
        </h1>
        <p className="mt-3 text-white/70">
          <Sparkles className="mr-1 inline size-4 text-amber-300" aria-hidden />
          Self-serve sign-up is coming soon. Today, accounts are created by your
          brand admin. If you already have one, sign in.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-black transition-transform hover:scale-[1.03] active:scale-95"
          >
            Sign in <ArrowRight className="size-4" aria-hidden />
          </Link>
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-full border border-white/25 px-6 py-3 text-sm font-semibold transition-colors hover:bg-white/10"
          >
            <ArrowLeft className="size-4" aria-hidden /> Back to home
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
