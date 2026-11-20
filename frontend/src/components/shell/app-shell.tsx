"use client";

import Link from "next/link";

import { usePathname } from "next/navigation";

import { BrandMark } from "@/components/shell/brand-mark";
import { NavLinks } from "@/components/shell/nav-links";

/** Pages with their own full-bleed layout and navigation (the public home page). */
const BARE = new Set(["/", "/signup", "/onboarding", "/auth/callback"]);

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (BARE.has(pathname)) {
    return (
      <>
        <a
          href="#main"
          className="sr-only z-[60] rounded-md bg-black px-3 py-2 text-white focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
        >
          Skip to content
        </a>
        <main id="main">{children}</main>
      </>
    );
  }
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="bg-primary text-primary-foreground sr-only z-50 rounded-md px-3 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-white/60 bg-white/75 shadow-[0_1px_0_0_oklch(0.92_0.01_277)] backdrop-blur-md supports-[backdrop-filter]:bg-white/65">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link
            href="/"
            className="focus-visible:ring-ring rounded-md focus-visible:outline-none focus-visible:ring-2"
          >
            <span className="inline-flex items-center gap-2 text-lg font-semibold tracking-tight">
              <BrandMark />
              Heimdall
            </span>
            <span className="text-muted-foreground ml-2 hidden text-sm sm:inline">
              Nothing crosses unchecked.
            </span>
          </Link>
          <nav aria-label="Main">
            <NavLinks />
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {children}
      </main>
    </div>
  );
}
