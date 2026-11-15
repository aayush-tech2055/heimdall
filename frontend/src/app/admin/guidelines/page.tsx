"use client";

import { CheckCheck, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { ReportCard } from "@/components/guidelines/report-card";
import { RuleEditDialog } from "@/components/guidelines/rule-edit-dialog";
import { RuleList } from "@/components/guidelines/rule-list";
import { UploadCard } from "@/components/guidelines/upload-card";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { api, ApiError } from "@/lib/api";
import type { Me, Rule, RuleStatus, VerificationReport } from "@/types/api";

type Filter = "all" | RuleStatus;

function GuidelinesWorkspace({ me }: { me: Me }) {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [filter, setFilter] = useState<Filter>("pending");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<Rule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, rep] = await Promise.all([
        api<Rule[]>(`/brands/${me.brand_id}/rules`),
        api<VerificationReport | null>(
          `/brands/${me.brand_id}/guidelines/report`,
        ),
      ]);
      setRules(r);
      setReport(rep);
      if (!r.some((x) => x.status === "pending")) setFilter("all");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load rules");
    }
  }, [me.brand_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = useMemo(
    () => (rules ?? []).filter((r) => filter === "all" || r.status === filter),
    [rules, filter],
  );
  const highlighted = useMemo(() => {
    const codes = new Set<string>();
    report?.duplicates.forEach(
      (p) => (codes.add(p.rule_a), codes.add(p.rule_b)),
    );
    report?.contradictions.forEach(
      (p) => (codes.add(p.rule_a), codes.add(p.rule_b)),
    );
    report?.vague.forEach((v) => codes.add(v.rule_code));
    return codes;
  }, [report]);

  function replace(updated: Rule[]) {
    const byCode = new Map(updated.map((r) => [r.rule_code, r]));
    setRules((prev) => (prev ?? []).map((r) => byCode.get(r.rule_code) ?? r));
  }

  async function setStatus(codes: string[], action: "approve" | "reject") {
    setError(null);
    try {
      replace(await api<Rule[]>("/rules/approve", { json: { codes, action } }));
      setSelected(new Set());
      setNotice(
        `${codes.length} rule${codes.length === 1 ? "" : "s"} ${action}d.`,
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update rules");
    }
  }

  async function useRewrite(code: string, text: string) {
    try {
      replace([
        await api<Rule>(`/rules/${code}`, { method: "PATCH", json: { text } }),
      ]);
      setNotice(`${code} rewritten. Re-run the check to update the report.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update the rule");
    }
  }

  async function recheck() {
    setRechecking(true);
    setError(null);
    try {
      setReport(
        await api<VerificationReport>(
          `/brands/${me.brand_id}/guidelines/verify`,
          { method: "POST" },
        ),
      );
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not re-run the check",
      );
    } finally {
      setRechecking(false);
    }
  }

  const pendingCodes = (rules ?? [])
    .filter((r) => r.status === "pending")
    .map((r) => r.rule_code);
  const pendingWithIssues = pendingCodes.filter((c) => highlighted.has(c));
  const allShownSelected =
    shown.length > 0 && shown.every((r) => selected.has(r.rule_code));

  function approveAllPending() {
    if (pendingWithIssues.length && !confirmAll) {
      setConfirmAll(true);
      return;
    }
    setConfirmAll(false);
    void setStatus(pendingCodes, "approve");
  }

  const counts = (s: Filter) =>
    (rules ?? []).filter((r) => s === "all" || r.status === s).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Guidelines"
        description={`Turn ${me.brand_name}'s brand guideline into rules that every piece of content is checked against.`}
      />
      <UploadCard
        brandId={me.brand_id}
        onDone={(result) => {
          setRules((prev) => [...(prev ?? []), ...result.rules]);
          setReport(result.report);
          setFilter("pending");
          setNotice(
            `Extracted ${result.rules.length} rules from ${result.pages} page${result.pages === 1 ? "" : "s"} of ${result.source_doc}. Review them below.`,
          );
        }}
      />
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
      {report && <ReportCard report={report} onUseRewrite={useRewrite} />}

      <section aria-labelledby="rules-h" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="rules-h" className="text-xl font-semibold">
            Rules
          </h2>
          <Button
            variant="outline"
            onClick={recheck}
            disabled={rechecking || !rules?.length}
          >
            {rechecking ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <RefreshCw aria-hidden />
            )}
            Re-run verification
          </Button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <FilterTabs
            label="Filter rules by status"
            value={filter}
            onChange={setFilter}
            options={(
              ["pending", "approved", "rejected", "all"] as Filter[]
            ).map((f) => ({
              value: f,
              label: `${f[0].toUpperCase()}${f.slice(1)} (${counts(f)})`,
            }))}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={!shown.length}
              aria-pressed={allShownSelected}
              onClick={() =>
                setSelected(
                  allShownSelected
                    ? new Set()
                    : new Set(shown.map((r) => r.rule_code)),
                )
              }
            >
              {allShownSelected
                ? "Clear selection"
                : `Select all shown (${shown.length})`}
            </Button>
            <Button
              variant="outline"
              disabled={!selected.size}
              onClick={() => setStatus([...selected], "approve")}
            >
              Approve selected ({selected.size})
            </Button>
            <Button
              variant="outline"
              disabled={!selected.size}
              onClick={() => setStatus([...selected], "reject")}
            >
              Reject selected
            </Button>
            <Button disabled={!pendingCodes.length} onClick={approveAllPending}>
              <CheckCheck aria-hidden /> Approve all pending (
              {pendingCodes.length})
            </Button>
          </div>
        </div>
        {confirmAll && (
          <Alert role="alert">
            <AlertDescription className="space-y-2">
              <p>
                {pendingWithIssues.length} of the {pendingCodes.length} pending
                rules have issues in the verification report (
                {pendingWithIssues.join(", ")}): duplicates, contradictions or
                vague wording. Approve all of them anyway?
              </p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={approveAllPending}>
                  Approve all {pendingCodes.length}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setConfirmAll(false);
                    void setStatus(
                      pendingCodes.filter((c) => !highlighted.has(c)),
                      "approve",
                    );
                  }}
                  disabled={pendingWithIssues.length === pendingCodes.length}
                >
                  Approve only the{" "}
                  {pendingCodes.length - pendingWithIssues.length} without
                  issues
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setConfirmAll(false)}
                >
                  Cancel
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}
        {rules === null ? (
          <p
            className="text-muted-foreground flex items-center gap-2"
            role="status"
          >
            <Loader2 className="size-4 animate-spin" aria-hidden /> Loading
            rules…
          </p>
        ) : (
          <RuleList
            rules={shown}
            selected={selected}
            highlighted={highlighted}
            onToggle={(code) =>
              setSelected((prev) => {
                const next = new Set(prev);
                if (next.has(code)) next.delete(code);
                else next.add(code);
                return next;
              })
            }
            onToggleAll={(codes, on) =>
              setSelected((prev) => {
                const next = new Set(prev);
                codes.forEach((c) => (on ? next.add(c) : next.delete(c)));
                return next;
              })
            }
            onEdit={setEditing}
            onSetStatus={setStatus}
          />
        )}
      </section>
      <RuleEditDialog
        rule={editing}
        onClose={() => setEditing(null)}
        onSaved={(rule) => {
          replace([rule]);
          setEditing(null);
          setNotice(`${rule.rule_code} saved.`);
        }}
      />
    </div>
  );
}

export default function AdminGuidelinesPage() {
  return (
    <RoleGate roles={["admin"]}>
      {(me) => <GuidelinesWorkspace me={me} />}
    </RoleGate>
  );
}
