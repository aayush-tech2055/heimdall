"use client";

import { Fragment } from "react";

import { SEVERITY_STYLE } from "@/components/content/badges";
import { cn } from "@/lib/utils";
import type { StoredFlag } from "@/types/api";
import { isTextLocation, type Severity } from "@/types/flag";

const RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

type Segment = { start: number; end: number; flags: StoredFlag[] };

/** Split the text at every flag boundary so overlapping flags still render. */
function segments(text: string, flags: StoredFlag[]): Segment[] {
  const spans = flags
    .filter(
      (f) =>
        isTextLocation(f.location) &&
        f.location.evidence_end > f.location.evidence_start,
    )
    .map((f) => {
      const loc = f.location as {
        evidence_start: number;
        evidence_end: number;
      };
      return { f, s: loc.evidence_start, e: loc.evidence_end };
    });
  const cuts = new Set<number>([0, text.length]);
  spans.forEach(({ s, e }) => (cuts.add(s), cuts.add(e)));
  const points = [...cuts].sort((a, b) => a - b);
  const out: Segment[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [start, end] = [points[i], points[i + 1]];
    out.push({
      start,
      end,
      flags: spans.filter((x) => x.s <= start && x.e >= end).map((x) => x.f),
    });
  }
  return out;
}

/** The content with flagged evidence highlighted by severity. Missing-phrase flags show a
 * marker where the text should go. Clicking a highlight selects its flag. */
export function HighlightedText({
  text,
  flags,
  selectedId,
  onSelect,
}: {
  text: string;
  flags: StoredFlag[];
  selectedId: string | null;
  onSelect: (flagId: string) => void;
}) {
  const shown = flags.filter(
    (f) => f.status === "open" || f.status === "dismissed",
  );
  const markers = shown.filter(
    (f) =>
      isTextLocation(f.location) &&
      f.location.evidence_end === f.location.evidence_start,
  );
  return (
    <div
      className="bg-card rounded-lg border p-5 leading-7 whitespace-pre-wrap"
      aria-label="Content with flags highlighted"
    >
      {segments(text, shown).map((seg) => {
        const chunk = text.slice(seg.start, seg.end);
        const at = markers.filter(
          (m) =>
            isTextLocation(m.location) && m.location.evidence_start === seg.end,
        );
        const marks = at.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => onSelect(m.id)}
            className={cn(
              "mx-1 rounded border border-dashed px-1.5 py-0.5 align-baseline text-xs font-medium",
              SEVERITY_STYLE[m.severity].badge,
              selectedId === m.id && "ring-ring ring-2",
            )}
            aria-label={`Missing text flagged by ${m.source_id}`}
          >
            ＋ missing: {m.suggested_fix ?? m.source_id}
          </button>
        ));
        if (!seg.flags.length) {
          return (
            <Fragment key={seg.start}>
              {chunk}
              {marks}
            </Fragment>
          );
        }
        const worst = [...seg.flags].sort(
          (a, b) => RANK[a.severity] - RANK[b.severity],
        )[0];
        const selected = seg.flags.some((f) => f.id === selectedId);
        const dismissed = seg.flags.every((f) => f.status !== "open");
        return (
          <Fragment key={seg.start}>
            <mark
              role="button"
              tabIndex={0}
              onClick={() => onSelect(worst.id)}
              onKeyDown={(e) =>
                (e.key === "Enter" || e.key === " ") &&
                (e.preventDefault(), onSelect(worst.id))
              }
              aria-label={`${chunk}: flagged by ${seg.flags.map((f) => f.source_id).join(", ")}`}
              className={cn(
                "cursor-pointer rounded-sm text-inherit underline decoration-2 underline-offset-4",
                SEVERITY_STYLE[worst.severity].mark,
                dismissed && "bg-transparent decoration-dotted opacity-70",
                selected && "ring-ring ring-2",
              )}
            >
              {chunk}
            </mark>
            {marks}
          </Fragment>
        );
      })}
    </div>
  );
}
