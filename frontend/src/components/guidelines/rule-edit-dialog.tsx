"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { Rule } from "@/types/api";
import { CATEGORIES, type Category } from "@/types/flag";

export function RuleEditDialog({
  rule,
  onClose,
  onSaved,
}: {
  rule: Rule | null;
  onClose: () => void;
  onSaved: (rule: Rule) => void;
}) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState<Category>("other");
  const [alwaysOn, setAlwaysOn] = useState(false);
  const [terms, setTerms] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!rule) return;
    setText(rule.text);
    setCategory(rule.category);
    setAlwaysOn(rule.always_on);
    setTerms(rule.terms.join(", "));
    setError(null);
  }, [rule]);

  async function save() {
    if (!rule) return;
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { text, category, always_on: alwaysOn };
      if (rule.check_type === "deterministic") {
        body.terms = terms
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
      }
      onSaved(await api<Rule>(`/rules/${rule.rule_code}`, { method: "PATCH", json: body }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the rule");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={!!rule} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {rule?.rule_code}</DialogTitle>
          <DialogDescription>
            Changing the text re-embeds the rule. A deterministic rule with no terms becomes
            semantic.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="rule-text">Rule</Label>
            <Textarea id="rule-text" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="rule-category">Category</Label>
            <Select value={category} onValueChange={(v) => setCategory(v as Category)}>
              <SelectTrigger id="rule-category" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {rule?.check_type === "deterministic" && (
            <div className="space-y-2">
              <Label htmlFor="rule-terms">
                {rule.det_kind === "banned_terms" ? "Banned terms" : "Required phrase"} (comma
                separated)
              </Label>
              <Input id="rule-terms" value={terms} onChange={(e) => setTerms(e.target.value)} />
            </div>
          )}
          <div className="flex items-center gap-2">
            <Checkbox
              id="rule-always-on"
              checked={alwaysOn}
              onCheckedChange={(v) => setAlwaysOn(v === true)}
            />
            <Label htmlFor="rule-always-on">Always check this rule (not only when retrieved)</Label>
          </div>
          {error && (
            <Alert variant="destructive" role="alert">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy || !text.trim()}>
            {busy && <Loader2 className="animate-spin" aria-hidden />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
