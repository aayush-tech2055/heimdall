"use client";

import { Loader2, Search, UserMinus, UserPlus } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { Input } from "@/components/ui/input";
import { ScrollPanel } from "@/components/ui/scroll-panel";
import { api, ApiError } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/roles";
import type { Me, Person, Role, TeamMember } from "@/types/api";

type Kind = "creator" | "manager";

const ROLE_TONE: Record<Role, string> = {
  admin: "bg-amber-100 text-amber-900 border-amber-300",
  manager: "bg-cyan-100 text-cyan-900 border-cyan-300",
  creator: "bg-fuchsia-100 text-fuchsia-900 border-fuchsia-300",
};

function Initials({ name }: { name: string }) {
  const letters = name
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
  return (
    <span
      aria-hidden
      className="flex size-9 shrink-0 items-center justify-center rounded-full bg-black text-xs font-semibold text-white"
    >
      {letters || "?"}
    </span>
  );
}

function Team({ me }: { me: Me }) {
  const base = `/brands/${me.brand_id}`;
  const [members, setMembers] = useState<TeamMember[] | null>(null);
  const [kind, setKind] = useState<Kind>("creator");
  const [q, setQ] = useState("");
  const [people, setPeople] = useState<Person[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadMembers = useCallback(
    () =>
      api<TeamMember[]>(`${base}/members`)
        .then(setMembers)
        .catch((e) =>
          setError(e instanceof ApiError ? e.message : "Could not load team"),
        ),
    [base],
  );
  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  // Debounced directory search.
  useEffect(() => {
    const ctrl = new AbortController();
    const t = window.setTimeout(() => {
      api<Person[]>(`${base}/directory`, {
        query: { role: kind, q: q.trim() },
        signal: ctrl.signal,
      })
        .then(setPeople)
        .catch(() => {});
    }, 250);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [base, kind, q, members]);

  async function act(id: string, fn: () => Promise<unknown>, done: string) {
    setBusy(id);
    setError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(done);
      await loadMembers();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That did not work");
    } finally {
      setBusy(null);
    }
  }

  const label = (p: { display_name: string | null; email: string | null }) =>
    p.display_name ?? p.email ?? "Unnamed";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Team"
        description={`Choose the creators and managers who follow ${me.brand_name}'s guidelines. A creator can be on several brands' teams and picks which one to follow.`}
      />
      {notice && (
        <Alert role="status">
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {error && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <section
          aria-labelledby="members-h"
          className="bg-card space-y-3 rounded-2xl border p-5"
        >
          <div className="flex items-baseline justify-between">
            <h2 id="members-h" className="text-lg font-semibold">
              On {me.brand_name}&apos;s team
            </h2>
            <span className="text-muted-foreground text-sm">
              {members?.length ?? "…"} people
            </span>
          </div>
          {!members ? (
            <p
              className="text-muted-foreground flex items-center gap-2"
              role="status"
            >
              <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
            </p>
          ) : (
            <ScrollPanel label="Team members" className="max-h-[60vh] pr-1">
              <ul className="space-y-2">
                <AnimatePresence initial={false}>
                  {members.map((m) => (
                    <motion.li
                      key={m.user_id}
                      layout
                      initial={{ opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 12 }}
                      className="flex items-center gap-3 rounded-xl border p-3"
                    >
                      <Initials name={label(m)} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{label(m)}</p>
                        <p className="text-muted-foreground truncate text-sm">
                          {m.email}
                        </p>
                      </div>
                      <Badge variant="outline" className={ROLE_TONE[m.role]}>
                        {ROLE_LABEL[m.role]}
                      </Badge>
                      {m.role !== "admin" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busy === m.user_id}
                          aria-label={`Remove ${label(m)} from the team`}
                          onClick={() =>
                            act(
                              m.user_id,
                              () =>
                                api(`${base}/members/${m.user_id}`, {
                                  method: "DELETE",
                                }),
                              `${label(m)} removed from the team.`,
                            )
                          }
                        >
                          <UserMinus aria-hidden />
                        </Button>
                      )}
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </ScrollPanel>
          )}
        </section>

        <section
          aria-labelledby="dir-h"
          className="bg-card space-y-3 rounded-2xl border p-5"
        >
          <h2 id="dir-h" className="text-lg font-semibold">
            Add people
          </h2>
          <FilterTabs<Kind>
            label="Show"
            value={kind}
            onChange={setKind}
            options={[
              { value: "creator", label: "Creators" },
              { value: "manager", label: "Managers" },
            ]}
          />
          <div className="relative">
            <Search
              className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2"
              aria-hidden
            />
            <Input
              aria-label={`Search ${kind}s by name or email`}
              placeholder={`Search ${kind}s by name or email`}
              className="pl-9"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          {!people ? (
            <p
              className="text-muted-foreground flex items-center gap-2"
              role="status"
            >
              <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
            </p>
          ) : people.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No {kind}s to add{q ? ` matching “${q}”` : ""}. People sign up as
              a {kind} first, then appear here.
            </p>
          ) : (
            <ScrollPanel
              label={`${kind}s you can add`}
              className="max-h-[52vh] pr-1"
            >
              <ul className="space-y-2">
                {people.map((p) => (
                  <li
                    key={p.user_id}
                    className="flex items-center gap-3 rounded-xl border p-3"
                  >
                    <Initials name={label(p)} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{label(p)}</p>
                      <p className="text-muted-foreground truncate text-sm">
                        {p.email}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      disabled={busy === p.user_id}
                      aria-label={`Add ${label(p)} to the team`}
                      onClick={() =>
                        act(
                          p.user_id,
                          () =>
                            api(`${base}/members`, {
                              json: { user_id: p.user_id },
                            }),
                          `${label(p)} now follows ${me.brand_name}'s guidelines.`,
                        )
                      }
                    >
                      {busy === p.user_id ? (
                        <Loader2 className="animate-spin" aria-hidden />
                      ) : (
                        <UserPlus aria-hidden />
                      )}
                      Add
                    </Button>
                  </li>
                ))}
              </ul>
            </ScrollPanel>
          )}
        </section>
      </div>
    </div>
  );
}

export default function TeamPage() {
  return <RoleGate roles={["admin"]}>{(me) => <Team me={me} />}</RoleGate>;
}
