"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { Fact, FactInput } from "@/types/api";

const EMPTY: FactInput = {
  entity: "",
  attribute: "",
  value: "",
  unit: "",
  statement: "",
  source: "",
  valid_until: "",
};

/** Add a fact (fact = null, open = true) or edit one. */
export function FactDialog({
  brandId,
  open,
  fact,
  onClose,
  onSaved,
}: {
  brandId: string;
  open: boolean;
  fact: Fact | null;
  onClose: () => void;
  onSaved: (fact: Fact) => void;
}) {
  const [form, setForm] = useState<FactInput>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    setForm(
      fact
        ? {
            entity: fact.entity,
            attribute: fact.attribute,
            value: fact.value,
            unit: fact.unit ?? "",
            statement: fact.statement,
            source: fact.source ?? "",
            valid_until: fact.valid_until ?? "",
          }
        : EMPTY,
    );
  }, [fact, open]);

  const set =
    (key: keyof FactInput) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      ...form,
      unit: form.unit || null,
      source: form.source || null,
      valid_until: form.valid_until || null,
    };
    try {
      const saved = fact
        ? await api<Fact>(`/brands/${brandId}/facts/${fact.fact_code}`, {
            method: "PATCH",
            json: body,
          })
        : await api<Fact>(`/brands/${brandId}/facts`, { json: body });
      onSaved(saved);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the fact");
    } finally {
      setBusy(false);
    }
  }

  const field = (
    key: keyof FactInput,
    label: string,
    props: React.ComponentProps<"input"> = {},
  ) => (
    <div className="space-y-1.5">
      <Label htmlFor={`fact-${key}`}>{label}</Label>
      <Input
        id={`fact-${key}`}
        value={form[key] ?? ""}
        onChange={set(key)}
        {...props}
      />
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={save}>
          <DialogHeader>
            <DialogTitle>
              {fact ? `Edit ${fact.fact_code}` : "Add a fact"}
            </DialogTitle>
            <DialogDescription>
              {fact
                ? "The fact keeps its code, so content that cites it stays linked."
                : "Facts you add here are approved straight away."}
            </DialogDescription>
          </DialogHeader>
          <div className="my-4 grid gap-3 sm:grid-cols-2">
            {field("entity", "Entity (product, plan or company)", {
              required: true,
            })}
            {field("attribute", "Attribute (e.g. monthly price)", {
              required: true,
            })}
            {field("value", "Value", { required: true })}
            {field("unit", "Unit (optional)")}
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="fact-statement">
                Statement (one plain sentence)
              </Label>
              <Textarea
                id="fact-statement"
                required
                rows={2}
                value={form.statement}
                onChange={set("statement")}
              />
            </div>
            {field("source", "Source (optional)")}
            {field("valid_until", "Valid until (optional)", { type: "date" })}
          </div>
          {error && (
            <Alert variant="destructive" role="alert" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="animate-spin" aria-hidden />} Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
