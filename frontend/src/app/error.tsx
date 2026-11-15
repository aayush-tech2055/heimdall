"use client";

import { RefreshCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/** Shown when a screen crashes, instead of a blank page (task 14.2). */
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-lg space-y-4 pt-8">
      <Alert variant="destructive" role="alert">
        <AlertTitle>Something went wrong on this screen</AlertTitle>
        <AlertDescription>
          {error.message || "An unexpected error happened."} Your work is saved;
          try again, or go back and reopen the page.
        </AlertDescription>
      </Alert>
      <Button onClick={reset}>
        <RefreshCw aria-hidden /> Try again
      </Button>
    </div>
  );
}
