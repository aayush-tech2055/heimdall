"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { GuidelineJobIndicator } from "@/components/guidelines/job-indicator";
import { Button } from "@/components/ui/button";
import { NAV_BY_ROLE, ROLE_LABEL } from "@/lib/roles";
import { cn } from "@/lib/utils";

export function NavLinks() {
  const pathname = usePathname();
  const { me, session, signOut } = useAuth();
  if (!session || !me) return null;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <ul className="flex flex-wrap gap-1">
        {NAV_BY_ROLE[me.role].map(({ href, label }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-full px-3.5 py-2 text-sm font-medium transition-all duration-200",
                  "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
                  active
                    ? "bg-primary text-primary-foreground shadow-[0_8px_18px_-10px_oklch(0_0_0_/_0.6)]"
                    : "text-foreground hover:bg-black/5",
                )}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
      <GuidelineJobIndicator />
      <span className="text-muted-foreground text-sm">
        {me.display_name ?? me.email} · {ROLE_LABEL[me.role]}, {me.brand_name}
      </span>
      <Button variant="ghost" size="sm" onClick={() => void signOut()}>
        <LogOut aria-hidden /> Sign out
      </Button>
    </div>
  );
}
