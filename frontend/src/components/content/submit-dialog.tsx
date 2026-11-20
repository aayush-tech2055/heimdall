"use client";

import { CheckCircle2, Loader2, Send, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

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
import { api, ApiError } from "@/lib/api";
import type { ManagerCheck } from "@/types/api";

type Check =
  | { state: "idle" }
  | { state: "checking" }
  | { state: "done"; result: ManagerCheck };

/** Ask for the manager's email and check it live: Submit unlocks only when a manager on
 * this brand's team has that email. */
export function SubmitDialog({
  open,
  onOpenChange,
  brandId,
  lastManagerEmail,
  busy,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  brandId: string | null;
  lastManagerEmail: string | null;
  busy: boolean;
  onSubmit: (managerEmail: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [check, setCheck] = useState<Check>({ state: "idle" });

  useEffect(() => {
    if (open) setEmail(lastManagerEmail ?? "");
  }, [open, lastManagerEmail]);

  useEffect(() => {
    const value = email.trim();
    if (!open || !brandId || !value) {
      setCheck({ state: "idle" });
      return;
    }
    setCheck({ state: "checking" });
    const ctrl = new AbortController();
    const t = window.setTimeout(() => {
      api<ManagerCheck>(`/brands/${brandId}/managers/check`, {
        query: { email: value },
        signal: ctrl.signal,
      })
        .then((result) => setCheck({ state: "done", result }))
        .catch((e) => {
          if (ctrl.signal.aborted) return;
          setCheck({
            state: "done",
            result: {
              found: false,
              display_name: null,
              message:
                e instanceof ApiError
                  ? e.message
                  : "Could not check this email",
            },
          });
        });
    }, 350);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [email, open, brandId]);

  const ok = check.state === "done" && check.result.found;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (ok && !busy) onSubmit(email.trim());
          }}
          className="space-y-4"
        >
          <DialogHeader>
            <DialogTitle>Submit to a manager</DialogTitle>
            <DialogDescription>
              Type the email of the manager who should review this. It must
              belong to a manager on this brand&apos;s team.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="manager-email">Manager&apos;s email</Label>
            <Input
              id="manager-email"
              type="email"
              autoComplete="off"
              autoFocus
              placeholder="manager@brand.example"
              value={email}
              aria-describedby="manager-check"
              aria-invalid={check.state === "done" && !check.result.found}
              onChange={(e) => setEmail(e.target.value)}
            />
            <p
              id="manager-check"
              aria-live="polite"
              className="flex min-h-5 items-center gap-1.5 text-sm"
            >
              {check.state === "checking" && (
                <>
                  <Loader2
                    className="text-muted-foreground size-4 animate-spin"
                    aria-hidden
                  />
                  <span className="text-muted-foreground">Checking…</span>
                </>
              )}
              {check.state === "done" &&
                (check.result.found ? (
                  <>
                    <CheckCircle2
                      className="size-4 text-green-700"
                      aria-hidden
                    />
                    <span className="font-medium text-green-800">
                      Found: {check.result.message}
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="size-4 text-red-700" aria-hidden />
                    <span className="text-red-800">{check.result.message}</span>
                  </>
                ))}
            </p>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!ok || busy}>
              {busy ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Send aria-hidden />
              )}
              Submit
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
