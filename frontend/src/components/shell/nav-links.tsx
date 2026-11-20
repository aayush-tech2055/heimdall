"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { GuidelineJobIndicator } from "@/components/guidelines/job-indicator";
import { Button } from "@/components/ui/button";
import { NAV_BY_ROLE, ROLE_LABEL } from "@/lib/roles";
import { cn } from "@/lib/utils";

export function NavLinks() {
  const pathname = usePathname();
  const router = useRouter();
  const { me, session, signOut, switchBrand } = useAuth();
  const [switching, setSwitching] = useState(false);
  if (!session || !me || !me.role) return null;
  const role = me.role;

  async function onSwitch(brandId: string) {
    setSwitching(true);
    try {
      await switchBrand(brandId);
      router.refresh();
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <ul className="flex flex-wrap gap-1">
        {NAV_BY_ROLE[role].map(({ href, label }) => {
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
        {me.display_name ?? me.email} · {ROLE_LABEL[role]}
        {me.memberships.length <= 1 && me.brand_name
          ? `, ${me.brand_name}`
          : ""}
      </span>
      {me.memberships.length > 1 && (
        <label className="flex items-center gap-1.5 text-sm">
          <span className="text-muted-foreground">Following</span>
          <select
            aria-label="Brand whose guidelines you follow"
            className="border-input bg-background focus-visible:ring-ring h-8 rounded-full border px-3 text-sm font-medium focus-visible:ring-2 focus-visible:outline-none"
            value={me.brand_id ?? ""}
            disabled={switching}
            onChange={(e) => void onSwitch(e.target.value)}
          >
            {me.memberships.map((m) => (
              <option key={m.brand_id} value={m.brand_id}>
                {m.brand_name}
              </option>
            ))}
          </select>
        </label>
      )}
      <Button variant="ghost" size="sm" onClick={() => void signOut()}>
        <LogOut aria-hidden /> Sign out
      </Button>
    </div>
  );
}
