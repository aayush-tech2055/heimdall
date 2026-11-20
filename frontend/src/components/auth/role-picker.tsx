"use client";

import { Building2, ClipboardCheck, PenLine } from "lucide-react";
import { motion } from "motion/react";

import { cn } from "@/lib/utils";
import type { Role } from "@/types/api";

const ROLES: {
  value: Role;
  title: string;
  blurb: string;
  icon: typeof Building2;
  accent: string;
}[] = [
  {
    value: "admin",
    title: "Admin",
    blurb: "Owns a brand: uploads guidelines and facts, builds the team.",
    icon: Building2,
    accent: "from-amber-300/30 to-amber-500/5 text-amber-200",
  },
  {
    value: "manager",
    title: "Manager",
    blurb: "Reviews what creators submit, approves or sends it back.",
    icon: ClipboardCheck,
    accent: "from-cyan-300/30 to-cyan-500/5 text-cyan-200",
  },
  {
    value: "creator",
    title: "Creator",
    blurb: "Writes content, fixes flags, submits to a manager.",
    icon: PenLine,
    accent: "from-fuchsia-300/30 to-fuchsia-500/5 text-fuchsia-200",
  },
];

/** Three role cards (a radio group) on a dark surface. */
export function RolePicker({
  value,
  onChange,
}: {
  value: Role | null;
  onChange: (role: Role) => void;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium text-white/80">
        I am joining as
      </legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {ROLES.map(({ value: v, title, blurb, icon: Icon, accent }, i) => {
          const on = value === v;
          return (
            <motion.label
              key={v}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.07 }}
              className={cn(
                "relative flex cursor-pointer flex-col gap-2 rounded-2xl border p-3.5 transition-all",
                "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-white/80",
                on
                  ? "border-white bg-white/[0.12] shadow-[0_0_0_1px_white]"
                  : "border-white/15 bg-white/[0.04] hover:border-white/35 hover:bg-white/[0.07]",
              )}
            >
              <input
                type="radio"
                name="role"
                value={v}
                checked={on}
                onChange={() => onChange(v)}
                className="sr-only"
              />
              <span
                className={cn(
                  "flex size-9 items-center justify-center rounded-xl bg-gradient-to-br",
                  accent,
                )}
              >
                <Icon className="size-4.5" aria-hidden />
              </span>
              <span className="font-semibold text-white">{title}</span>
              <span className="text-xs leading-snug text-white/65">
                {blurb}
              </span>
            </motion.label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Shared input style for the dark auth pages. */
export const DARK_INPUT =
  "h-10 w-full rounded-md border border-white/20 bg-white/[0.06] px-3 text-sm text-white placeholder:text-white/40 focus-visible:border-white focus-visible:ring-2 focus-visible:ring-white/40 focus-visible:outline-none";
