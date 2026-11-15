"use client";

import { Check, Globe, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { FactChange, Me } from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_URLS = [
  `${API_URL}/demo-site/acmelearn/pricing.html`,
  `${API_URL}/demo-site/acmelearn/about.html`,
];

function WebsiteCheck({ me }: { me: Me }) {
  const [urls, setUrls] = useState(DEMO_URLS.join("\n"));
  const [changes, setChanges] = useState<FactChange[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [deciding, setDeciding] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setChanges(
        await api<FactChange[]>(`/brands/${me.brand_id}/fact-changes`),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load changes");
    }
  }, [me.brand_id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const list = urls
        .split(/\s+/)
        .map((u) => u.trim())
        .filter(Boolean);
      const found = await api<FactChange[]>(
        `/brands/${me.brand_id}/website-check`,
        { json: { urls: list } },
      );
      setChanges(found);
      setNotice(
        found.length
          ? `${found.length} change${found.length === 1 ? "" : "s"} to review.`
          : "The website matches your approved facts.",
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The check failed");
    } finally {
      setBusy(false);
    }
  }

  async function decide(change: FactChange, action: "accept" | "reject") {
    setDeciding(change.id);
    try {
      await api(`/fact-changes/${change.id}/${action}`, { method: "POST" });
      setChanges((prev) => (prev ?? []).filter((c) => c.id !== change.id));
      setNotice(
        action === "accept"
          ? change.kind === "changed"
            ? `${change.fact_code} updated (same code, so content citing it stays linked).`
            : "New fact added and approved."
          : "Change rejected.",
      );
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not save the decision",
      );
    } finally {
      setDeciding(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Website check"
        description={`Compare ${me.brand_name}'s web pages with the approved facts. Nothing changes until you accept it.`}
      />
      <form onSubmit={run} className="space-y-3">
        <Label htmlFor="urls">
          Pages to check (one URL per line, up to 10)
        </Label>
        <Textarea
          id="urls"
          rows={4}
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
        />
        <p className="text-muted-foreground text-sm">
          During the event only the fictional AcmeLearn site served by the
          backend is used.
        </p>
        <Button type="submit" disabled={busy}>
          {busy ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Globe aria-hidden />
          )}
          {busy ? "Reading pages and comparing facts…" : "Check website"}
        </Button>
      </form>
      {notice && (
        <Alert role="status">
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <section aria-labelledby="changes-h" className="space-y-3">
        <h2 id="changes-h" className="text-xl font-semibold">
          Changes waiting for you ({changes?.length ?? 0})
        </h2>
        {changes === null ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : changes.length === 0 ? (
          <p className="text-muted-foreground">Nothing to review.</p>
        ) : (
          <ul className="space-y-2">
            {changes.map((c) => (
              <li
                key={c.id}
                className="bg-card flex flex-wrap items-start justify-between gap-3 rounded-lg border p-3"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={c.kind === "changed" ? "default" : "secondary"}
                    >
                      {c.kind === "changed"
                        ? `Changed ${c.fact_code}`
                        : "New fact"}
                    </Badge>
                    <span className="font-medium">
                      {c.entity} · {c.attribute}
                    </span>
                  </div>
                  <p>
                    {c.kind === "changed" ? (
                      <>
                        <del className="text-muted-foreground">
                          {c.old_value}
                        </del>{" "}
                        →{" "}
                        <ins className="font-semibold no-underline">
                          {c.new_value}
                        </ins>
                      </>
                    ) : (
                      <span className="font-semibold">{c.new_value}</span>
                    )}{" "}
                    {c.unit}
                  </p>
                  <p className="text-sm">{c.statement}</p>
                  <p className="text-muted-foreground text-xs break-all">
                    From {c.source_url}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={deciding === c.id}
                    onClick={() => decide(c, "accept")}
                  >
                    <Check aria-hidden /> Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={deciding === c.id}
                    onClick={() => decide(c, "reject")}
                  >
                    <X aria-hidden /> Reject
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default function WebsitePage() {
  return (
    <RoleGate roles={["admin"]}>{(me) => <WebsiteCheck me={me} />}</RoleGate>
  );
}
