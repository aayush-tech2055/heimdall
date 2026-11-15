"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { SEVERITY_STYLE } from "@/components/content/badges";
import { api, apiBlobUrl, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ReviewUnit, StoredFlag } from "@/types/api";
import type { BBox, ImageLocation, PdfLocation } from "@/types/flag";

type PageSize = { page: number; width: number; height: number };

const isPdf = (l: unknown): l is PdfLocation =>
  typeof l === "object" && l !== null && "page" in l && "bbox" in l;
const isImage = (l: unknown): l is ImageLocation =>
  typeof l === "object" && l !== null && "image_id" in l;

function useBlobUrl(path: string | null) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!path) return;
    let revoked: string | null = null;
    apiBlobUrl(path)
      .then((u) => {
        revoked = u;
        setUrl(u);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load the file"),
      );
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [path]);
  return { url, error };
}

function Box({
  flag,
  style,
  selected,
  onSelect,
}: {
  flag: StoredFlag;
  style: React.CSSProperties;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      style={style}
      aria-label={`${flag.severity} flag ${flag.source_id}: ${flag.evidence}`}
      className={cn(
        "absolute rounded-sm border-2 opacity-60 transition-opacity hover:opacity-90 focus-visible:opacity-100",
        SEVERITY_STYLE[flag.severity].badge,
        flag.status !== "open" && "border-dashed opacity-40",
        selected && "ring-ring opacity-90 ring-2",
      )}
    />
  );
}

const pct = (v: number, of: number) => `${(100 * v) / of}%`;

function boxStyle(b: BBox, w: number, h: number): React.CSSProperties {
  return {
    left: pct(b[0], w),
    top: pct(b[1], h),
    width: pct(b[2] - b[0], w),
    height: pct(b[3] - b[1], h),
  };
}

function PdfPage({
  versionId,
  size,
  flags,
  units,
  selectedId,
  onSelect,
}: {
  versionId: string;
  size: PageSize;
  flags: StoredFlag[];
  units: ReviewUnit[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { url, error } = useBlobUrl(
    `/versions/${versionId}/pages/${size.page}.png`,
  );
  const boxes = flags.flatMap((f) =>
    isPdf(f.location) && f.location.page === size.page
      ? [{ f, b: f.location.bbox }]
      : [],
  );
  const imageBoxes = flags.flatMap((f) => {
    if (!isImage(f.location)) return [];
    const loc = f.location;
    const unit = units.find((u) => u.unit_id === loc.image_id);
    const page = unit?.location.page as number | undefined;
    const ib = unit?.location.bbox as BBox | undefined;
    if (page !== size.page || !ib) return [];
    const r = loc.region ?? [0, 0, 1, 1];
    const [x0, y0, x1, y1] = ib;
    const bw = x1 - x0;
    const bh = y1 - y0;
    return [
      {
        f,
        b: [
          x0 + r[0] * bw,
          y0 + r[1] * bh,
          x0 + r[2] * bw,
          y0 + r[3] * bh,
        ] as BBox,
      },
    ];
  });
  return (
    <figure className="space-y-1">
      <div
        className="bg-muted relative w-full overflow-hidden rounded-md border"
        style={{ aspectRatio: `${size.width} / ${size.height}` }}
      >
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={`Page ${size.page}`}
            className="absolute inset-0 h-full w-full"
          />
        ) : (
          <p className="text-muted-foreground absolute inset-0 flex items-center justify-center gap-2 text-sm">
            {error ?? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden /> Loading
                page {size.page}…
              </>
            )}
          </p>
        )}
        {[...boxes, ...imageBoxes].map(({ f, b }) => (
          <Box
            key={f.id}
            flag={f}
            style={boxStyle(b, size.width, size.height)}
            selected={selectedId === f.id}
            onSelect={() => onSelect(f.id)}
          />
        ))}
      </div>
      <figcaption className="text-muted-foreground text-xs">
        Page {size.page}
      </figcaption>
    </figure>
  );
}

/** Pages of a PDF version with flag boxes (task 8.4). */
export function PdfViewer({
  versionId,
  flags,
  units,
  selectedId,
  onSelect,
}: {
  versionId: string;
  flags: StoredFlag[];
  units: ReviewUnit[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [pages, setPages] = useState<PageSize[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<PageSize[]>(`/versions/${versionId}/pages`)
      .then(setPages)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load the PDF"),
      );
  }, [versionId]);
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!pages)
    return <p className="text-muted-foreground text-sm">Loading the PDF…</p>;
  const shown = flags.filter(
    (f) => f.status === "open" || f.status === "dismissed",
  );
  return (
    <div className="space-y-4" aria-label="PDF with flags marked">
      {pages.map((p) => (
        <PdfPage
          key={p.page}
          versionId={versionId}
          size={p}
          flags={shown}
          units={units}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

/** An uploaded image with flagged regions (task 8.4). */
export function ImageViewer({
  versionId,
  flags,
  selectedId,
  onSelect,
}: {
  versionId: string;
  flags: StoredFlag[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { url, error } = useBlobUrl(`/versions/${versionId}/file`);
  const shown = flags.filter(
    (f) =>
      (f.status === "open" || f.status === "dismissed") && isImage(f.location),
  );
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!url)
    return <p className="text-muted-foreground text-sm">Loading the image…</p>;
  return (
    <div className="relative inline-block max-w-full rounded-md border">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt="Uploaded content" className="block max-w-full" />
      {shown.map((f) => {
        const r = (f.location as ImageLocation).region ?? [0, 0, 1, 1];
        return (
          <Box
            key={f.id}
            flag={f}
            style={boxStyle(r, 1, 1)}
            selected={selectedId === f.id}
            onSelect={() => onSelect(f.id)}
          />
        );
      })}
    </div>
  );
}
