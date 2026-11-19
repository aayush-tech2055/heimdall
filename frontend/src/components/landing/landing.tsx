"use client";

import {
  ArrowRight,
  BadgeCheck,
  BarChart3,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  Code2,
  EyeOff,
  FileSearch,
  FileText,
  Film,
  Globe,
  History,
  Image as ImageIcon,
  Layers,
  Library,
  MessageSquare,
  PenLine,
  ShieldCheck,
  Sparkles,
  Upload,
  UserCheck,
  Users,
} from "lucide-react";
import {
  animate,
  motion,
  MotionConfig,
  useInView,
  useMotionValueEvent,
  useScroll,
  useSpring,
  useTransform,
} from "motion/react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { HeroScene } from "@/components/landing/hero-scene";
import { BrandMark } from "@/components/shell/brand-mark";
import { HOME_BY_ROLE } from "@/lib/roles";
import { cn } from "@/lib/utils";

const ease = [0.2, 0.7, 0.2, 1] as const;

/** Fades and rises into view once, as it scrolls in. */
function Reveal({
  children,
  delay = 0,
  className,
  y = 28,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  y?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.7, delay, ease }}
    >
      {children}
    </motion.div>
  );
}

function Kicker({
  children,
  dark,
}: {
  children: React.ReactNode;
  dark?: boolean;
}) {
  return (
    <p
      className={cn(
        "text-xs font-semibold tracking-[0.25em] uppercase",
        dark ? "text-white/70" : "text-black/60",
      )}
    >
      {children}
    </p>
  );
}

/* ------------------------------------------------------------------ */
/* Navigation                                                          */
/* ------------------------------------------------------------------ */

