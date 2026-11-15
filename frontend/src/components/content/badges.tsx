import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ContentStatus, FlagStatus } from "@/types/api";
import type { Severity } from "@/types/flag";

const STATUS: Record<ContentStatus, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-muted text-foreground" },
  checking: {
    label: "Checking…",
    className: "bg-sky-100 text-sky-900 border-sky-300",
  },
  creator_review: {
    label: "Needs your review",
    className: "bg-amber-100 text-amber-900 border-amber-300",
  },
  manager_review: {
    label: "With manager",
    className: "bg-violet-100 text-violet-900 border-violet-300",
  },
  changes_requested: {
    label: "Changes requested",
    className: "bg-red-100 text-red-900 border-red-300",
  },
  approved: {
    label: "Approved",
    className: "bg-green-100 text-green-900 border-green-300",
  },
};

export function ContentStatusBadge({ status }: { status: ContentStatus }) {
  const s = STATUS[status];
  return (
    <Badge variant="outline" className={s.className}>
      {s.label}
    </Badge>
  );
}

/** Severity colours, used for badges and text highlights. AA contrast on white. */
export const SEVERITY_STYLE: Record<
  Severity,
  { badge: string; mark: string; label: string }
> = {
  high: {
    badge: "bg-red-100 text-red-900 border-red-300",
    mark: "bg-red-100 decoration-red-600",
    label: "High",
  },
  medium: {
    badge: "bg-amber-100 text-amber-900 border-amber-300",
    mark: "bg-amber-100 decoration-amber-600",
    label: "Medium",
  },
  low: {
    badge: "bg-sky-100 text-sky-900 border-sky-300",
    mark: "bg-sky-100 decoration-sky-600",
    label: "Low",
  },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className={SEVERITY_STYLE[severity].badge}>
      {SEVERITY_STYLE[severity].label}
    </Badge>
  );
}

const FLAG_STATUS: Record<FlagStatus, string> = {
  open: "Open",
  accepted: "Fix accepted",
  edited: "Edited",
  dismissed: "Dismissed",
  excepted: "Exception approved",
};

export function FlagStatusBadge({ status }: { status: FlagStatus }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        status === "open"
          ? "border-foreground/30"
          : "bg-muted text-muted-foreground",
      )}
    >
      {FLAG_STATUS[status]}
    </Badge>
  );
}
