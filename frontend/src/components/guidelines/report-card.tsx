"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  HelpCircle,
  Layers,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollPanel } from "@/components/ui/scroll-panel";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { PairIssue, VerificationReport } from "@/types/api";

function RuleLink({ code }: { code: string }) {
  return (
    <a
      href={`#rule-${code}`}
      onClick={(e) => {
        // Scroll the rules list (its own scroll panel) to the rule and flash it.
        const el = document.getElementById(`rule-${code}`);
        if (!el) return;
        e.preventDefault();
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.remove("hd-pulse");
        void el.offsetWidth;
        el.classList.add("hd-pulse");
      }}
      className="focus-visible:ring-ring text-primary rounded font-mono text-sm font-medium underline underline-offset-2 focus-visible:ring-2 focus-visible:outline-none"
    >
      {code}
    </a>
  );
}

function PairList({
  items,
  empty,
  label,
}: {
  items: PairIssue[];
  empty: string;
  label: string;
}) {
  if (!items.length)
    return <p className="text-muted-foreground text-sm">{empty}</p>;
  return (
    <ScrollPanel label={label} surface="var(--card)" className="max-h-72 pr-2">
      <ul className="space-y-2">
        {items.map((p) => (
          <li key={`${p.rule_a}-${p.rule_b}`} className="text-sm">
            <RuleLink code={p.rule_a} /> and <RuleLink code={p.rule_b} />
            <span className="text-muted-foreground">
              {" "}
              · similarity {p.similarity.toFixed(2)}
            </span>
            <p className="text-muted-foreground mt-0.5">{p.explanation}</p>
          </li>
        ))}
      </ul>
    </ScrollPanel>
  );
}

export function ReportCard({
  report,
  onUseRewrite,
}: {
  report: VerificationReport;
  onUseRewrite: (code: string, text: string) => void;
}) {
  const problems =
    report.duplicates.length +
    report.contradictions.length +
    report.vague.length +
    report.missing_categories.length;
  return (
    <Card className="hd-rise">
      <CardHeader>
        <CardTitle>
          <h2 className="flex items-center gap-2">
            {problems ? (
              <AlertTriangle className="size-5 text-amber-600" aria-hidden />
            ) : (
              <CheckCircle2 className="size-5 text-green-700" aria-hidden />
            )}
            Verification report
          </h2>
        </CardTitle>
        <CardDescription>
          {problems
            ? `${problems} issue${problems === 1 ? "" : "s"} to review`
            : "No issues found"}{" "}
          · {report.rules_checked} rules and {report.pairs_checked} similar
          pairs checked. Fix issues by editing or rejecting rules, then re-run
          the check.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        <section aria-labelledby="dup-h">
          <h3 id="dup-h" className="mb-2 flex items-center gap-2 font-medium">
            <Copy className="size-4" aria-hidden /> Duplicates (
            {report.duplicates.length})
          </h3>
          <PairList
            items={report.duplicates}
            empty="No duplicate rules."
            label="Duplicate rules"
          />
        </section>
        <section aria-labelledby="con-h">
          <h3 id="con-h" className="mb-2 flex items-center gap-2 font-medium">
            <AlertTriangle className="size-4" aria-hidden /> Contradictions (
            {report.contradictions.length})
          </h3>
          <PairList
            items={report.contradictions}
            empty="No contradicting rules."
            label="Contradicting rules"
          />
        </section>
        <section aria-labelledby="vague-h">
          <h3 id="vague-h" className="mb-2 flex items-center gap-2 font-medium">
            <HelpCircle className="size-4" aria-hidden /> Vague rules (
            {report.vague.length})
          </h3>
          {report.vague.length ? (
            <ScrollPanel
              label="Vague rules"
              surface="var(--card)"
              className="max-h-80 pr-2"
            >
              <ul className="space-y-3">
                {report.vague.map((v) => (
                  <li key={v.rule_code} className="text-sm">
                    <RuleLink code={v.rule_code} />
                    <span className="text-muted-foreground"> · {v.reason}</span>
                    {v.suggested_rewrite && (
                      <div className="bg-muted mt-1 rounded-md p-2">
                        <p>
                          <span className="font-medium">Suggested: </span>
                          {v.suggested_rewrite}
                        </p>
                        <Button
                          size="sm"
                          variant="outline"
                          className="mt-2"
                          onClick={() =>
                            onUseRewrite(v.rule_code, v.suggested_rewrite!)
                          }
                        >
                          Use this rewrite
                        </Button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </ScrollPanel>
          ) : (
            <p className="text-muted-foreground text-sm">
              Every rule is testable.
            </p>
          )}
        </section>
        <section aria-labelledby="miss-h">
          <h3 id="miss-h" className="mb-2 flex items-center gap-2 font-medium">
            <Layers className="size-4" aria-hidden /> Missing categories (
            {report.missing_categories.length})
          </h3>
          {report.missing_categories.length ? (
            <div className="flex flex-wrap gap-2">
              {report.missing_categories.map((c) => (
                <Badge key={c} variant="outline">
                  {c}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              Every required category has rules.
            </p>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