function Nav() {
  const { me } = useAuth();
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setSolid(v > 60));
  const links = [
    ["Product", "#product"],
    ["How it works", "#how"],
    ["Features", "#features"],
    ["Who it's for", "#teams"],
  ];
  return (
    <motion.header
      initial={{ y: -40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease }}
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-colors duration-500",
        solid
          ? "border-b border-black/10 bg-white/80 text-black backdrop-blur-xl"
          : "bg-transparent text-white",
      )}
    >
      <nav
        aria-label="Main"
        className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4"
      >
        <Link
          href="/"
          className="flex items-center gap-2 text-lg font-semibold tracking-tight"
        >
          <BrandMark tone={solid ? "dark" : "light"} />
          Heimdall
        </Link>
        <ul className="hidden items-center gap-1 md:flex">
          {links.map(([label, href]) => (
            <li key={href}>
              <a
                href={href}
                className={cn(
                  "rounded-full px-3 py-2 text-sm font-medium transition-colors",
                  solid ? "hover:bg-black/5" : "hover:bg-white/10",
                )}
              >
                {label}
              </a>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-2">
          {me ? (
            <Link
              href={HOME_BY_ROLE[me.role]}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition-transform active:scale-95",
                solid ? "bg-black text-white" : "bg-white text-black",
              )}
            >
              Open workspace <ArrowRight className="size-4" aria-hidden />
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className={cn(
                  "rounded-full px-4 py-2 text-sm font-semibold transition-colors",
                  solid ? "hover:bg-black/5" : "hover:bg-white/10",
                )}
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className={cn(
                  "rounded-full px-4 py-2 text-sm font-semibold transition-transform hover:scale-[1.03] active:scale-95",
                  solid ? "bg-black text-white" : "bg-white text-black",
                )}
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </nav>
    </motion.header>
  );
}

/* ------------------------------------------------------------------ */
/* Hero                                                                */
/* ------------------------------------------------------------------ */

function Hero() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const textY = useTransform(scrollYProgress, [0, 1], [0, 160]);
  const fade = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const cardY = useTransform(scrollYProgress, [0, 1], [0, -120]);
  const words = ["Nothing", "crosses", "unchecked."];
  return (
    <section
      ref={ref}
      id="product"
      className="relative flex min-h-[100svh] items-center overflow-hidden bg-black text-white"
    >
      <div className="hd-grid-bg absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
      <HeroScene />
      <div
        aria-hidden
        className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/40 to-transparent"
      />
      <motion.div
        style={{ y: textY, opacity: fade }}
        className="relative z-10 mx-auto w-full max-w-6xl px-4 pt-24 pb-40"
      >
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.6, ease }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium text-white/80 backdrop-blur"
        >
          <Sparkles className="size-3.5 text-amber-300" aria-hidden /> AI brand
          governance · built for marketing teams
        </motion.div>
        <h1 className="max-w-4xl text-5xl leading-[1.02] font-bold tracking-tight sm:text-7xl md:text-8xl">
          {words.map((w, i) => (
            <span
              key={w}
              className="inline-block overflow-hidden pb-2 align-bottom"
            >
              <motion.span
                className={cn(
                  "mr-[0.25em] inline-block",
                  i === 2 &&
                    "bg-gradient-to-r from-white via-indigo-200 to-amber-200 bg-clip-text text-transparent",
                )}
                initial={{ y: "110%" }}
                animate={{ y: 0 }}
                transition={{ delay: 0.35 + i * 0.12, duration: 0.9, ease }}
              >
                {w}
              </motion.span>
            </span>
          ))}
        </h1>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.7, ease }}
          className="mt-6 max-w-2xl text-lg text-white/75 sm:text-xl"
        >
          Heimdall is the checkpoint between &ldquo;draft&rdquo; and
          &ldquo;publish&rdquo;. It checks every ad, post, PDF, image and video
          against your brand guidelines and approved facts, and shows the source
          for every issue it raises. People make every decision.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1, duration: 0.7, ease }}
          className="mt-10 flex flex-wrap items-center gap-3"
        >
          <Link
            href="/signup"
            className="group inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-black transition-transform hover:scale-[1.03] active:scale-95"
          >
            Get started
            <ArrowRight
              className="size-4 transition-transform group-hover:translate-x-1"
              aria-hidden
            />
          </Link>
          <Link
            href="/login"
            className="rounded-full border border-white/25 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
          >
            Sign in
          </Link>
          <a
            href="#how"
            className="px-2 py-3 text-sm font-medium text-white/70 underline-offset-4 hover:text-white hover:underline"
          >
            See how it works
          </a>
        </motion.div>
      </motion.div>

      {/* Floating preview of a real flag */}
      <motion.div
        style={{ y: cardY }}
        initial={{ opacity: 0, x: 40, rotate: 4 }}
        animate={{ opacity: 1, x: 0, rotate: 2 }}
        transition={{ delay: 1.2, duration: 0.9, ease }}
        className="absolute right-6 bottom-28 z-10 hidden w-80 rounded-2xl border border-white/15 bg-white/10 p-4 text-sm text-white shadow-2xl backdrop-blur-xl lg:block"
      >
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-rose-500/90 px-2 py-0.5 text-xs font-semibold">
            High
          </span>
          <span className="rounded-full bg-white/15 px-2 py-0.5 text-xs">
            Claims
          </span>
          <span className="rounded-md bg-white/15 px-2 py-0.5 font-mono text-xs">
            F-001
          </span>
        </div>
        <p className="mt-3 border-l-2 border-amber-300 pl-2 italic">
          &ldquo;kills 99.9% of germs&rdquo;
        </p>
        <p className="mt-2 text-white/80">
          The approved fact says 99% of mouth germs in lab tests.
        </p>
        <p className="mt-2">
          <span className="font-semibold">Fix:</span> kills 99% of germs
        </p>
      </motion.div>

      <motion.div
        style={{ opacity: fade }}
        className="absolute bottom-8 left-1/2 z-10 -translate-x-1/2 text-white/60"
        aria-hidden
      >
        <div className="flex h-10 w-6 justify-center rounded-full border border-white/30 pt-2">
          <motion.span
            className="block h-2 w-1 rounded-full bg-white/80"
            animate={{ y: [0, 12, 0] }}
            transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
          />
        </div>
      </motion.div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Marquee                                                             */
/* ------------------------------------------------------------------ */

