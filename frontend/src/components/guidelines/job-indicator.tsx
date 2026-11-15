"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth/auth-provider";
import { isActive, useGuidelineJobs } from "@/lib/use-guideline-jobs";

/** A small "extracting rules" badge in the header, on every admin page, while a job runs. */
export function GuidelineJobIndicator() {
  const { me } = useAuth();
  const isAdmin = me?.role === "admin";
  const { jobs } = useGuidelineJobs(me?.brand_id ?? null, isAdmin);
  const active = jobs.filter(isActive);
  if (!isAdmin || active.length === 0) return null;
  const total = active.reduce((n, j) => n + j.files.length, 0);
  const done = active.reduce((n, j) => n + j.files_done, 0);
  return (
    <span role="status">
      <Link
        href="/admin/guidelines"
        className="bg-muted hover:bg-muted/70 focus-visible:ring-ring inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm focus-visible:ring-2 focus-visible:outline-none"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Extracting rules: {done} of {total} file{total === 1 ? "" : "s"}
      </Link>
    </span>
  );
}
