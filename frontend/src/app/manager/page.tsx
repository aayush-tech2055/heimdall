"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { ContentTable } from "@/components/content/content-table";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { api, ApiError } from "@/lib/api";
import type { ContentStatus, ContentSummary, Me } from "@/types/api";

const TABS: { value: ContentStatus | "all"; label: string }[] = [
  { value: "manager_review", label: "Waiting for you" },
  { value: "changes_requested", label: "Sent back" },
  { value: "approved", label: "Approved" },
  { value: "all", label: "All" },
];

function Queue({ me }: { me: Me }) {
  const [items, setItems] = useState<ContentSummary[] | null>(null);
  const [tab, setTab] = useState<ContentStatus | "all">("manager_review");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<ContentSummary[]>("/contents")
      .then(setItems)
      .catch((e) =>
        setError(
          e instanceof ApiError ? e.message : "Could not load the queue",
        ),
      );
  }, []);

  const shown = useMemo(
    () => (items ?? []).filter((c) => tab === "all" || c.status === tab),
    [items, tab],
  );
  const count = (s: ContentStatus | "all") =>
    (items ?? []).filter((c) => s === "all" || c.status === s).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Review queue"
        description={`Content from ${me.brand_name}'s creators that needs a decision.`}
      />
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <FilterTabs
        label="Filter by status"
        value={tab}
        onChange={setTab}
        options={TABS.map((t) => ({
          value: t.value,
          label: `${t.label} (${count(t.value)})`,
        }))}
      />
      {items === null ? (
        <p
          className="text-muted-foreground flex items-center gap-2"
          role="status"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
        </p>
      ) : (
        <ContentTable
          items={shown}
          hrefBase="/manager/content"
          showCreator
          actionLabel="Review"
          empty="Nothing here right now."
        />
      )}
    </div>
  );
}

export default function ManagerPage() {
  return (
    <RoleGate roles={["manager", "admin"]}>
      {(me) => <Queue me={me} />}
    </RoleGate>
  );
}
