"use client";

import {
  Bot,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  PenLine,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

type Step = {
  title: string;
  body: string;
  points: string[];
  shot: string;
  alt: string;
};

type RoleGuideData = {
  id: "admin" | "manager" | "creator";
  name: string;
  icon: LucideIcon;
  accent: string;
  ring: string;
  tagline: string;
  steps: Step[];
};

const ROLES: RoleGuideData[] = [
  {
    id: "admin",
    name: "Admin",
    icon: Building2,
    accent: "from-amber-300 to-amber-500",
    ring: "text-amber-300",
    tagline:
      "You own the brand. You teach Heimdall your rules and facts and decide who works under them.",
    steps: [
      {
        title: "Upload your brand guidelines",
        body: "Sign up as an Admin and name your brand. On Guidelines, upload your guideline (PDF, Word, PowerPoint, text, Markdown or CSV, several files at once) or paste it.",
        points: [
          "Heimdall turns it into one rule per instruction, each with a code like R-012, a category and the page it came from.",
          "It checks the guideline itself: duplicate rules, contradictions, vague rules (with a suggested rewrite) and missing categories.",
          "New rules stay pending. Approve or reject each one (or Approve all). Only approved rules are used in checks.",
          "Banned words and required phrases run in plain code; everything else is judged by AI against the exact rule.",
        ],
        shot: "/guide/admin-guidelines.jpg",
        alt: "The admin Guidelines page with the upload form and the verification report listing duplicate and contradicting rules.",
      },
      {
        title: "Add the facts claims are checked against",
        body: "On Facts, add or import (CSV) your approved facts: prices, product details, survey results, each with a source and a valid-until date.",
        points: [
          "Every factual or promotional claim in content must match an approved fact, or it is flagged under the policy SYS-CLAIM-001.",
          "Expired facts, and facts expiring within 30 days, get a badge, so nobody quotes an old price.",
          "Website check compares your live web pages with the facts and proposes changes. Nothing changes until you accept.",
        ],
        shot: "/guide/admin-facts.jpg",
        alt: "The admin Facts page listing approved facts with values, sources and expiry dates.",
      },
      {
        title: "Build your team",
        body: "Creators and managers sign up themselves with their role. Then you choose who follows your guidelines from the Team tab.",
        points: [
          "Open Team. The left side shows everyone on your brand's team, with their role.",
          "On the right, switch between Creators and Managers, search by name or email, and press Add.",
          "Remove someone with the button next to their name. Admins cannot be removed.",
          'A creator can be on several admins\' teams; they pick which brand to follow from the "Following" menu.',
          "Creators submit their work to a manager on your team, by email.",
        ],
        shot: "/guide/admin-team.jpg",
        alt: "The admin Team page: current members on the left, and a searchable list of creators to add on the right.",
      },
      {
        title: "Set privacy and checking options",
        body: "On Settings, list confidential terms (unreleased product names, partner names). They are masked, with emails, phone numbers and card numbers, before any AI sees the content.",
        points: [
          "Switch the claim policy on or off for your brand.",
          "Set a readability target; content below it gets an accessibility flag.",
          "In Assets, keep approved logos, disclaimers and product copy; missing disclaimers are fixed with the approved text.",
        ],
        shot: "/guide/admin-settings.jpg",
        alt: "The admin Settings page with confidential terms, the claim policy switch and the readability target.",
      },
      {
        title: "Watch how it is going",
        body: "Insights shows flags per week and by category, how many were dismissed, how often content is sent back and the average time to approval.",
        points: [
          'Guideline health marks a rule "probably unclear" when it is dismissed in 40% or more of at least 5 flags, so you know which rule to rewrite.',
          "AI disclosure lists every AI service used, what it received and what was removed first.",
        ],
        shot: "/guide/admin-insights.jpg",
        alt: "The Insights page with charts of flags per week and by category.",
      },
    ],
  },
  {
    id: "creator",
    name: "Creator",
    icon: PenLine,
    accent: "from-fuchsia-300 to-fuchsia-500",
    ring: "text-fuchsia-300",
    tagline:
      "You write and design. Heimdall shows you exactly what breaks the brand rules, and why, before anyone else sees it.",
    steps: [
      {
        title: "Join a brand's team",
        body: 'Sign up as a Creator. Until an admin adds you to their team you will see "You are not on a team yet": send them your email.',
        points: [
          'You can be on several brands\' teams. Pick the brand whose guidelines you are working under from "Following" in the header.',
          "My content lists everything you have checked and where it is in review.",
        ],
        shot: "/guide/creator-list.jpg",
        alt: "The creator's My content page listing checked items with their status and flag counts.",
      },
      {
        title: "Run a check",
        body: "Press New check, give it a title and paste text or upload a PDF, an image (with alt text) or a video up to 60 seconds.",
        points: [
          "Feedback usually arrives in under a minute.",
          "Personal details and the brand's confidential terms are masked before any AI call.",
        ],
        shot: "/guide/creator-new.jpg",
        alt: "The New check page with a title field and options to paste text or upload a file.",
      },
      {
        title: "Fix the flags",
        body: "Every flag highlights the exact words, says why, and cites its source: a rule (R-012), a fact (F-003) or the claim policy. No source, no flag.",
        points: [
          "Accept fix applies the suggested fix in a new version.",
          "Edit wording lets you write your own fix. Dismiss needs a short reason, which your manager sees.",
          "Choose several fixes and apply them at once, or upload a revised script for a fresh AI check.",
        ],
        shot: "/guide/creator-review.jpg",
        alt: "The creator review page: the script with highlighted problems on the left and flags with Accept fix, Edit wording and Dismiss on the right.",
      },
      {
        title: "Submit to your manager",
        body: 'Press Submit to manager and type their email. It is checked as you type: a green "Found" means a manager with that email is on the brand\'s team, and Submit unlocks.',
        points: [
          "If the manager asks for changes, read their comment, press Start revising, fix it and submit again.",
          "If they press Re-evaluate, it comes back to you with fresh AI flags.",
        ],
        shot: "/guide/creator-submit.jpg",
        alt: "The Submit to a manager dialog showing a green Found message under the manager's email.",
      },
    ],
  },
  {
    id: "manager",
    name: "Manager",
    icon: ClipboardCheck,
    accent: "from-cyan-300 to-cyan-500",
    ring: "text-cyan-300",
    tagline:
      "You approve what goes out. You see only what is still open, with the reasons behind every dismissal.",
    steps: [
      {
        title: "Your review queue",
        body: "Sign up as a Manager and ask a brand admin to add you to their team. Creators then send their work to you by typing your email.",
        points: [
          "You see only what was sent to you, with the creator's name and email.",
          "Filter by status: with you, sent back or approved.",
        ],
        shot: "/guide/manager-queue.jpg",
        alt: "The manager's review queue listing submitted content with the creator's name and email.",
      },
      {
        title: "Decide",
        body: "Open an item to see who sent it, the content with highlights, and the flags still open or dismissed (with the creator's reason).",
        points: [
          "Approve: it can be published.",
          "Request changes: it goes back to the same creator with your comment.",
          "Re-evaluate: runs a fresh AI check on the latest version and returns it to the same creator.",
          "Approve exception on a flag (with a reason) to allow it in future checks. Every decision is recorded.",
        ],
        shot: "/guide/manager-review.jpg",
        alt: "The manager review page with the From email line and the Approve, Request changes and Re-evaluate buttons.",
      },
    ],
  },
];

function Shot({ step, ring }: { step: Step; ring: string }) {
  return (
    <motion.figure
      whileHover={{ y: -6, rotateX: 2, rotateY: -2 }}
      transition={{ type: "spring", stiffness: 220, damping: 22 }}
      className="relative [perspective:1200px]"
    >
      <div className="overflow-hidden rounded-2xl border border-white/15 bg-white/5 shadow-[0_40px_90px_-40px_rgba(0,0,0,0.9)]">
        <div className="flex items-center gap-1.5 border-b border-white/10 bg-white/[0.06] px-3 py-2">
          <span className="size-2.5 rounded-full bg-white/25" />
          <span className="size-2.5 rounded-full bg-white/25" />
          <span className="size-2.5 rounded-full bg-white/25" />
          <span className="ml-3 truncate text-[11px] text-white/50">
            heimdall · {step.title}
          </span>
        </div>
        <Image
          src={step.shot}
          alt={step.alt}
          width={1440}
          height={900}
          sizes="(min-width: 1024px) 640px, 100vw"
          className="h-auto w-full"
        />
      </div>
      <span
        aria-hidden
        className={cn(
          "pointer-events-none absolute -inset-6 -z-10 rounded-[2rem] bg-current opacity-[0.07] blur-2xl",
          ring,
        )}
      />
    </motion.figure>
  );
}

/** Step-by-step guide for each role, with real screenshots. Dark surface. */
export function RoleGuide({ headingLevel = 2 }: { headingLevel?: 2 | 3 }) {
  const [active, setActive] = useState<RoleGuideData["id"]>("admin");
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const role = ROLES.find((r) => r.id === active)!;
  const H = headingLevel === 2 ? "h3" : "h4";

  function onKey(e: React.KeyboardEvent, i: number) {
    const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = (i + dir + ROLES.length) % ROLES.length;
    setActive(ROLES[next].id);
    tabs.current[next]?.focus();
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label="Choose a role"
        className="mx-auto flex w-fit flex-wrap justify-center gap-2 rounded-full border border-white/15 bg-white/[0.05] p-1.5"
      >
        {ROLES.map((r, i) => {
          const on = r.id === active;
          return (
            <button
              key={r.id}
              ref={(el) => {
                tabs.current[i] = el;
              }}
              role="tab"
              id={`guide-tab-${r.id}`}
              aria-selected={on}
              aria-controls={`guide-panel-${r.id}`}
              tabIndex={on ? 0 : -1}
              onClick={() => setActive(r.id)}
              onKeyDown={(e) => onKey(e, i)}
              className={cn(
                "relative flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none",
                on ? "text-black" : "text-white/75 hover:text-white",
              )}
            >
              {on && (
                <motion.span
                  layoutId="guide-pill"
                  className="absolute inset-0 rounded-full bg-white"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <r.icon className="relative size-4" aria-hidden />
              <span className="relative">{r.name}</span>
            </button>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={role.id}
          role="tabpanel"
          id={`guide-panel-${role.id}`}
          aria-labelledby={`guide-tab-${role.id}`}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.35 }}
          className="mt-10"
        >
          <p className="mx-auto max-w-2xl text-center text-lg text-white/75">
            {role.tagline}
          </p>
          <ol className="mt-14 space-y-20">
            {role.steps.map((s, i) => (
              <motion.li
                key={s.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.6 }}
                className="grid items-center gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-12"
              >
                <div className={cn(i % 2 === 1 && "lg:order-2")}>
                  <span
                    className={cn(
                      "inline-flex size-10 items-center justify-center rounded-xl bg-gradient-to-br text-base font-bold text-black",
                      role.accent,
                    )}
                  >
                    {i + 1}
                  </span>
                  <H className="mt-4 text-2xl font-bold tracking-tight text-white">
                    {s.title}
                  </H>
                  <p className="mt-3 text-white/75">{s.body}</p>
                  <ul className="mt-5 space-y-2.5 text-sm text-white/80">
                    {s.points.map((pt) => (
                      <li key={pt} className="flex items-start gap-2.5">
                        <CheckCircle2
                          className={cn("mt-0.5 size-4 shrink-0", role.ring)}
                          aria-hidden
                        />
                        {pt}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className={cn(i % 2 === 1 && "lg:order-1")}>
                  <Shot step={s} ring={role.ring} />
                </div>
              </motion.li>
            ))}
          </ol>
        </motion.div>
      </AnimatePresence>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        className="mt-24 grid items-center gap-8 rounded-3xl border border-white/15 bg-white/[0.04] p-6 sm:p-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]"
      >
        <div>
          <span className="inline-flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-300 to-amber-300 text-black">
            <Bot className="size-5" aria-hidden />
          </span>
          <H className="mt-4 text-2xl font-bold tracking-tight text-white">
            Stuck? Ask the Help assistant
          </H>
          <p className="mt-3 text-white/75">
            Every portal has a Help button in the bottom-right corner. Ask what
            a page or button does, or how to get something done, and it answers
            for your role and the page you are on.
          </p>
        </div>
        <Shot
          step={{
            title: "Help assistant",
            body: "",
            points: [],
            shot: "/guide/help-chat.jpg",
            alt: "The Help assistant open on a creator's review page, answering how to submit to a manager in four steps.",
          }}
          ring="text-indigo-300"
        />
      </motion.div>
    </div>
  );
}
