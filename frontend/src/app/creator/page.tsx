"use client";

import { Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { ContentTable } from "@/components/content/content-table";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { ContentSummary } from "@/types/api";

function MyContent() {
  const [items, setItems] = useState<ContentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const data = await api<ContentSummary[]>("/contents");
        setItems(data);
        if (data.some((c) => c.status === "checking"))
          timer = setTimeout(load, 4000);
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "Could not load your content",
        );
      }
    };
    void load();
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title="My content"
          description="Everything you have checked, and where it is in review."
        />
        <Button asChild>
          <Link href="/creator/new">
            <Plus aria-hidden /> New check
          </Link>
        </Button>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {items === null ? (
        <p
          className="text-muted-foreground flex items-center gap-2"
          role="status"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
        </p>
      ) : (
        <ContentTable
          items={items}
          hrefBase="/creator/content"
          empty="Nothing yet. Start with a new check."
        />
      )}
    </div>
  );
}

export default function CreatorPage() {
  return <RoleGate roles={["creator"]}>{() => <MyContent />}</RoleGate>;
}
