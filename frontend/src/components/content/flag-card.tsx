"use client";

import { Bot, Check, Code2, Pencil, ShieldCheck, X } from "lucide-react";
import { useState } from "react";

import { FlagStatusBadge, SeverityBadge } from "@/components/content/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { StoredFlag } from "@/types/api";

export type FlagAction =
  | { kind: "accept" }
  | { kind: "edit"; text: string }
  | { kind: "dismiss"; reason: string }
  | { kind: "except"; reason: string };

/** Coloured left edge by severity (the severity is also written on the card). */
const SEVERITY_EDGE = {
  high: "border-l-red-500",
  medium: "border-l-amber-500",
  low: "border-l-sky-500",
} as const;

const SOURCE_LABEL = { rule: "Rule", fact: "Fact", policy: "Policy" } as const;

export function SourceChip({ flag }: { flag: StoredFlag }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="bg-muted focus-visible:ring-ring rounded-md border px-2 py-0.5 font-mono text-xs focus-visible:ring-2 focus-visible:outline-none"
          aria-label={`${SOURCE_LABEL[flag.source_type]} ${flag.source_id}: ${flag.source_text ?? ""}`}
        >
          {flag.source_id}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="font-medium">
          {SOURCE_LABEL[flag.source_type]} {flag.source_id}
        </p>
        <p>{flag.source_text ?? "Source text unavailable."}</p>
      </TooltipContent>
    </Tooltip>
  );
}

export function FlagCard({
  flag,
  mode,
  selected,
  busy,
  onSelect,
  onAction,
  canFix = true,
  aiLabel,
  picked,
  onPick,
  stagedEdit,
  onStageEdit,
  index = 0,
}: {
  flag: StoredFlag;
  mode: "creator" | "manager" | "readonly";
  /** False for PDFs and images: fixes are made by uploading a corrected file. */
  canFix?: boolean;
  /** Which provider and model produced this flag (from the AI call log). */
  aiLabel?: string;
  /** Chosen for the fix round ("Accept fix" pressed); toggles only when onPick is given. */
  picked?: boolean;
  onPick?: (on: boolean) => void;
  /** The creator's own wording for this flag in the fix round, if any. */
  stagedEdit?: string;
  onStageEdit?: (text: string | null) => void;
  /** Position in the list, used to stagger the entrance animation. */
  index?: number;
  selected: boolean;
  busy: boolean;
  onSelect: () => void;
  onAction: (action: FlagAction) => void;
}) {
  const [panel, setPanel] = useState<"edit" | "dismiss" | "except" | null>(
    null,
  );
  const [text, setText] = useState(flag.suggested_fix ?? flag.evidence);
  const [reason, setReason] = useState("");
  const open = flag.status === "open";
  const fromAI = flag.layer !== "rules";

  return (
    <article
      id={`flag-${flag.id}`}
      aria-label={`${flag.severity} ${flag.category} flag, ${flag.source_id}`}
      onClick={onSelect}
      style={{ animationDelay: `${Math.min(index, 12) * 40}ms` }}
      className={cn(
        "bg-card hd-rise hd-lift scroll-mt-4 space-y-2 rounded-xl border border-l-4 p-3 text-sm",
        SEVERITY_EDGE[flag.severity],
        selected && "ring-ring hd-pulse ring-2",
        !open && "bg-muted/40",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={flag.severity} />
        <Badge variant="secondary" className="capitalize">
          {flag.category}
        </Badge>
        <SourceChip flag={flag} />
        <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
          {fromAI ? (
            <Bot className="size-3.5" aria-hidden />
          ) : (
            <Code2 className="size-3.5" aria-hidden />
          )}
          {fromAI
            ? `AI used${aiLabel ? `: ${aiLabel}` : ""}`
            : "Checked in code"}
        </span>
        {!open && <FlagStatusBadge status={flag.status} />}
      </div>
      {flag.evidence ? (
        <blockquote className="border-l-2 pl-2 italic">
          “{flag.evidence}”
        </blockquote>
      ) : (
        <p className="text-muted-foreground italic">Missing from the content</p>
      )}
      <p>{flag.explanation}</p>
      {flag.suggested_fix && (
        <p>
          <span className="font-medium">Suggested fix: </span>
          {flag.suggested_fix}
        </p>
      )}
      {flag.resolution_note && (
        <p className="text-muted-foreground">
          <span className="font-medium">Reason: </span>
          {flag.resolution_note}
        </p>
      )}

      {mode === "creator" && open && (
        <div
          className="flex flex-wrap gap-2 pt-1"
          onClick={(e) => e.stopPropagation()}
        >
          {canFix &&
            flag.suggested_fix &&
            onPick &&
            stagedEdit === undefined && (
              <Button
                size="sm"
                variant={picked ? "default" : "outline"}
                aria-pressed={picked ?? false}
                disabled={busy}
                onClick={() => onPick(!picked)}
              >
                <Check aria-hidden />
                {picked ? "Fix chosen" : "Accept fix"}
              </Button>
            )}
          {canFix && onStageEdit && (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setPanel(panel === "edit" ? null : "edit")}
            >
              <Pencil aria-hidden />{" "}
              {stagedEdit === undefined ? "Edit wording" : "Change wording"}
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => setPanel(panel === "dismiss" ? null : "dismiss")}
          >
            <X aria-hidden /> Dismiss
          </Button>
        </div>
      )}
      {mode === "manager" &&
        (open || flag.status === "dismissed") &&
        flag.evidence && (
          <div className="pt-1" onClick={(e) => e.stopPropagation()}>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setPanel(panel === "except" ? null : "except")}
            >
              <ShieldCheck aria-hidden /> Approve exception
            </Button>
          </div>
        )}

      {stagedEdit !== undefined && panel !== "edit" && (
        <p
          className="rounded-md bg-amber-50 p-2"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="font-medium">Your wording: </span>“{stagedEdit}”{" "}
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => onStageEdit?.(null)}
          >
            Remove
          </button>
        </p>
      )}
      {panel === "edit" && (
        <form
          className="space-y-2"
          onClick={(e) => e.stopPropagation()}
          onSubmit={(e) => {
            e.preventDefault();
            if (onStageEdit) onStageEdit(text);
            else onAction({ kind: "edit", text });
            setPanel(null);
          }}
        >
          <Label htmlFor={`edit-${flag.id}`}>
            Replace “{flag.evidence || "(insert)"}” with
          </Label>
          <Input
            id={`edit-${flag.id}`}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Button size="sm" type="submit" disabled={busy}>
            Use this wording
          </Button>
        </form>
      )}
      {(panel === "dismiss" || panel === "except") && (
        <form
          className="space-y-2"
          onClick={(e) => e.stopPropagation()}
          onSubmit={(e) => {
            e.preventDefault();
            onAction({ kind: panel, reason });
            setPanel(null);
            setReason("");
          }}
        >
          <Label htmlFor={`reason-${flag.id}`}>
            {panel === "dismiss"
              ? "Why is this flag wrong or acceptable?"
              : "Why is this an approved exception?"}{" "}
            (required)
          </Label>
          <Textarea
            id={`reason-${flag.id}`}
            rows={2}
            required
            minLength={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            size="sm"
            type="submit"
            disabled={busy || reason.trim().length < 3}
          >
            {panel === "dismiss" ? "Dismiss flag" : "Approve exception"}
          </Button>
        </form>
      )}
    </article>
  );
}
