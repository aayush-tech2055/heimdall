"use client";

import { Check, Pencil, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { Rule, RuleStatus } from "@/types/api";
import { CATEGORIES } from "@/types/flag";

const STATUS_STYLE: Record<RuleStatus, string> = {
  pending: "bg-amber-100 text-amber-900 border-amber-300",
  approved: "bg-green-100 text-green-900 border-green-300",
  rejected: "bg-neutral-100 text-neutral-700 border-neutral-300",
};

export function StatusBadge({ status }: { status: RuleStatus }) {
  return (
    <Badge variant="outline" className={STATUS_STYLE[status]}>
      {status}
    </Badge>
  );
}

export function RuleList({
  rules,
  selected,
  highlighted,
  onToggle,
  onToggleAll,
  onEdit,
  onSetStatus,
}: {
  rules: Rule[];
  selected: Set<string>;
  highlighted: Set<string>;
  onToggle: (code: string) => void;
  onToggleAll: (codes: string[], on: boolean) => void;
  onEdit: (rule: Rule) => void;
  onSetStatus: (codes: string[], action: "approve" | "reject") => void;
}) {
  if (!rules.length) {
    return <p className="text-muted-foreground">No rules here yet.</p>;
  }
  const allSelected = rules.every((r) => selected.has(r.rule_code));
  return (
    <div className="space-y-8">
      <div className="flex items-center gap-2">
        <Checkbox
          id="select-all"
          checked={allSelected}
          onCheckedChange={(v) =>
            onToggleAll(
              rules.map((r) => r.rule_code),
              v === true,
            )
          }
        />
        <label htmlFor="select-all" className="text-sm">
          Select all {rules.length} shown
        </label>
      </div>
      {CATEGORIES.filter((c) => rules.some((r) => r.category === c)).map(
        (category) => (
          <section key={category} aria-labelledby={`cat-${category}`}>
            <h3
              id={`cat-${category}`}
              className="mb-2 text-lg font-semibold capitalize"
            >
              {category}
            </h3>
            <ul className="divide-y rounded-lg border">
              {rules
                .filter((r) => r.category === category)
                .map((rule) => (
                  <li
                    key={rule.rule_code}
                    id={`rule-${rule.rule_code}`}
                    className={cn(
                      "flex scroll-mt-24 gap-3 p-3",
                      highlighted.has(rule.rule_code) && "bg-amber-50",
                      rule.status === "rejected" && "bg-muted/40",
                    )}
                  >
                    <Checkbox
                      className="mt-1"
                      aria-label={`Select ${rule.rule_code}`}
                      checked={selected.has(rule.rule_code)}
                      onCheckedChange={() => onToggle(rule.rule_code)}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-semibold">
                          {rule.rule_code}
                        </span>
                        <StatusBadge status={rule.status} />
                        <Badge variant="secondary">
                          {rule.check_type === "deterministic"
                            ? rule.det_kind === "banned_terms"
                              ? "banned words · checked in code"
                              : "required phrase · checked in code"
                            : "checked by AI"}
                        </Badge>
                        {rule.always_on && (
                          <Badge variant="outline">always on</Badge>
                        )}
                        <span className="text-muted-foreground text-xs">
                          {rule.source_doc}
                          {rule.source_page ? `, page ${rule.source_page}` : ""}
                        </span>
                      </div>
                      <p className="mt-1">{rule.text}</p>
                      {rule.terms.length > 0 && (
                        <p className="text-muted-foreground mt-1 text-sm">
                          Terms: {rule.terms.map((t) => `“${t}”`).join(", ")}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-start gap-1">
                      {rule.status !== "approved" && (
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Approve ${rule.rule_code}`}
                          onClick={() =>
                            onSetStatus([rule.rule_code], "approve")
                          }
                        >
                          <Check aria-hidden />
                        </Button>
                      )}
                      {rule.status !== "rejected" && (
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Reject ${rule.rule_code}`}
                          onClick={() =>
                            onSetStatus([rule.rule_code], "reject")
                          }
                        >
                          <X aria-hidden />
                        </Button>
                      )}
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Edit ${rule.rule_code}`}
                        onClick={() => onEdit(rule)}
                      >
                        <Pencil aria-hidden />
                      </Button>
                    </div>
                  </li>
                ))}
            </ul>
          </section>
        ),
      )}
    </div>
  );
}
