"use client";

import { Loader2, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import type { BrandSettings, Me } from "@/types/api";

function SettingsForm({ me }: { me: Me }) {
  const [settings, setSettings] = useState<BrandSettings | null>(null);
  const [term, setTerm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const url = `/brands/${me.brand_id}/settings`;

  useEffect(() => {
    api<BrandSettings>(url)
      .then(setSettings)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load settings"),
      );
  }, [url]);

  if (!settings)
    return error ? (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    ) : (
      <p
        className="text-muted-foreground flex items-center gap-2"
        role="status"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
      </p>
    );

  const update = (patch: Partial<BrandSettings>) =>
    setSettings({ ...settings, ...patch });

  function addTerm(event: React.FormEvent) {
    event.preventDefault();
    const t = term.trim();
    if (
      !t ||
      settings!.confidential_terms.some(
        (x) => x.toLowerCase() === t.toLowerCase(),
      )
    )
      return;
    update({ confidential_terms: [...settings!.confidential_terms, t] });
    setTerm("");
  }

  async function save() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setSettings(
        await api<BrandSettings>(url, {
          method: "PUT",
          json: {
            confidential_terms: settings!.confidential_terms,
            claim_policy_enabled: settings!.claim_policy_enabled,
            readability_target: settings!.readability_target,
          },
        }),
      );
      setNotice("Settings saved. They apply to the next check.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader
        title="Brand settings"
        description={`Privacy and checking options for ${me.brand_name}.`}
      />

      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Confidential terms</h2>
          </CardTitle>
          <CardDescription>
            Words that must never reach an AI service (code names, unreleased
            products, partner names). They are replaced with [CONFIDENTIAL]
            before any AI call. Emails, phone numbers, PAN, Aadhaar and card
            numbers are always masked
            {settings.presidio_available ? ", and so are names and places" : ""}
            .
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {settings.confidential_terms.length === 0 && (
              <p className="text-muted-foreground text-sm">
                No confidential terms yet.
              </p>
            )}
            {settings.confidential_terms.map((t) => (
              <Badge key={t} variant="secondary" className="gap-1 pr-1">
                {t}
                <button
                  type="button"
                  aria-label={`Remove ${t}`}
                  className="hover:bg-muted rounded p-0.5"
                  onClick={() =>
                    update({
                      confidential_terms: settings.confidential_terms.filter(
                        (x) => x !== t,
                      ),
                    })
                  }
                >
                  <X className="size-3" aria-hidden />
                </button>
              </Badge>
            ))}
          </div>
          <form onSubmit={addTerm} className="flex gap-2">
            <Label htmlFor="new-term" className="sr-only">
              New confidential term
            </Label>
            <Input
              id="new-term"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="e.g. Project Falcon"
            />
            <Button type="submit" variant="outline">
              <Plus aria-hidden /> Add
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Claim policy</h2>
          </CardTitle>
          <CardDescription>
            A built-in rule that every flag about an unsupported claim cites.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-md border p-3">
            <p className="font-mono text-sm font-semibold">
              {settings.claim_policy_id}
            </p>
            <p>{settings.claim_policy_text}</p>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="claim-policy"
              checked={settings.claim_policy_enabled}
              onCheckedChange={(v) =>
                update({ claim_policy_enabled: v === true })
              }
            />
            <Label htmlFor="claim-policy">
              Flag claims that no approved fact supports (contradicted and
              outdated claims are always flagged)
            </Label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Readability target</h2>
          </CardTitle>
          <CardDescription>
            Flesch reading ease, 0 to 100 (60 is plain English; higher is
            easier). Paragraphs below it are flagged under your readability
            rule. Leave empty to turn the check off.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Label htmlFor="readability">Minimum reading ease</Label>
          <Input
            id="readability"
            type="number"
            min={0}
            max={100}
            className="mt-2 w-32"
            value={settings.readability_target ?? ""}
            onChange={(e) =>
              update({
                readability_target:
                  e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
        </CardContent>
      </Card>

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
      <Button onClick={save} disabled={busy}>
        {busy && <Loader2 className="animate-spin" aria-hidden />} Save settings
      </Button>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RoleGate roles={["admin"]}>{(me) => <SettingsForm me={me} />}</RoleGate>
  );
}
