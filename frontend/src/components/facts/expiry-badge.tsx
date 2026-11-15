import { Badge } from "@/components/ui/badge";
import type { Expiry } from "@/types/api";

/** Expiry shown in code-computed terms: expired, expiring within 30 days, valid or none. */
export function ExpiryBadge({
  expiry,
  validUntil,
}: {
  expiry: Expiry;
  validUntil: string | null;
}) {
  if (expiry === "expired")
    return (
      <Badge
        className="border-red-300 bg-red-100 text-red-900"
        variant="outline"
      >
        expired {validUntil}
      </Badge>
    );
  if (expiry === "expiring")
    return (
      <Badge
        className="border-amber-300 bg-amber-100 text-amber-900"
        variant="outline"
      >
        expires {validUntil}
      </Badge>
    );
  if (expiry === "valid")
    return (
      <span className="text-muted-foreground text-sm">until {validUntil}</span>
    );
  return <span className="text-muted-foreground text-sm">no expiry</span>;
}
