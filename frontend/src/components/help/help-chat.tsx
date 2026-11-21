"use client";

import { Bot, Loader2, MessageCircleQuestion, Send, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Role } from "@/types/api";

type Turn = { role: "user" | "assistant"; text: string; error?: boolean };

const SUGGEST: Record<Role, string[]> = {
  admin: [
    "How do I build my team?",
    "How do I upload guidelines?",
    "What are pending rules?",
  ],
  creator: [
    "How do I submit to my manager?",
    "What do Accept, Edit and Dismiss do?",
    "How do I get my script checked again?",
  ],
  manager: [
    "What does Re-evaluate do?",
    "How do I send content back?",
    "What is an exception?",
  ],
};

/** A floating "Help" button in every portal: a chat assistant that explains the page the
 * person is on, what each button does and how to get something done. */
export function HelpChat() {
  const { me } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns, busy]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (!me?.role) return null;
  const role = me.role;

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    const history = turns
      .filter((t) => !t.error)
      .map(({ role: r, text }) => ({ role: r, text }));
    setTurns((t) => [...t, { role: "user", text: q }]);
    setDraft("");
    setBusy(true);
    try {
      const out = await api<{ answer: string }>("/help/chat", {
        json: { question: q, path: pathname, history },
      });
      setTurns((t) => [...t, { role: "assistant", text: out.answer }]);
    } catch (e) {
      setTurns((t) => [
        ...t,
        {
          role: "assistant",
          error: true,
          text:
            e instanceof ApiError
              ? e.message
              : "Could not reach the help assistant.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function close() {
    setOpen(false);
    buttonRef.current?.focus();
  }

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.section
            role="dialog"
            aria-modal="false"
            aria-labelledby="help-title"
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.97 }}
            transition={{ duration: 0.22, ease: [0.2, 0.7, 0.2, 1] }}
            onKeyDown={(e) => e.key === "Escape" && close()}
            className="bg-background fixed right-4 bottom-24 z-50 flex h-[min(34rem,calc(100svh-8rem))] w-[min(24rem,calc(100vw-2rem))] origin-bottom-right flex-col overflow-hidden rounded-2xl border shadow-[0_30px_80px_-30px_oklch(0_0_0_/_0.55)]"
          >
            <header className="flex items-center gap-3 bg-black px-4 py-3 text-white">
              <span className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-400 to-amber-300 text-black">
                <Bot className="size-4.5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <h2 id="help-title" className="text-sm font-semibold">
                  Heimdall help
                </h2>
                <p className="truncate text-xs text-white/65">
                  Ask how anything on this page works
                </p>
              </div>
              <button
                type="button"
                onClick={close}
                aria-label="Close help"
                className="rounded-full p-1.5 hover:bg-white/15 focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
              >
                <X className="size-4" aria-hidden />
              </button>
            </header>

            <div
              ref={listRef}
              data-lenis-prevent
              aria-live="polite"
              className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
            >
              {turns.length === 0 && (
                <div className="space-y-3">
                  <p className="bg-muted rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm">
                    Hi {me.display_name?.split(" ")[0] ?? "there"}! I can
                    explain this page, what each button does, and how to get
                    things done as a {role}. Try one of these:
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {["What can I do on this page?", ...SUGGEST[role]].map(
                      (s) => (
                        <li key={s}>
                          <button
                            type="button"
                            onClick={() => void ask(s)}
                            className="hover:bg-muted focus-visible:ring-ring rounded-full border px-3 py-1.5 text-left text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
                          >
                            {s}
                          </button>
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              )}
              {turns.map((t, i) => (
                <motion.p
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-line",
                    t.role === "user"
                      ? "ml-auto rounded-tr-sm bg-black text-white"
                      : t.error
                        ? "rounded-tl-sm border border-red-300 bg-red-50 text-red-900"
                        : "bg-muted rounded-tl-sm",
                  )}
                >
                  <span className="sr-only">
                    {t.role === "user" ? "You: " : "Help: "}
                  </span>
                  {t.text}
                </motion.p>
              ))}
              {busy && (
                <p
                  role="status"
                  className="bg-muted text-muted-foreground flex w-fit items-center gap-2 rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm"
                >
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Thinking…
                </p>
              )}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                void ask(draft);
              }}
              className="flex items-end gap-2 border-t p-3"
            >
              <label htmlFor="help-input" className="sr-only">
                Ask the help assistant
              </label>
              <textarea
                id="help-input"
                ref={inputRef}
                rows={1}
                maxLength={600}
                value={draft}
                placeholder="e.g. What does Re-evaluate do?"
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void ask(draft);
                  }
                }}
                className="border-input focus-visible:ring-ring max-h-28 min-h-10 flex-1 resize-none rounded-xl border bg-transparent px-3 py-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
              />
              <button
                type="submit"
                disabled={busy || !draft.trim()}
                aria-label="Send question"
                className="focus-visible:ring-ring flex size-10 items-center justify-center rounded-xl bg-black text-white transition-transform focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-95 disabled:opacity-40"
              >
                <Send className="size-4" aria-hidden />
              </button>
            </form>
            <p className="text-muted-foreground px-3 pb-2 text-[11px]">
              AI answers about using Heimdall. Personal details are masked
              first.
            </p>
          </motion.section>
        )}
      </AnimatePresence>

      <motion.button
        ref={buttonRef}
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        aria-expanded={open}
        aria-label={open ? "Close help" : "Open help assistant"}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className="fixed right-4 bottom-5 z-50 flex h-14 items-center gap-2 rounded-full bg-black pr-5 pl-4 text-sm font-semibold text-white shadow-[0_16px_40px_-12px_oklch(0_0_0_/_0.6)] focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:outline-none"
      >
        <span className="relative flex">
          <MessageCircleQuestion className="size-5" aria-hidden />
          {!open && turns.length === 0 && (
            <span
              aria-hidden
              className="absolute -top-0.5 -right-0.5 size-2.5 animate-ping rounded-full bg-amber-300"
            />
          )}
        </span>
        Help
      </motion.button>
    </>
  );
}
