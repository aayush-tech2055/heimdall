"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { GuidelineJob } from "@/types/api";

/** Fired after a guideline upload starts, so every listener starts polling at once. */
export const GUIDELINE_JOB_EVENT = "heimdall:guideline-job";

export const isActive = (job: GuidelineJob) =>
  job.status === "queued" || job.status === "running";

/**
 * The brand's recent guideline uploads. Polls every 3 seconds while any of them is still
 * queued or running, and stops once all are finished.
 */
export function useGuidelineJobs(brandId: string | null, enabled = true) {
  const [jobs, setJobs] = useState<GuidelineJob[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    if (!brandId || !enabled) return;
    if (timer.current) clearTimeout(timer.current);
    try {
      const list = await api<GuidelineJob[]>(
        `/brands/${brandId}/guideline-jobs`,
      );
      setJobs(list);
      if (list.some(isActive)) timer.current = setTimeout(refresh, 3000);
    } catch {
      timer.current = setTimeout(refresh, 10000); // network hiccup: try again later
    }
  }, [brandId, enabled]);

  useEffect(() => {
    void refresh();
    const onStart = () => void refresh();
    window.addEventListener(GUIDELINE_JOB_EVENT, onStart);
    return () => {
      window.removeEventListener(GUIDELINE_JOB_EVENT, onStart);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [refresh]);

  return { jobs, refresh };
}
