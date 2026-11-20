"use client";

import {
  CheckCheck,
  CheckCircle2,
  Loader2,
  Mail,
  RefreshCw,
  RotateCcw,
  Send,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ContentStatusBadge } from "@/components/content/badges";
import { CommentsPanel } from "@/components/content/comments-panel";
import { FlagCard, type FlagAction } from "@/components/content/flag-card";
import {
  ImageViewer,
  PdfViewer,
  VideoViewer,
} from "@/components/content/file-viewers";
import { HighlightedText } from "@/components/content/highlighted-text";
import { SubmitDialog } from "@/components/content/submit-dialog";
import { VersionHistory } from "@/components/content/version-history";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollPanel } from "@/components/ui/scroll-panel";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useContent } from "@/lib/use-content";
import type { ContentDetail, StoredFlag } from "@/types/api";

type Mode = "creator" | "manager";

const ORDER = {
  open: 0,
  dismissed: 1,
  edited: 2,
  accepted: 3,
  excepted: 4,
} as const;

export function ReviewWorkspace({
  contentId,
  mode,
  backHref,
}: {
  contentId: string;
  mode: Mode;
  backHref: string;
}) {
  const [viewing, setViewing] = useState<string | null>(null);
  const { content, flags, error, reload } = useContent(contentId, viewing);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [decision, setDecision] = useState("");
  const [submitOpen, setSubmitOpen] = useState(false);
  const [commentKey, setCommentKey] = useState(0);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [edits, setEdits] = useState<Map<string, string>>(new Map());

  const oldVersion = !!viewing && viewing !== content?.latest_version_id;
  const visible = useMemo(() => {
    const all = flags?.flags ?? [];
    const base =
      mode === "manager"
        ? all.filter((f) => f.status === "open" || f.status === "dismissed")
        : showResolved
          ? all
          : all.filter((f) => f.status === "open");
    return [...base].sort((a, b) => ORDER[a.status] - ORDER[b.status]);
  }, [flags, mode, showResolved]);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not open this content</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!content) {
    return (
      <p
        className="text-muted-foreground flex items-center gap-2"
        role="status"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
      </p>
    );
  }

  async function run<T>(
    label: string | ((result: T) => string),
    fn: () => Promise<T>,
  ) {
    setBusy(true);
    setActionError(null);
    setNotice(null);
    try {
      const result = await fn();
      setNotice(typeof label === "function" ? label(result) : label);
      setPicked(new Set());
      setEdits(new Map());
      setCommentKey((k) => k + 1);
      await reload();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "That did not work");
    } finally {
      setBusy(false);
    }
  }

  function onAction(flag: StoredFlag, action: FlagAction) {
    if (action.kind === "accept")
      void run("Fix applied in a new version.", () =>
        api<ContentDetail>(`/flags/${flag.id}/accept`, { method: "POST" }),
      );
    if (action.kind === "edit")
      void run("Your wording applied in a new version.", () =>
        api<ContentDetail>(`/flags/${flag.id}/edit`, {
          json: { text: action.text },
        }),
      );
    if (action.kind === "dismiss")
      void run("Flag dismissed.", () =>
        api(`/flags/${flag.id}/dismiss`, { json: { reason: action.reason } }),
      );
    if (action.kind === "except")
      void run(
        "Exception approved. The same wording will not be flagged again.",
        () =>
          api(`/flags/${flag.id}/except`, { json: { reason: action.reason } }),
      );
  }

  const PURPOSES: Record<string, string[]> = {
    guidelines: ["judge"],
    claims: ["claim_verification", "claim_extraction"],
    visuals: ["visual_check"],
  };
  function aiLabelFor(layer: string): string | undefined {
    for (const purpose of PURPOSES[layer] ?? []) {
      const use = flags?.ai_usage.find((u) => u.purpose === purpose);
      if (use)
        return `${use.provider} ${use.model}${use.cached === use.calls ? " (cached)" : ""}`;
    }
    return undefined;
  }

  function selectFlag(id: string) {
    setSelected(id);
    document
      .getElementById(`flag-${id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  const canEdit =
    mode === "creator" &&
    !oldVersion &&
    (content.status === "creator_review" ||
      content.status === "changes_requested");
  const canDecide =
    mode === "manager" && !oldVersion && content.status === "manager_review";
  const openHigh = content.counts.open_high;
  // One fix round per AI check: on a checked text version the creator chooses fixes (and
  // may reword any open flag), then applies them all at once. The fixed version is not
  // checked again; it is submitted, or a revised script is uploaded for a new check.
  const canFixRound =
    canEdit && content.format === "text" && !content.fixes_applied;
  const fixable = canFixRound
    ? visible.filter((f) => f.status === "open" && f.suggested_fix)
    : [];
  const pickedFixable = fixable.filter(
    (f) => picked.has(f.id) && !edits.has(f.id),
  );
  const allPicked =
    fixable.length > 0 &&
    fixable.every((f) => picked.has(f.id) || edits.has(f.id));
  const chosenCount = pickedFixable.length + edits.size;

  function applyFixes(all: boolean) {
    const ids = all
      ? fixable.filter((f) => !edits.has(f.id)).map((f) => f.id)
      : pickedFixable.map((f) => f.id);
    void run(
      (out: { applied: string[]; skipped: string[] }) =>
        `${out.applied.length} fix${out.applied.length === 1 ? "" : "es"} applied in version ${(content!.latest_version_number ?? 1) + 1}. Review it, then submit it to your manager.` +
        (out.skipped.length
          ? ` ${out.skipped.length} overlapped a more serious fix on the same words and stay open for your manager.`
          : ""),
      () =>
        api<{ applied: string[]; skipped: string[] }>(
          `/contents/${content!.id}/accept-fixes`,
          { json: { flag_ids: ids, edits: Object.fromEntries(edits) } },
        ),
    );
  }
  const codeOf = (id: string) =>
    flags?.flags.find((f) => f.id === id)?.source_id;

  return (
    <div className="space-y-6">
      {mode === "creator" && (
        <SubmitDialog
          open={submitOpen}
          onOpenChange={setSubmitOpen}
          brandId={content.brand_id}
          lastManagerEmail={content.manager_email}
          busy={busy}
          onSubmit={(managerEmail) =>
            run(`Sent to ${managerEmail} for approval.`, () =>
              api(`/contents/${content.id}/submit`, {
                json: { manager_email: managerEmail },
              }),
            ).then(() => setSubmitOpen(false))
          }
        />
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href={backHref}
            className="text-muted-foreground text-sm underline underline-offset-2"
          >
            ← Back
          </Link>
          <h1 className="hd-gradient-text mt-1 text-3xl font-bold tracking-tight">
            {content.title}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
            <ContentStatusBadge status={content.status} />
            <span className="text-muted-foreground">
              Version {flags?.version_number ?? content.latest_version_number}
              {content.creator_name ? ` · by ${content.creator_name}` : ""}
            </span>
          </div>
          {(mode === "manager"
            ? content.creator_email
            : content.manager_email) && (
            <p className="text-muted-foreground mt-1.5 flex items-center gap-1.5 text-sm">
              <Mail className="size-4" aria-hidden />
              {mode === "manager" ? (
                <>
                  From{" "}
                  <a
                    href={`mailto:${content.creator_email}`}
                    className="text-foreground font-medium underline underline-offset-2"
                  >
                    {content.creator_email}
                  </a>
                </>
              ) : (
                <>
                  Submitted to{" "}
                  <span className="text-foreground font-medium">
                    {content.manager_name ?? content.manager_email}
                  </span>{" "}
                  ({content.manager_email})
                </>
              )}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {mode === "creator" &&
            content.status === "creator_review" &&
            !oldVersion && (
              <Button disabled={busy} onClick={() => setSubmitOpen(true)}>
                <Send aria-hidden /> Submit to manager
              </Button>
            )}
          {mode === "creator" && content.status === "changes_requested" && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                run("Back in your review.", () =>
                  api(`/contents/${content.id}/reopen`, { method: "POST" }),
                )
              }
            >
              <Undo2 aria-hidden /> Start revising
            </Button>
          )}
        </div>
      </div>

      {mode === "creator" &&
        content.status === "creator_review" &&
        !oldVersion &&
        openHigh > 0 && (
          <p className="text-sm">
            {openHigh} high-severity flag{openHigh === 1 ? " is" : "s are"}{" "}
            still open. You can still submit: your manager will see{" "}
            {openHigh === 1 ? "it" : "them"} and decide.
          </p>
        )}
      {mode === "creator" &&
        content.fixes_applied &&
        !oldVersion &&
        canEdit && (
          <Alert>
            <CheckCircle2 className="size-4 text-green-700" aria-hidden />
            <AlertTitle>Your fixes are applied</AlertTitle>
            <AlertDescription>
              This version was made from your fixes and is not checked by AI
              again. Submit it to your manager, who decides on anything still
              open. To have the script checked again, upload a revised script
              below.
            </AlertDescription>
          </Alert>
        )}
      {content.status === "checking" && (
        <Alert role="status">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          <AlertTitle>Checking this version…</AlertTitle>
          <AlertDescription>
            Rules, brand guidelines and claims are being checked. This usually
            takes under a minute; the page updates by itself.
          </AlertDescription>
        </Alert>
      )}
      {content.status === "draft" && content.review_error && (
        <Alert variant="destructive">
          <AlertTitle>The check did not finish</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{content.review_error}</p>
            {mode === "creator" && (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() =>
                  run("Checking again…", () =>
                    api(`/contents/${content.id}/recheck`, { method: "POST" }),
                  )
                }
              >
                <RefreshCw aria-hidden /> Try again
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}
      {content.status === "changes_requested" && mode === "creator" && (
        <Alert>
          <AlertTitle>Your manager asked for changes</AlertTitle>
          <AlertDescription>
            See their comment below, fix the flags or the text, then submit
            again.
          </AlertDescription>
        </Alert>
      )}
      {content.status === "approved" && (
        <Alert>
          <CheckCircle2 className="size-4 text-green-700" aria-hidden />
          <AlertTitle>Approved</AlertTitle>
          <AlertDescription>
            This content passed review and can be published.
          </AlertDescription>
        </Alert>
      )}
      {oldVersion && (
        <Alert>
          <AlertDescription>
            You are viewing an older version (read only).{" "}
            <button className="underline" onClick={() => setViewing(null)}>
              Back to the latest
            </button>
          </AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert role="status">
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {actionError && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      {canDecide && (
        <section
          aria-labelledby="decide-h"
          className="bg-card space-y-3 rounded-lg border p-4"
        >
          <h2 id="decide-h" className="text-lg font-semibold">
            Your decision
          </h2>
          <Label htmlFor="decision">
            Comment (required to request changes)
          </Label>
          <Textarea
            id="decision"
            rows={3}
            value={decision}
            onChange={(e) => setDecision(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy}
              onClick={() =>
                run("Approved.", () =>
                  api(`/contents/${content.id}/approve`, {
                    json: { comment: decision.trim() || null },
                  }),
                ).then(() => setDecision(""))
              }
            >
              <CheckCircle2 aria-hidden /> Approve
            </Button>
            <Button
              variant="outline"
              disabled={busy || decision.trim().length < 3}
              onClick={() =>
                run("Sent back to the creator.", () =>
                  api(`/contents/${content.id}/request-changes`, {
                    json: { comment: decision.trim() },
                  }),
                ).then(() => setDecision(""))
              }
            >
              <Undo2 aria-hidden /> Request changes
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                run(
                  `Sent back to ${content.creator_email ?? "the creator"} with a fresh AI check.`,
                  () =>
                    api(`/contents/${content.id}/reevaluate`, {
                      json: { comment: decision.trim() || null },
                    }),
                ).then(() => setDecision(""))
              }
            >
              <RotateCcw aria-hidden /> Re-evaluate
            </Button>
          </div>
          <p className="text-muted-foreground text-xs">
            Re-evaluate runs the AI check again on the latest version and
            returns it to the same creator with fresh flags.
          </p>
        </section>
      )}
      {flags && content.status !== "checking" && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
          <section
            aria-labelledby="text-h"
            className="flex flex-col gap-2 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)]"
          >
            <h2 id="text-h" className="text-lg font-semibold">
              Content
            </h2>
            <ScrollPanel
              label="Content being reviewed"
              className="max-h-[75vh] min-h-0 space-y-3 pr-1 lg:max-h-none lg:flex-1"
            >
              {content.format === "pdf" ? (
                <PdfViewer
                  versionId={flags.version_id}
                  flags={mode === "manager" ? visible : flags.flags}
                  units={flags.units}
                  selectedId={selected}
                  onSelect={selectFlag}
                />
              ) : content.format === "video" ? (
                <VideoViewer
                  versionId={flags.version_id}
                  flags={mode === "manager" ? visible : flags.flags}
                  transcript={flags.text}
                  selectedId={selected}
                  onSelect={selectFlag}
                />
              ) : content.format === "image" ? (
                <ImageViewer
                  versionId={flags.version_id}
                  flags={mode === "manager" ? visible : flags.flags}
                  selectedId={selected}
                  onSelect={selectFlag}
                />
              ) : (
                <HighlightedText
                  text={flags.text}
                  flags={mode === "manager" ? visible : flags.flags}
                  selectedId={selected}
                  onSelect={selectFlag}
                />
              )}
              {canEdit && content.format === "text" && (
                <form
                  className="bg-muted space-y-2 rounded-md p-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const el = e.currentTarget.elements.namedItem(
                      "revised",
                    ) as HTMLTextAreaElement | null;
                    const text = el?.value.trim();
                    if (!text) return;
                    const form = new FormData();
                    form.append("text", text);
                    void run(
                      "Revised script uploaded. The AI is checking it…",
                      () => api(`/contents/${content.id}/versions`, { form }),
                    );
                  }}
                >
                  <Label htmlFor="revised">
                    Want the AI to check it again? Paste a revised script. It
                    becomes a new version and gets a new check.
                  </Label>
                  <Textarea id="revised" name="revised" rows={4} />
                  <Button
                    size="sm"
                    type="submit"
                    variant="outline"
                    disabled={busy}
                  >
                    Upload revised script
                  </Button>
                </form>
              )}
              {canEdit && content.format !== "text" && (
                <form
                  className="bg-muted space-y-2 rounded-md p-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const input =
                      (e.currentTarget.elements.namedItem(
                        "corrected",
                      ) as HTMLInputElement) ?? null;
                    const file = input?.files?.[0];
                    if (!file) return;
                    const form = new FormData();
                    form.append("file", file);
                    void run("New version uploaded. Checking it…", () =>
                      api(`/contents/${content.id}/versions`, { form }),
                    );
                  }}
                >
                  <Label htmlFor="corrected">
                    Fixes can&apos;t be applied inside a {content.format}.
                    Upload a corrected file as a new version:
                  </Label>
                  <input
                    id="corrected"
                    name="corrected"
                    type="file"
                    accept={
                      content.format === "pdf"
                        ? "application/pdf"
                        : "image/png,image/jpeg"
                    }
                    className="block text-sm"
                  />
                  <Button size="sm" type="submit" disabled={busy}>
                    Upload corrected {content.format}
                  </Button>
                </form>
              )}
            </ScrollPanel>
          </section>
          <section
            aria-labelledby="flags-h"
            className="flex flex-col gap-3 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)]"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="flags-h" className="text-lg font-semibold">
                {mode === "manager"
                  ? "Unresolved and dismissed flags"
                  : "Flags"}{" "}
                ({visible.length})
              </h2>
              {mode === "creator" && (
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="show-resolved"
                    checked={showResolved}
                    onCheckedChange={(v) => setShowResolved(v === true)}
                  />
                  <Label htmlFor="show-resolved" className="text-sm">
                    Show resolved
                  </Label>
                </div>
              )}
            </div>
            {canFixRound && (fixable.length > 0 || edits.size > 0) && (
              <div
                className="bg-muted flex flex-wrap items-center gap-2 rounded-md p-2"
                role="group"
                aria-label="Your fix round"
              >
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || fixable.length === 0}
                  aria-pressed={allPicked}
                  onClick={() =>
                    setPicked(
                      allPicked ? new Set() : new Set(fixable.map((f) => f.id)),
                    )
                  }
                >
                  {allPicked ? "Clear selection" : "Choose all fixes"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || chosenCount === 0}
                  onClick={() => applyFixes(false)}
                >
                  Apply chosen fixes ({chosenCount})
                </Button>
                <Button
                  size="sm"
                  disabled={busy || fixable.length + edits.size === 0}
                  onClick={() => applyFixes(true)}
                >
                  <CheckCheck aria-hidden /> Apply all suggested fixes (
                  {fixable.filter((f) => !edits.has(f.id)).length + edits.size})
                </Button>
                <p className="w-full text-xs">
                  You can apply fixes <strong>once</strong>. Choose them (or
                  reword any flag with &ldquo;Edit wording&rdquo;), then apply.
                  The fixed script is not checked by AI again: submit it, and
                  your manager decides on anything left.
                </p>
              </div>
            )}
            <ScrollPanel
              label={
                mode === "manager"
                  ? "Unresolved and dismissed flags"
                  : "Issues in this content"
              }
              className="max-h-[70vh] min-h-0 space-y-3 p-1 pr-2 lg:max-h-none lg:flex-1"
            >
              {visible.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  {mode === "manager"
                    ? "Nothing unresolved: every flag was fixed."
                    : "No open flags. Nothing crosses unchecked, and this passed."}
                </p>
              ) : (
                visible.map((flag, index) => (
                  <FlagCard
                    key={flag.id}
                    index={index}
                    flag={flag}
                    canFix={canFixRound}
                    aiLabel={aiLabelFor(flag.layer)}
                    picked={picked.has(flag.id)}
                    onPick={
                      fixable.some((f) => f.id === flag.id)
                        ? (on) =>
                            setPicked((prev) => {
                              const next = new Set(prev);
                              if (on) next.add(flag.id);
                              else next.delete(flag.id);
                              return next;
                            })
                        : undefined
                    }
                    stagedEdit={edits.get(flag.id)}
                    onStageEdit={
                      canFixRound
                        ? (text) =>
                            setEdits((prev) => {
                              const next = new Map(prev);
                              if (text === null) next.delete(flag.id);
                              else next.set(flag.id, text);
                              return next;
                            })
                        : undefined
                    }
                    mode={
                      canEdit ? "creator" : canDecide ? "manager" : "readonly"
                    }
                    selected={selected === flag.id}
                    busy={busy}
                    onSelect={() => setSelected(flag.id)}
                    onAction={(a) => onAction(flag, a)}
                  />
                ))
              )}
            </ScrollPanel>
          </section>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {(flags?.version_id ?? content.latest_version_id) && (
          <CommentsPanel
            versionId={(flags?.version_id ?? content.latest_version_id)!}
            refreshKey={commentKey}
            flagLabel={codeOf}
          />
        )}
        <VersionHistory
          content={content}
          viewing={viewing}
          onView={setViewing}
        />
      </div>
    </div>
  );
}
