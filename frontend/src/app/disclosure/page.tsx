"use client";

import { Bot, Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import type { Disclosure } from "@/types/api";

const PURPOSE: Record<string, string> = {
  judge: "Checking content against guidelines",
  claim_extraction: "Finding claims",
  claim_verification: "Checking claims against facts",
  visual_check: "Checking images",
  rule_extraction: "Reading guidelines",
  pair_check: "Finding duplicate or contradicting rules",
  vagueness_check: "Finding vague rules",
  rule_embedding: "Indexing rules",
  fact_embedding: "Indexing facts",
  unit_embedding: "Matching content to rules",
  claim_embedding: "Matching claims to facts",
  help: "Answering questions in the help assistant",
};

function DisclosureView() {
  const [data, setData] = useState<Disclosure | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Disclosure>("/disclosure")
      .then(setData)
      .catch((e) =>
        setError(
          e instanceof ApiError ? e.message : "Could not load the disclosure",
        ),
      );
  }, []);

  if (error)
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  if (!data)
    return (
      <p
        className="text-muted-foreground flex items-center gap-2"
        role="status"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
      </p>
    );

  return (
    <div className="space-y-8">
      <PageHeader
        title="AI disclosure"
        description="Which AI services Heimdall uses, what they receive, and what is removed first. AI advises; people decide."
      />
      <section aria-labelledby="how-h" className="space-y-2">
        <h2 id="how-h" className="text-xl font-semibold">
          How AI is used
        </h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Banned words and required phrases are checked in code. No AI is
            involved, and those flags say “Checked in code”.
          </li>
          <li>
            Guideline checks, claim checks and image checks use AI. Those flags
            say “AI used” and name the model.
          </li>
          <li>
            Every AI flag must cite a rule, a fact or the claim policy it was
            given, and quote words that really appear in the content. Plain code
            drops any flag that does not.
          </li>
          <li>
            Nothing is published or blocked automatically. Creators and managers
            decide, and every dismissal keeps its reason.
          </li>
          <li>
            Models are tried in this order: {data.provider_order.join(" → ")}.
            If one is busy or unavailable, the next one is used.
          </li>
        </ul>
      </section>

      <section aria-labelledby="redact-h" className="space-y-2">
        <h2
          id="redact-h"
          className="flex items-center gap-2 text-xl font-semibold"
        >
          <ShieldCheck className="size-5" aria-hidden /> Removed before any AI
          call
        </h2>
        <div className="flex flex-wrap gap-2">
          {data.redaction.map((r) => (
            <Badge key={r} variant="outline">
              {r}
            </Badge>
          ))}
        </div>
        <p className="text-muted-foreground text-sm">
          Name and place detection is{" "}
          {data.presidio_active
            ? "on"
            : "off (Presidio is not installed on this server)"}
          . Masked values are replaced with labels such as [EMAIL]; only the
          text being checked is sent, never the whole document at once.
        </p>
      </section>

      <section aria-labelledby="svc-h" className="space-y-3">
        <h2 id="svc-h" className="text-xl font-semibold">
          Services
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          {data.services.map((s) => (
            <Card key={s.name}>
              <CardHeader>
                <CardTitle>
                  <h3 className="flex items-center gap-2">
                    <Bot className="size-4" aria-hidden /> {s.name}
                    {!s.configured && (
                      <Badge variant="outline">not configured</Badge>
                    )}
                  </h3>
                </CardTitle>
                <CardDescription>{s.role}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {s.models.length > 0 && (
                  <p>
                    <span className="font-medium">Models: </span>
                    {s.models.filter(Boolean).join(", ")}
                  </p>
                )}
                <p>
                  <span className="font-medium">Receives: </span>
                  {s.data_sent}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section aria-labelledby="usage-h" className="space-y-3">
        <h2 id="usage-h" className="text-xl font-semibold">
          AI calls for your brand, last 30 days
        </h2>
        {data.usage_last_30_days.length === 0 ? (
          <p className="text-muted-foreground">No AI calls yet.</p>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>What for</TableHead>
                  <TableHead>Provider and model</TableHead>
                  <TableHead>Calls</TableHead>
                  <TableHead>From cache</TableHead>
                  <TableHead>Failed</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.usage_last_30_days.map((u) => (
                  <TableRow key={`${u.provider}-${u.model}-${u.purpose}`}>
                    <TableCell>{PURPOSE[u.purpose] ?? u.purpose}</TableCell>
                    <TableCell>
                      {u.provider} {u.model}
                    </TableCell>
                    <TableCell>{u.calls}</TableCell>
                    <TableCell>{u.cached}</TableCell>
                    <TableCell>{u.failed}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  );
}

export default function DisclosurePage() {
  return (
    <RoleGate roles={["admin", "creator", "manager"]}>
      {() => <DisclosureView />}
    </RoleGate>
  );
}
