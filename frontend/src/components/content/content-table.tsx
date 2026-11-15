import Link from "next/link";

import { ContentStatusBadge } from "@/components/content/badges";
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
}: {
  items: ContentSummary[];
  hrefBase: string;
  showCreator?: boolean;
  empty: string;
}) {
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
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((c) => (
            <TableRow key={c.id}>
              <TableCell>
                <Link
                  href={`${hrefBase}/${c.id}`}
                  className="font-medium underline-offset-2 hover:underline"
                >
                  {c.title}
                </Link>
              </TableCell>
              {showCreator && <TableCell>{c.creator_name ?? "—"}</TableCell>}
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
