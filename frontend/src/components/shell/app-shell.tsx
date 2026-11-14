import Link from "next/link";

import { NavLinks } from "@/components/shell/nav-links";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="bg-primary text-primary-foreground sr-only z-50 rounded-md px-3 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link
            href="/"
            className="focus-visible:ring-ring rounded-md focus-visible:outline-none focus-visible:ring-2"
          >
            <span className="text-lg font-semibold tracking-tight">
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
