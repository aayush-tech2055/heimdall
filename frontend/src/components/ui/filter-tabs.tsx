"use client";

import { cn } from "@/lib/utils";

/** Tab-styled filter buttons (a toggle group, not ARIA tabs: there are no tab panels). */
export function FilterTabs<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="bg-muted text-muted-foreground inline-flex h-9 w-fit items-center rounded-lg p-[3px]"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "focus-visible:ring-ring inline-flex h-[calc(100%-1px)] items-center rounded-md px-2.5 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:outline-none",
            value === o.value
              ? "bg-background text-foreground shadow-sm"
              : "text-foreground/80 hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
