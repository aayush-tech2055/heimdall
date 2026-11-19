import Link from "next/link";

import { NavLinks } from "@/components/shell/nav-links";

/** The Heimdall mark: two arcs (the bridge watched) and a gold eye. */
function BrandMark() {
  return (
    <svg
      width="26"
      height="18"
      viewBox="0 0 58 40"
      aria-hidden
      className="shrink-0"
    >
      <path
        d="M5 34a24 24 0 0 1 48 0"
        fill="none"
        stroke="var(--brand-navy)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d="M16 34a13 13 0 0 1 26 0"
        fill="none"
        stroke="oklch(0.511 0.262 276.966)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="29" cy="33" r="5.5" fill="var(--brand-gold)" />
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
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
