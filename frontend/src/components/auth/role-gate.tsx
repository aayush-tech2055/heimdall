"use client";

import { Loader2, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ROLE_LABEL } from "@/lib/roles";
import type { Me, MeRaw, Role } from "@/types/api";

/** True when the person has a role and an active brand, so portal pages can use them. */
export function isActive(me: MeRaw | null): me is Me {
  return !!me && !!me.role && !!me.brand_id && !!me.brand_name;
}

/** Renders children only for signed-in users with one of `roles`; sends others to sign in. */
export function RoleGate({
  roles,
  children,
}: {
  roles: Role[];
  children: (me: Me) => React.ReactNode;
}) {
  const { session, me, loading, error, refresh, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
    else if (!loading && me?.needs_onboarding) router.replace("/onboarding");
  }, [loading, session, me, router]);

  if (loading || !session || me?.needs_onboarding) {
    return (
      <p
        className="text-muted-foreground flex items-center gap-2"
        role="status"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
      </p>
    );
  }
  if (error || !me || !me.role) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load your account</AlertTitle>
        <AlertDescription>
          {error ?? "No Heimdall profile for this account."}
        </AlertDescription>
      </Alert>
    );
  }
  if (!roles.includes(me.role)) {
    return (
      <Alert>
        <AlertTitle>Not available for your role</AlertTitle>
        <AlertDescription>
          This page is for {roles.join(" or ")} users. You are signed in as{" "}
          {me.role}.
        </AlertDescription>
      </Alert>
    );
  }
  if (!isActive(me)) {
    return (
      <section className="bg-card mx-auto max-w-lg space-y-4 rounded-2xl border p-8 text-center">
        <Users className="text-primary mx-auto size-10" aria-hidden />
        <h1 className="text-2xl font-bold tracking-tight">
          You are not on a team yet
        </h1>
        <p className="text-muted-foreground">
          You signed up as a {ROLE_LABEL[me.role].toLowerCase()}. Ask a brand
          admin to add <strong className="text-foreground">{me.email}</strong>{" "}
          to their team from their <em>Team</em> tab. Their guidelines then
          appear here.
        </p>
        <div className="flex justify-center gap-2">
          <Button onClick={() => void refresh()}>Check again</Button>
          <Button variant="outline" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </section>
    );
  }
  return <>{children(me)}</>;
}
