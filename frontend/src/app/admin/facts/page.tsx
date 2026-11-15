"use client";

import { FileUp, Loader2, Pencil, Plus, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { ExpiryBadge } from "@/components/facts/expiry-badge";
import { FactDialog } from "@/components/facts/fact-dialog";
import { StatusBadge } from "@/components/guidelines/rule-list";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError } from "@/lib/api";
import type { Fact, FactStatus, Me } from "@/types/api";

type Filter = "all" | FactStatus;

function FactsWorkspace({ me }: { me: Me }) {
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dialog, setDialog] = useState<{ open: boolean; fact: Fact | null }>({
    open: false,
    fact: null,
  });
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const base = `/brands/${me.brand_id}/facts`;

  const load = useCallback(async () => {
    try {
      setFacts(await api<Fact[]>(base));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load facts");
    }
  }, [base]);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (facts ?? []).filter(
      (f) =>
        (filter === "all" || f.status === filter) &&
        (!q ||
          [f.fact_code, f.entity, f.attribute, f.value, f.statement].some((s) =>
            s.toLowerCase().includes(q),
          )),
    );
  }, [facts, filter, query]);

  function upsert(updated: Fact[]) {
    setFacts((prev) => {
      const byCode = new Map((prev ?? []).map((f) => [f.fact_code, f]));
      updated.forEach((f) => byCode.set(f.fact_code, f));
      return [...byCode.values()].sort((a, b) =>
        a.fact_code.localeCompare(b.fact_code),
      );
    });
  }

  async function importCsv(file: File) {
    setImporting(true);
    setError(null);
    setImportErrors([]);
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await api<{ imported: Fact[] }>(`${base}/import`, {
        form,
      });
      upsert(result.imported);
      setFilter("pending");
      setNotice(
        `Imported ${result.imported.length} facts. They are pending: review and approve them.`,
      );
    } catch (e) {
      if (e instanceof ApiError && e.status === 422)
        setImportErrors(e.message.split("; "));
      else setError(e instanceof ApiError ? e.message : "Import failed");
    } finally {
      setImporting(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function setStatus(action: "approve" | "reject") {
    try {
      upsert(
        await api<Fact[]>(`${base}/approve`, {
          json: { codes: [...selected], action },
        }),
      );
      setNotice(
        `${selected.size} fact${selected.size === 1 ? "" : "s"} ${action}d.`,
      );
      setSelected(new Set());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update facts");
    }
  }

  const count = (s: Filter) =>
    (facts ?? []).filter((f) => s === "all" || f.status === s).length;
  const expired = (facts ?? []).filter(
    (f) => f.status === "approved" && f.expiry === "expired",
  ).length;
  const expiring = (facts ?? []).filter(
    (f) => f.status === "approved" && f.expiry === "expiring",
  ).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Facts"
        description={`The approved facts that claims in ${me.brand_name}'s content are checked against.`}
      />
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => setDialog({ open: true, fact: null })}>
          <Plus aria-hidden /> Add a fact
        </Button>
        <Button
          variant="outline"
          disabled={importing}
          onClick={() => fileInput.current?.click()}
        >
          {importing ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <FileUp aria-hidden />
          )}
          Import CSV
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          aria-label="Facts CSV file"
          onChange={(e) => e.target.files?.[0] && importCsv(e.target.files[0])}
        />
        <p className="text-muted-foreground self-center text-sm">
          CSV columns: entity, attribute, value, unit, statement, source,
          valid_until (YYYY-MM-DD)
        </p>
      </div>
      {(expired > 0 || expiring > 0) && (
        <Alert>
          <AlertTitle>Facts need attention</AlertTitle>
          <AlertDescription>
            {expired} approved fact{expired === 1 ? " has" : "s have"} expired
            and {expiring} expire{expiring === 1 ? "s" : ""} within 30 days.
            Content citing expired facts is flagged as outdated.
          </AlertDescription>
        </Alert>
      )}
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
      {importErrors.length > 0 && (
        <Alert variant="destructive" role="alert">
          <AlertTitle>
            Nothing was imported. Fix these rows and try again:
          </AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {importErrors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
          <TabsList>
            {(["all", "pending", "approved", "rejected"] as Filter[]).map(
              (f) => (
                <TabsTrigger key={f} value={f} className="capitalize">
                  {f} ({count(f)})
                </TabsTrigger>
              ),
            )}
          </TabsList>
        </Tabs>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search
              className="text-muted-foreground absolute top-2.5 left-2 size-4"
              aria-hidden
            />
            <Input
              aria-label="Search facts"
              placeholder="Search facts"
              className="w-56 pl-8"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Button
            disabled={!selected.size}
            onClick={() => setStatus("approve")}
          >
            Approve ({selected.size})
          </Button>
          <Button
            variant="outline"
            disabled={!selected.size}
            onClick={() => setStatus("reject")}
          >
            Reject
          </Button>
        </div>
      </div>
      {facts === null ? (
        <p
          className="text-muted-foreground flex items-center gap-2"
          role="status"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading facts…
        </p>
      ) : shown.length === 0 ? (
        <p className="text-muted-foreground">
          {facts.length
            ? "No facts match."
            : "No facts yet. Add one or import a CSV."}
        </p>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8">
                  <Checkbox
                    aria-label="Select all shown facts"
                    checked={shown.every((f) => selected.has(f.fact_code))}
                    onCheckedChange={(v) =>
                      setSelected(
                        v === true
                          ? new Set(shown.map((f) => f.fact_code))
                          : new Set(),
                      )
                    }
                  />
                </TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Fact</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Expiry</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((f) => (
                <TableRow key={f.fact_code}>
                  <TableCell>
                    <Checkbox
                      aria-label={`Select ${f.fact_code}`}
                      checked={selected.has(f.fact_code)}
                      onCheckedChange={() =>
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (next.has(f.fact_code)) next.delete(f.fact_code);
                          else next.add(f.fact_code);
                          return next;
                        })
                      }
                    />
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {f.fact_code}
                  </TableCell>
                  <TableCell className="max-w-md whitespace-normal">
                    <span className="font-medium">{f.entity}</span>
                    <span className="text-muted-foreground">
                      {" "}
                      · {f.attribute}
                    </span>
                    <p className="text-sm">{f.statement}</p>
                    {f.source && (
                      <p className="text-muted-foreground text-xs">
                        Source: {f.source}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    {f.value} {f.unit}
                  </TableCell>
                  <TableCell>
                    <ExpiryBadge expiry={f.expiry} validUntil={f.valid_until} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={f.status} />
                  </TableCell>
                  <TableCell>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Edit ${f.fact_code}`}
                      onClick={() => setDialog({ open: true, fact: f })}
                    >
                      <Pencil aria-hidden />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <FactDialog
        brandId={me.brand_id}
        open={dialog.open}
        fact={dialog.fact}
        onClose={() => setDialog({ open: false, fact: null })}
        onSaved={(fact) => {
          upsert([fact]);
          setDialog({ open: false, fact: null });
          setNotice(`${fact.fact_code} saved.`);
        }}
      />
    </div>
  );
}

export default function AdminFactsPage() {
  return (
    <RoleGate roles={["admin"]}>{(me) => <FactsWorkspace me={me} />}</RoleGate>
  );
}
