"use client";

import { Loader2, MessageSquare } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { Comment } from "@/types/api";

export function CommentsPanel({
  versionId,
  refreshKey,
  flagLabel,
}: {
  versionId: string;
  refreshKey?: number;
  /** Turns a comment's flag id into a short label (e.g. its source code). */
  flagLabel?: (flagId: string) => string | undefined;
}) {
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setComments(await api<Comment[]>(`/versions/${versionId}/comments`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load comments");
    }
  }, [versionId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function post(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await api(`/versions/${versionId}/comments`, { json: { body } });
      setBody("");
      await load();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not post the comment",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="comments-h" className="space-y-3">
      <h2
        id="comments-h"
        className="flex items-center gap-2 text-lg font-semibold"
      >
        <MessageSquare className="size-4" aria-hidden /> Comments
      </h2>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {comments === null ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : comments.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No comments on this version yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {comments.map((c) => (
            <li key={c.id} className="bg-muted rounded-md p-2 text-sm">
              <p className="text-muted-foreground text-xs">
                {c.author_name ?? "Someone"}
                {c.author_role ? ` (${c.author_role})` : ""} ·{" "}
                {new Date(c.created_at).toLocaleString()}
                {c.flag_id && flagLabel?.(c.flag_id)
                  ? ` · on ${flagLabel(c.flag_id)}`
                  : ""}
              </p>
              <p className="whitespace-pre-wrap">{c.body}</p>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={post} className="space-y-2">
        <Label htmlFor="new-comment">Add a comment</Label>
        <Textarea
          id="new-comment"
          rows={2}
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <Button size="sm" type="submit" disabled={busy || !body.trim()}>
          {busy && <Loader2 className="animate-spin" aria-hidden />} Post
          comment
        </Button>
      </form>
    </section>
  );
}
