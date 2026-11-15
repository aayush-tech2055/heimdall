"use client";

import { History, Loader2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { diffText } from "@/lib/diff";
import { cn } from "@/lib/utils";
import type { ContentDetail, VersionFlags } from "@/types/api";

/** Version list with flag counts, a diff against the previous version, and a way to view
 * any version's flags (task 7.9). */
export function VersionHistory({
  content,
  viewing,
  onView,
}: {
  content: ContentDetail;
  viewing: string | null;
  onView: (versionId: string | null) => void;
}) {
  const [diffFor, setDiffFor] = useState<string | null>(null);
  const [diff, setDiff] = useState<ReturnType<typeof diffText> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const versions = [...content.versions].reverse();

  async function showDiff(versionId: string) {
    const index = content.versions.findIndex((v) => v.id === versionId);
    if (index < 1) return;
    setBusy(true);
    setError(null);
    try {
      const [prev, curr] = await Promise.all([
        api<VersionFlags>(`/versions/${content.versions[index - 1].id}/flags`),
        api<VersionFlags>(`/versions/${versionId}/flags`),
      ]);
      setDiff(diffText(prev.text, curr.text));
      setDiffFor(versionId);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not load the versions",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="history-h" className="space-y-3">
      <h2
        id="history-h"
        className="flex items-center gap-2 text-lg font-semibold"
      >
        <History className="size-4" aria-hidden /> Version history
      </h2>
      <ol className="space-y-2">
        {versions.map((v) => {
          const latest = v.id === content.latest_version_id;
          const isViewing = viewing ? viewing === v.id : latest;
          return (
            <li
              key={v.id}
              className={cn(
                "rounded-md border p-2 text-sm",
                isViewing && "border-primary",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">Version {v.version_number}</span>
                {latest && <Badge variant="secondary">latest</Badge>}
                <span className="text-muted-foreground text-xs">
                  {new Date(v.created_at).toLocaleString()}
                </span>
              </div>
              <p className="text-muted-foreground text-xs">
                {v.review_error
                  ? `Check failed: ${v.review_error}`
                  : `${v.counts.open} open (${v.counts.open_high} high) · ${v.counts.resolved} resolved`}
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                {!isViewing && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onView(latest ? null : v.id)}
                  >
                    View flags
                  </Button>
                )}
                {v.version_number > 1 && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => showDiff(v.id)}
                  >
                    {busy && diffFor !== v.id && (
                      <Loader2 className="animate-spin" aria-hidden />
                    )}
                    Changes from v{v.version_number - 1}
                  </Button>
                )}
              </div>
              {diffFor === v.id && diff && (
                <div
                  className="bg-muted mt-2 rounded-md p-2 whitespace-pre-wrap"
                  aria-label="Changes"
                >
                  {diff.map((part, i) =>
                    part.type === "same" ? (
                      <span key={i}>{part.text}</span>
                    ) : part.type === "add" ? (
                      <ins
                        key={i}
                        className="bg-green-200 text-green-950 no-underline"
                      >
                        {part.text}
                      </ins>
                    ) : (
                      <del key={i} className="bg-red-200 text-red-950">
                        {part.text}
                      </del>
                    ),
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {error && <p className="text-destructive text-sm">{error}</p>}
    </section>
  );
}
