"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { HOME_BY_ROLE } from "@/lib/roles";

/** Sends signed-in users to their workspace and everyone else to sign in. */
export default function Home() {
  const { session, me, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) return;
    if (!session) router.replace("/login");
    else if (me) router.replace(HOME_BY_ROLE[me.role]);
  }, [loading, session, me, router]);
  return (
    <p className="text-muted-foreground flex items-center gap-2" role="status">
      <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
    </p>
  );
}
