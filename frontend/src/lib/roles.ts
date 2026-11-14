import type { Role } from "@/types/api";

export type NavLink = { href: string; label: string };

/** Where each role lands after sign-in. */
export const HOME_BY_ROLE: Record<Role, string> = {
  admin: "/admin/guidelines",
  creator: "/creator",
  manager: "/manager",
};

/** Navigation shown to each role. */
export const NAV_BY_ROLE: Record<Role, NavLink[]> = {
  admin: [
    { href: "/admin/guidelines", label: "Guidelines" },
    { href: "/admin/facts", label: "Facts" },
    { href: "/admin/website", label: "Website check" },
    { href: "/admin/assets", label: "Assets" },
    { href: "/admin/settings", label: "Settings" },
    { href: "/insights", label: "Insights" },
    { href: "/disclosure", label: "AI disclosure" },
  ],
  creator: [
    { href: "/creator", label: "My content" },
    { href: "/creator/new", label: "New check" },
    { href: "/disclosure", label: "AI disclosure" },
  ],
  manager: [
    { href: "/manager", label: "Review queue" },
    { href: "/insights", label: "Insights" },
    { href: "/disclosure", label: "AI disclosure" },
  ],
};

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Admin",
  creator: "Creator",
  manager: "Manager",
};
