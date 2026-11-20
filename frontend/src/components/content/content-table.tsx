"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ContentStatusBadge } from "@/components/content/badges";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ContentSummary } from "@/types/api";

export function ContentTable({
  items,
  hrefBase,
  showCreator = false,
  empty,
  actionLabel = "Open",
}: {
  items: ContentSummary[];
  hrefBase: string;
  showCreator?: boolean;
  empty: string;
  /** Text of the button that opens an item, e.g. "Review" in the manager queue. */
  actionLabel?: string;
}) {
  const router = useRouter();
  if (!items.length) return <p className="text-muted-foreground">{empty}</p>;
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Title</TableHead>
            {showCreator && <TableHead>Creator</TableHead>}
            <TableHead>Status</TableHead>
            <TableHead>Open flags</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead>
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((c) => (
            <TableRow
              key={c.id}
              className="hover:bg-primary/5 cursor-pointer transition-colors"
              onClick={() => router.push(`${hrefBase}/${c.id}`)}
            >
              <TableCell>
                <Link
                  href={`${hrefBase}/${c.id}`}
                  className="font-medium underline underline-offset-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  {c.title}
                </Link>
              </TableCell>
              {showCreator && (
                <TableCell>
                  <span className="block">{c.creator_name ?? "—"}</span>
                  {c.creator_email && (
                    <span className="text-muted-foreground block text-xs">
                      {c.creator_email}
                    </span>
                  )}
                </TableCell>
              )}
              <TableCell>
                <ContentStatusBadge status={c.status} />
              </TableCell>
              <TableCell>
                {c.counts.open}
                {c.counts.open_high > 0 && (
                  <span className="text-red-800">
                    {" "}
                    ({c.counts.open_high} high)
                  </span>
                )}
              </TableCell>
              <TableCell>v{c.latest_version_number ?? 1}</TableCell>
              <TableCell className="text-muted-foreground text-sm">
                {new Date(c.updated_at).toLocaleString()}
              </TableCell>
              <TableCell className="text-right">
                <Button
                  asChild
                  size="sm"
                  variant={
                    c.status === "manager_review" ? "default" : "outline"
                  }
                >
                  <Link
                    href={`${hrefBase}/${c.id}`}
                    aria-label={`${actionLabel} ${c.title}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {actionLabel} <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
