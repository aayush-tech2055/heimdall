"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { Me, Role } from "@/types/api";

/** Renders children only for signed-in users with one of `roles`; sends others to sign in. */
export function RoleGate({
  roles,
  children,
}: {
  roles: Role[];
  children: (me: Me) => React.ReactNode;
}) {
  const { session, me, loading, error } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, session, router]);

  if (loading || !session) {
    return (
      <p className="text-muted-foreground flex items-center gap-2" role="status">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
      </p>
    );
  }
  if (error || !me) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load your account</AlertTitle>
        <AlertDescription>{error ?? "No Heimdall profile for this account."}</AlertDescription>
      </Alert>
    );
  }
  if (!roles.includes(me.role)) {
    return (
      <Alert>
        <AlertTitle>Not available for your role</AlertTitle>
        <AlertDescription>
          This page is for {roles.join(" or ")} users. You are signed in as {me.role}.
        </AlertDescription>
      </Alert>
    );
  }
  return <>{children(me)}</>;
}