function Marquee() {
  const items = [
    "Text",
    "PDF",
    "Images",
    "Video",
    "Brand guidelines",
    "Approved facts with expiry",
    "No source, no flag",
    "Suggested fixes",
    "Manager approval",
    "Audit trail",
    "Guideline health",
    "Privacy masking",
  ];
  const row = [...items, ...items];
  return (
    <div
      className="overflow-hidden border-y border-black/10 bg-white py-5"
      aria-label="What Heimdall covers"
    >
      <div className="hd-marquee flex w-max gap-10 whitespace-nowrap">
        {row.map((t, i) => (
          <span
            key={i}
            aria-hidden={i >= items.length}
            className="flex items-center gap-10 text-2xl font-semibold tracking-tight text-black/80"
          >
            {t}
            <span className="size-2 rounded-full bg-gradient-to-r from-indigo-500 to-amber-400" />
          </span>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Problem (stats)                                                     */
/* ------------------------------------------------------------------ */

function Counter({
  to,
  decimals = 0,
  prefix = "",
  suffix = "",
}: {
  to: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!inView) return;
    const controls = animate(0, to, {
      duration: 1.6,
      ease: "easeOut",
      onUpdate: (v) => setValue(v),
    });
    return () => controls.stop();
  }, [inView, to]);
  return (
    <span ref={ref}>
      {prefix}
      {value.toLocaleString("en-IN", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}

function Problem() {
  const stats = [
    {
      n: 11581,
      label:
        "ad complaints reviewed by ASCI, India's advertising regulator, in 2025-26 — up 21% in a year",
      src: "ASCI 2025-26",
    },
    {
      n: 10,
      prefix: "₹",
      suffix: " lakh",
      label:
        "penalty cap for one misleading advertisement in India, ₹50 lakh for repeats",
      src: "Consumer Protection Act, 2019",
    },
    {
      n: 81,
      suffix: "%",
      label: "of companies say they deal with off-brand content",
      src: "Lucidpress, 2019",
    },
    {
      n: 83.9,
      decimals: 1,
      suffix: "%",
      label: "of the top million home pages have low-contrast text",
      src: "WebAIM Million 2026",
    },
  ];
  return (
    <section className="hd-grid-bg-light relative bg-white py-28">
      <div className="mx-auto max-w-6xl px-4">
        <Reveal>
          <Kicker>The problem</Kicker>
          <h2 className="mt-3 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
            Content comes from everyone now. Nobody can check all of it.
          </h2>
          <p className="mt-5 max-w-2xl text-lg text-black/70">
            Employees, agencies and AI tools publish faster than any brand
            manager can read. Wrong claims, outdated prices, off-brand words and
            inaccessible visuals slip through — and the cost is real.
          </p>
        </Reveal>
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s, i) => (
            <Reveal key={s.label} delay={i * 0.08}>
              <div className="hd-lift h-full rounded-2xl border border-black/10 bg-white p-6">
                <p className="text-4xl font-bold tracking-tight">
                  <Counter
                    to={s.n}
                    decimals={s.decimals}
                    prefix={s.prefix}
                    suffix={s.suffix}
                  />
                </p>
                <p className="mt-3 text-sm text-black/70">{s.label}</p>
                <p className="mt-3 text-xs text-black/60">{s.src}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* How it works (scroll-linked progress)                               */
/* ------------------------------------------------------------------ */

function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 70%", "end 60%"],
  });
  const fill = useSpring(scrollYProgress, { stiffness: 120, damping: 30 });
  const steps = [
    {
      icon: Upload,
      who: "Admin",
      title: "Set the rules",
      text: "Upload your brand guideline (PDF, Word, PowerPoint, text or CSV). Heimdall splits it into one rule per instruction, checks the rulebook itself for duplicates, contradictions and vague rules, and waits for your approval. Add approved facts with expiry dates.",
    },
    {
      icon: FileSearch,
      who: "Creator",
      title: "Upload a draft",
      text: "Paste a script or upload a PDF, image or short video. Sensitive details are masked before any AI sees it.",
    },
    {
      icon: ShieldCheck,
      who: "Heimdall",
      title: "Flag with a source",
      text: "Exact rules run in code; tone, claims and visuals are checked by AI against your approved rules and facts. Every flag quotes the words, cites its rule or fact, and suggests a fix.",
    },
    {
      icon: PenLine,
      who: "Creator",
      title: "Fix in one round",
      text: "Accept fixes, reword them, or dismiss a flag with a reason — then send it on. Most problems are gone before a manager ever looks.",
    },
    {
      icon: UserCheck,
      who: "Manager",
      title: "Approve or send back",
      text: "See only what is left, with every reason on record. Approve, request changes, or approve an exception that Heimdall remembers.",
    },
  ];
  return (
    <section id="how" className="bg-black py-28 text-white">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 lg:grid-cols-[1fr_1.3fr]">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <Reveal>
            <Kicker dark>How it works</Kicker>
            <h2 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
              From draft to approved, with nothing unchecked.
            </h2>
            <p className="mt-5 text-lg text-white/70">
              Five steps. AI advises; people decide. Every version, decision and
              reason is saved.
            </p>
          </Reveal>
        </div>
        <div ref={ref} className="relative pl-10">
          <div className="absolute top-2 bottom-2 left-3 w-px bg-white/15" />
          <motion.div
            style={{ scaleY: fill }}
            className="absolute top-2 bottom-2 left-3 w-px origin-top bg-gradient-to-b from-indigo-400 via-fuchsia-400 to-amber-300"
          />
          <ol className="space-y-8">
            {steps.map((s, i) => (
              <motion.li
                key={s.title}
                initial={{ opacity: 0, y: 28 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.7, delay: i * 0.05, ease }}
                className="relative rounded-2xl border border-white/10 bg-white/[0.04] p-6 transition-colors hover:border-white/25 hover:bg-white/[0.07]"
              >
                <span className="absolute top-7 -left-[2.15rem] flex size-6 items-center justify-center rounded-full bg-white text-xs font-bold text-black">
                  {i + 1}
                </span>
                <div className="flex items-center gap-3">
                  <s.icon className="size-5 text-amber-300" aria-hidden />
                  <p className="text-xs font-semibold tracking-[0.2em] text-white/60 uppercase">
                    {s.who}
                  </p>
                </div>
                <h3 className="mt-2 text-xl font-semibold">{s.title}</h3>
                <p className="mt-2 text-white/70">{s.text}</p>
              </motion.li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Features (bento with cursor spotlight)                              */
/* ------------------------------------------------------------------ */

function Spot({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--x", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--y", `${e.clientY - r.top}px`);
      }}
      className={cn(
        "hd-spotlight h-full rounded-3xl border border-white/10 bg-white/[0.04] p-7 transition-colors hover:border-white/25",
        className,
      )}
    >
      {children}
    </div>
  );
}

function Features() {
  const items = [
    {
      icon: Layers,
      color: "text-indigo-300",
      title: "Guidelines become rules",
      text: "One record per rule with its page. Banned words and required lines are checked in code; everything else by AI. The guideline itself is checked first.",
      span: "lg:col-span-2",
    },
    {
      icon: BadgeCheck,
      color: "text-emerald-300",
      title: "Facts with a shelf life",
      text: "Approved prices, statistics and names with a source and a valid-until date. Expired facts are flagged automatically.",
    },
    {
      icon: Globe,
      color: "text-cyan-300",
      title: "Website fact check",
      text: "Reads your site, shows what changed (₹95 → ₹99) and updates facts only when you approve.",
    },
    {
      icon: Film,
      color: "text-pink-300",
      title: "Text, PDF, image and video",
      text: "Flags land exactly where the problem is: a highlighted phrase, a box on the PDF page, a region of the image, a moment on the video timeline.",
      span: "lg:col-span-2",
    },
    {
      icon: Code2,
      color: "text-amber-300",
      title: "No source, no flag",
      text: "Plain code removes any AI finding whose rule wasn't supplied or whose quote isn't in your content.",
    },
    {
      icon: MessageSquare,
      color: "text-violet-300",
      title: "Review and approval",
      text: "Comments, version history with a word-level diff, role-based workflow and a full audit log.",
    },
    {
      icon: BarChart3,
      color: "text-lime-300",
      title: "Insights and guideline health",
      text: "Recurring problems over time, the most-broken rules, and rules people keep dismissing — so you can rewrite them.",
    },
    {
      icon: Library,
      color: "text-orange-300",
      title: "Asset library",
      text: "Approved logos and disclaimers that the image checks know about.",
    },
    {
      icon: EyeOff,
      color: "text-rose-300",
      title: "Private by design",
      text: "Emails, phone numbers, IDs, names and your confidential terms are masked before any AI call. Every AI use is disclosed.",
      span: "lg:col-span-2",
    },
  ];
  return (
    <section id="features" className="relative bg-black pb-28 text-white">
      <div className="mx-auto max-w-6xl px-4">
        <Reveal>
          <Kicker dark>Features</Kicker>
          <h2 className="mt-3 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
            Everything a brand team needs at the checkpoint.
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((f, i) => (
            <Reveal key={f.title} delay={(i % 4) * 0.06} className={f.span}>
              <Spot>
                <f.icon className={cn("size-7", f.color)} aria-hidden />
                <h3 className="mt-5 text-lg font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/70">
                  {f.text}
                </p>
              </Spot>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* No source, no flag (live demo)                                      */
/* ------------------------------------------------------------------ */

function SourceDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-120px" });
  const checks = [
    "The cited fact F-001 was supplied to the AI",
    "The quoted words are really in the script",
    "No approved exception covers this wording",
  ];
  return (
    <section className="relative overflow-hidden bg-white py-28">
      <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 lg:grid-cols-2">
        <Reveal>
          <Kicker>Trust, enforced in code</Kicker>
          <h2 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            No source, no flag.
          </h2>
          <p className="mt-5 text-lg text-black/70">
            AI can sound right while quoting words that aren&rsquo;t there or
            citing rules that don&rsquo;t exist. Heimdall checks every AI
            finding with plain code before anyone sees it. If the source
            doesn&rsquo;t hold up, the flag never appears.
          </p>
          <ul className="mt-8 space-y-3">
            {checks.map((c, i) => (
              <motion.li
                key={c}
                initial={{ opacity: 0, x: -16 }}
                animate={inView ? { opacity: 1, x: 0 } : {}}
                transition={{ delay: 0.6 + i * 0.35, duration: 0.5, ease }}
                className="flex items-center gap-3 text-black/80"
              >
                <CheckCircle2 className="size-5 text-emerald-600" aria-hidden />
                {c}
              </motion.li>
            ))}
          </ul>
        </Reveal>
        <div ref={ref} className="relative">
          <div className="absolute -inset-6 rounded-[2rem] bg-gradient-to-br from-indigo-200/60 via-white to-amber-100/70 blur-2xl" />
          <div className="relative rounded-3xl border border-black/10 bg-white p-6 shadow-[0_30px_80px_-40px_rgba(0,0,0,0.45)]">
            <p className="text-xs font-semibold tracking-[0.2em] text-black/60 uppercase">
              TV ad script · draft 3
            </p>
            <p className="mt-4 text-lg leading-relaxed">
              Introducing Active Shield, the toothpaste that{" "}
              <motion.mark
                initial={{ backgroundColor: "rgba(0,0,0,0)" }}
                animate={
                  inView ? { backgroundColor: "rgba(244,63,94,0.18)" } : {}
                }
                transition={{ delay: 0.3, duration: 0.6 }}
                className="rounded px-0.5 text-black underline decoration-rose-500 decoration-2 underline-offset-4"
              >
                kills 99.9% of germs
              </motion.mark>{" "}
              and keeps your smile fresh all day.
            </p>
            <motion.div
              initial={{ opacity: 0, y: 24, scale: 0.97 }}
              animate={inView ? { opacity: 1, y: 0, scale: 1 } : {}}
              transition={{ delay: 1.7, duration: 0.6, ease }}
              className="mt-6 rounded-2xl border border-black/10 border-l-4 border-l-rose-500 bg-white p-4 text-sm shadow-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">
                  High
                </span>
                <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs">
                  Claims
                </span>
                <span className="rounded-md border border-black/10 px-2 py-0.5 font-mono text-xs">
                  F-001
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-black/60">
                  <Bot className="size-3.5" aria-hidden /> AI used
                </span>
              </div>
              <p className="mt-2 text-black/80">
                Fact F-001 says Active Shield fights 99% of mouth germs in lab
                tests, not 99.9%.
              </p>
              <p className="mt-2">
                <span className="font-semibold">Suggested fix:</span> kills 99%
                of germs
              </p>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Who it's for                                                        */
/* ------------------------------------------------------------------ */

function Teams() {
  const people = [
    {
      icon: PenLine,
      tint: "from-indigo-500/15",
      title: "Content creators",
      who: "Employees, agencies and freelancers who write and design.",
      gets: [
        "Feedback in under a minute",
        "The exact rule behind every issue",
        "A suggested fix that keeps your intent",
      ],
    },
    {
      icon: ClipboardCheck,
      tint: "from-amber-400/20",
      title: "Brand and marketing managers",
      who: "The people who approve content before it goes out.",
      gets: [
        "Only unresolved issues to review",
        "Approve or send back in one place",
        "Every decision recorded with its reason",
      ],
    },
    {
      icon: Users,
      tint: "from-emerald-400/20",
      title: "Brand admins",
      who: "Owners of guidelines, facts and assets — brand, legal or compliance.",
      gets: [
        "One maintained source of truth",
        "A check on the guidelines themselves",
        "Insight into recurring problems",
      ],
    },
  ];
  return (
    <section id="teams" className="hd-grid-bg-light bg-white py-28">
      <div className="mx-auto max-w-6xl px-4">
        <Reveal>
          <Kicker>Who it&rsquo;s for</Kicker>
          <h2 className="mt-3 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
            Made for every team that publishes in your brand&rsquo;s name.
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {people.map((p, i) => (
            <Reveal key={p.title} delay={i * 0.1}>
              <motion.div
                whileHover={{
                  y: -8,
                  rotate: i === 1 ? 0 : i === 0 ? -0.6 : 0.6,
                }}
                transition={{ type: "spring", stiffness: 260, damping: 20 }}
                className={cn(
                  "h-full rounded-3xl border border-black/10 bg-gradient-to-b to-white p-7",
                  p.tint,
                )}
              >
                <p.icon className="size-7" aria-hidden />
                <h3 className="mt-5 text-xl font-semibold">{p.title}</h3>
                <p className="mt-2 text-sm text-black/70">{p.who}</p>
                <ul className="mt-5 space-y-2 text-sm">
                  {p.gets.map((g) => (
                    <li key={g} className="flex items-start gap-2">
                      <CheckCircle2
                        className="mt-0.5 size-4 shrink-0"
                        aria-hidden
                      />
                      {g}
                    </li>
                  ))}
                </ul>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Formats + privacy                                                   */
/* ------------------------------------------------------------------ */

function Privacy() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-120px" });
  const [masked, setMasked] = useState(false);
  useEffect(() => {
    if (!inView) return;
    const t = setTimeout(() => setMasked(true), 900);
    return () => clearTimeout(t);
  }, [inView]);
  const pieces: [string, string][] = [
    ["priya.sharma@example.com", "[EMAIL]"],
    ["98201 45678", "[PHONE]"],
    ["Project Neelkanth", "[CONFIDENTIAL]"],
  ];
  const formats = [
    { icon: FileText, label: "Text & scripts" },
    { icon: FileText, label: "PDF documents" },
    { icon: ImageIcon, label: "Images & posters" },
    { icon: Film, label: "Short videos" },
  ];
  return (
    <section className="bg-black py-28 text-white">
      <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 lg:grid-cols-2">
        <div
          ref={ref}
          className="rounded-3xl border border-white/10 bg-white/[0.04] p-7"
        >
          <p className="text-xs font-semibold tracking-[0.2em] text-white/60 uppercase">
            Before any AI call
          </p>
          <p className="mt-4 text-lg leading-relaxed text-white/90">
            Call{" "}
            {pieces.map(([raw, mask], i) => (
              <span key={raw}>
                <motion.span
                  key={masked ? mask : raw}
                  initial={{ opacity: 0, filter: "blur(6px)" }}
                  animate={{ opacity: 1, filter: "blur(0px)" }}
                  transition={{ duration: 0.5, delay: i * 0.25 }}
                  className={cn(
                    "rounded px-1 font-mono text-base",
                    masked
                      ? "bg-emerald-400/15 text-emerald-200"
                      : "bg-rose-400/15 text-rose-200",
                  )}
                >
                  {masked ? mask : raw}
                </motion.span>
                {i === 0
                  ? " or "
                  : i === 1
                    ? " about the new formula from "
                    : "."}
              </span>
            ))}
          </p>
          <p className="mt-5 flex items-center gap-2 text-sm text-white/70">
            <ShieldCheck className="size-4 text-emerald-300" aria-hidden />
            Emails, phone numbers, PAN, Aadhaar, card numbers, names, places and
            your confidential terms are masked.
          </p>
        </div>
        <Reveal>
          <Kicker dark>Privacy and transparency</Kicker>
          <h2 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            Your drafts stay yours.
          </h2>
          <p className="mt-5 text-lg text-white/70">
            Only masked excerpts reach an AI model. Every flag says whether code
            or which AI model found it, and a disclosure page lists each
            service, what it receives and how often it was called.
          </p>
          <div className="mt-8 grid grid-cols-2 gap-3">
            {formats.map((f) => (
              <div
                key={f.label}
                className="flex items-center gap-3 rounded-2xl border border-white/10 px-4 py-3 text-sm"
              >
                <f.icon className="size-4 text-white/70" aria-hidden />
                {f.label}
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* CTA + footer                                                        */
/* ------------------------------------------------------------------ */

function Cta() {
  return (
    <section className="relative overflow-hidden bg-white py-32">
      <motion.div
        aria-hidden
        className="absolute top-1/2 left-1/2 size-[44rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[conic-gradient(from_0deg,#6366f1,#22d3ee,#34d399,#f5b544,#f472b6,#6366f1)] opacity-20 blur-3xl"
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 30, ease: "linear" }}
      />
      <Reveal className="relative mx-auto max-w-3xl px-4 text-center">
        <BrandMark size={52} />
        <h2 className="mt-6 text-5xl font-bold tracking-tight sm:text-6xl">
          Guard your brand.
          <br />
          Let nothing cross unchecked.
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-lg text-black/70">
          Set up your rules once. Every draft after that gets checked in under a
          minute, with a source for every issue.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Link
            href="/signup"
            className="group inline-flex items-center gap-2 rounded-full bg-black px-7 py-3.5 text-sm font-semibold text-white transition-transform hover:scale-[1.03] active:scale-95"
          >
            Sign up
            <ArrowRight
              className="size-4 transition-transform group-hover:translate-x-1"
              aria-hidden
            />
          </Link>
          <Link
            href="/login"
            className="rounded-full border border-black/15 bg-white px-7 py-3.5 text-sm font-semibold transition-colors hover:bg-black/5"
          >
            Sign in
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bg-black py-12 text-white/70">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 text-white">
          <BrandMark tone="light" />
          <span className="font-semibold">Heimdall</span>
          <span className="text-white/60">· Nothing crosses unchecked.</span>
        </div>
        <p className="text-sm">
          Built by Team Nobita&amp;Avaneja · Inkloom AI problem statement
        </p>
        <div className="flex items-center gap-4 text-sm">
          <a
            href="https://github.com/aayush-tech2055/heimdall"
            className="inline-flex items-center gap-1.5 hover:text-white"
          >
            <History className="size-4" aria-hidden /> Source code
          </a>
          <Link href="/login" className="hover:text-white">
            Sign in
          </Link>
        </div>
      </div>
    </footer>
  );
}

function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const x = useSpring(scrollYProgress, { stiffness: 140, damping: 30 });
  return (
    <motion.div
      aria-hidden
      style={{ scaleX: x }}
      className="fixed inset-x-0 top-0 z-[60] h-0.5 origin-left bg-gradient-to-r from-indigo-500 via-fuchsia-500 to-amber-400"
    />
  );
}

export function Landing() {
  return (
    <MotionConfig reducedMotion="user">
      <ScrollProgress />
      <Nav />
      <Hero />
      <Marquee />
      <Problem />
      <HowItWorks />
      <Features />
      <SourceDemo />
      <Teams />
      <Privacy />
      <Cta />
      <Footer />
    </MotionConfig>
  );
}
