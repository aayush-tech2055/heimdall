"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { RoleGuide } from "@/components/guide/role-guide";
import { BrandMark } from "@/components/shell/brand-mark";
import { markGuideSeen } from "@/lib/guide";

/** Shown before a person's first sign-up: how each role works, then "Create my account". */
export default function GuidePage() {
  const router = useRouter();

  function toSignup() {
    markGuideSeen();
    router.push("/signup");
  }

  return (
    <div className="min-h-[100svh] bg-black text-white">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-black/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-md font-semibold focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
          >
            <BrandMark tone="light" /> Heimdall
          </Link>
          <button
            type="button"
            onClick={toSignup}
            className="rounded-full px-4 py-2 text-sm font-semibold text-white/80 hover:bg-white/10 hover:text-white focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
          >
            Skip to sign up
          </button>
        </div>
      </header>

      <section className="relative overflow-hidden px-4 pt-16 pb-28">
        <div className="hd-grid-bg absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black,transparent_65%)]" />
        <div className="relative mx-auto max-w-6xl">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.2, 0.7, 0.2, 1] }}
            className="text-center"
          >
            <p className="text-xs font-semibold tracking-[0.25em] text-white/70 uppercase">
              Before you sign up
            </p>
            <h1 className="mx-auto mt-3 max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
              How Heimdall works for you
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-white/70">
              Heimdall checks every draft against your brand&apos;s rules and
              facts before it is published. Pick your role below to see each
              step, then create your account with that role.
            </p>
          </motion.div>
          <div className="mt-14">
            <RoleGuide headingLevel={2} />
          </div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-24 rounded-3xl border border-white/15 bg-gradient-to-br from-indigo-500/20 via-white/[0.04] to-amber-400/15 p-8 text-center sm:p-12"
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ready? Pick your role and start.
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-white/70">
              Admins create a brand. Creators and managers join an admin&apos;s
              team after signing up.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <button
                type="button"
                onClick={toSignup}
                className="inline-flex items-center gap-2 rounded-full bg-white px-7 py-3.5 text-sm font-semibold text-black transition-transform hover:scale-[1.03] focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black focus-visible:outline-none active:scale-95"
              >
                Create my account <ArrowRight className="size-4" aria-hidden />
              </button>
              <Link
                href="/"
                className="inline-flex items-center gap-2 rounded-full border border-white/25 px-7 py-3.5 text-sm font-semibold hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
              >
                <ArrowLeft className="size-4" aria-hidden /> Back to home
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
