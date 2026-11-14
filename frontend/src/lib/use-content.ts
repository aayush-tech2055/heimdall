"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { ContentDetail, VersionFlags } from "@/types/api";

/** Loads a content item and the flags of a version (latest by default), polling every
 * 3 seconds while the content is being checked. */
export function useContent(contentId: string, versionId?: string | null) {
  const [content, setContent] = useState<ContentDetail | null>(null);
  const [flags, setFlags] = useState<VersionFlags | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const c = await api<ContentDetail>(`/contents/${contentId}`);
      setContent(c);
      setError(null);
      const vid = versionId ?? c.latest_version_id;
      if (vid && c.status !== "checking")
        setFlags(await api<VersionFlags>(`/versions/${vid}/flags`));
      if (timer.current) clearTimeout(timer.current);
      if (c.status === "checking")
        timer.current = setTimeout(() => void load(), 3000);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not load this content",
      );
    }
  }, [contentId, versionId]);

  useEffect(() => {
    void load();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [load]);

  return { content, flags, error, reload: load, setContent };
}
