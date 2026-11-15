"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HOME_BY_ROLE } from "@/lib/roles";

export default function LoginPage() {
  const { me, signIn, loading, error: profileError } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (me) router.replace(HOME_BY_ROLE[me.role]);
  }, [me, router]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(email, password);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm pt-8">
      <Card>
        <CardHeader>
          <CardTitle>
            <h1>Sign in to Heimdall</h1>
          </CardTitle>
          <CardDescription>Use the account your brand admin gave you.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {(error ?? profileError) && (
              <Alert variant="destructive" role="alert">
                <AlertDescription>{error ?? profileError}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" className="w-full" disabled={submitting || (loading && !!me)}>
              {submitting && <Loader2 className="animate-spin" aria-hidden />}
              Sign in
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
