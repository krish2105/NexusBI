"use client";
import Link from "next/link";
import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import {
  ArrowRight,
  Bell,
  Brain,
  Database,
  GitBranch,
  LayoutDashboard,
  LineChart,
  Lock,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import Hero from "@/components/Hero";
import Magnetic from "@/components/motion/Magnetic";
import Counter from "@/components/motion/Counter";
import SplitWords from "@/components/motion/SplitWords";

const reveal = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] as const },
};

const STEPS = [
  { icon: Brain, title: "Plans & grounds", body: "A multi-agent graph decomposes your question and retrieves the real schema + business glossary — never guessing column names." },
  { icon: ShieldCheck, title: "Writes safe SQL", body: "A five-layer text-to-SQL guard proves the query is a read-only SELECT before it ever runs. Destructive queries are impossible by construction." },
  { icon: LineChart, title: "Forecasts & narrates", body: "Deterministic ML forecasts the trend and flags anomalies; the LLM only narrates — so every number is real and reproducible." },
];

const CAPABILITIES = [
  { icon: ShieldCheck, label: "5-layer SQL guard" },
  { icon: LineChart, label: "Holt-Winters + LSTM forecasts" },
  { icon: Users, label: "RFM customer segments" },
  { icon: GitBranch, label: "Root-cause analysis" },
  { icon: LayoutDashboard, label: "NL → dashboards" },
  { icon: Bell, label: "Monitors & alerts" },
  { icon: ScrollText, label: "Append-only audit log" },
  { icon: Database, label: "Postgres · MySQL · SQLite · CSV" },
];

/** Cursor spotlight: feed the card's ::after gradient its pointer position. */
function spotlightMove(e: React.MouseEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
}

function MarqueeRow() {
  const items = CAPABILITIES.map(({ icon: Icon, label }) => (
    <span
      key={label}
      className="flex shrink-0 items-center gap-2 rounded-full border border-line bg-surface/70 px-4 py-1.5 text-sm text-ink-dim"
    >
      <Icon className="h-3.5 w-3.5 text-indigo" aria-hidden />
      {label}
    </span>
  ));
  return (
    <div className="marquee py-2" aria-hidden>
      <div className="marquee-track">{items}</div>
      <div className="marquee-track">{items}</div>
    </div>
  );
}

export default function Landing() {
  const reduced = useReducedMotion();
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const visualY = useTransform(scrollYProgress, [0, 1], [0, 60]);
  const visualOpacity = useTransform(scrollYProgress, [0, 0.9], [1, 0.4]);

  return (
    <main className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      {/* Aurora backdrop — transform/opacity only, masked to the hero area */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[52rem] overflow-hidden">
        <div className="aurora aurora-a left-[-10%] top-[-16%] h-[34rem] w-[38rem]" />
        <div className="aurora aurora-b right-[-12%] top-[6%] h-[30rem] w-[34rem]" />
      </div>

      {/* Hero */}
      <section
        ref={heroRef}
        className="relative mx-auto grid max-w-6xl grid-cols-1 items-center gap-8 px-4 pb-12 pt-32 lg:grid-cols-2 lg:pt-40"
      >
        <div>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="glass mb-5 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-ink-dim"
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan" />
            Agentic Decision Intelligence · bounded autonomy
          </motion.div>
          <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            <SplitWords text="Ask your data" delay={0.1} />
            <br />
            <span className="inline-block overflow-hidden pb-[0.12em] align-bottom">
              <motion.span
                className="gradient-text inline-block will-change-transform"
                initial={reduced ? false : { y: "110%" }}
                animate={{ y: 0 }}
                transition={{ delay: 0.32, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              >
                anything.
              </motion.span>
            </span>
          </h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.35 }}
            className="mt-5 max-w-md text-lg text-ink-dim"
          >
            Nexus writes the SQL, runs the numbers, forecasts what&apos;s next, and
            tells you what it means — in seconds. No analyst required.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.45 }}
            className="mt-8 flex flex-wrap items-center gap-3"
          >
            <Magnetic>
              <Link
                href="/app"
                className="focus-ring group relative flex items-center gap-2 overflow-hidden rounded-xl bg-ai-gradient px-5 py-3 font-medium text-white shadow-glow"
              >
                {/* shine sweep on hover */}
                <span
                  aria-hidden
                  className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
                />
                Launch the workspace
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Magnetic>
            <Link
              href="/connections"
              className="focus-ring flex items-center gap-2 rounded-xl border border-line px-5 py-3 text-ink-dim transition-colors hover:border-ink-faint hover:text-ink"
            >
              <Database className="h-4 w-4" /> Explore the data
            </Link>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, delay: 0.2 }}
          style={reduced ? undefined : { y: visualY, opacity: visualOpacity }}
          className="relative aspect-[720/420] w-full"
        >
          <Hero />
        </motion.div>
      </section>

      {/* Capability marquee */}
      <motion.section {...reveal} className="relative mx-auto max-w-6xl px-4 pb-4">
        <MarqueeRow />
      </motion.section>

      {/* Stats */}
      <section className="relative mx-auto max-w-6xl px-4 py-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            {
              k: <Counter to={100} suffix="%" className="gradient-text" />,
              v: "adversarial queries blocked in eval",
            },
            {
              k: <Counter to={99441} className="gradient-text" />,
              v: "real Olist orders, live",
            },
            { k: <span className="gradient-text">5-layer</span>, v: "text-to-SQL safety" },
            { k: <span className="gradient-text">$0</span>, v: "free-tier, no billed keys" },
          ].map((s, i) => (
            <motion.div
              key={s.v}
              {...reveal}
              transition={{ ...reveal.transition, delay: i * 0.06 }}
              whileHover={{ y: -3 }}
              className="card p-5"
            >
              <p className="font-mono text-2xl font-semibold">{s.k}</p>
              <p className="mt-1 text-xs text-ink-dim">{s.v}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="relative mx-auto max-w-6xl px-4 py-20">
        <motion.h2 {...reveal} className="text-center text-3xl font-semibold tracking-tight">
          From question to decision in <span className="gradient-text">five seconds</span>
        </motion.h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.title}
              {...reveal}
              transition={{ ...reveal.transition, delay: i * 0.1 }}
              whileHover={{ y: -4 }}
              onMouseMove={spotlightMove}
              className="card gradient-border spotlight relative p-6"
            >
              <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-ai-gradient shadow-glow">
                <s.icon className="h-5 w-5 text-white" />
              </span>
              <h3 className="text-lg font-medium">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-dim">{s.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Safety highlight */}
      <section className="relative mx-auto max-w-6xl px-4 pb-24">
        <motion.div {...reveal} className="card gradient-border relative overflow-hidden p-8 md:p-12">
          <div className="flex flex-col items-start gap-6 md:flex-row md:items-center md:justify-between">
            <div className="max-w-xl">
              <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-pos/30 bg-pos/10 px-3 py-1 text-xs font-medium text-pos">
                <Lock className="h-3.5 w-3.5" /> Safety is non-negotiable
              </span>
              <h3 className="text-2xl font-semibold tracking-tight">
                Destructive queries are impossible by construction
              </h3>
              <p className="mt-3 text-ink-dim">
                Read-only role · <code className="text-cyan">sqlglot</code> AST allow-listing ·
                table/column verification · NL-injection defense · a capped repair loop
                that never executes unvalidated SQL. The worst case is a query that
                returns nothing — never one that harms the database.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              {["read-only role", "AST validation", "allow-list + LIMIT", "NL injection screen", "dry-run + repair"].map(
                (l, i) => (
                  <motion.div
                    key={l}
                    initial={{ opacity: 0, x: 16 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: "-60px" }}
                    transition={{ delay: 0.15 + i * 0.08, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span className="grid h-6 w-6 place-items-center rounded-full border border-pos/40 bg-pos/10 text-[11px] text-pos">
                      L{i + 1}
                    </span>
                    <span className="text-ink-dim">{l}</span>
                  </motion.div>
                ),
              )}
            </div>
          </div>
        </motion.div>
      </section>

      <footer className="relative border-t border-line py-8 text-center text-xs text-ink-faint">
        <p className="flex items-center justify-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-indigo" /> Nexus BI · built on the real
          Olist e-commerce dataset · free-tier native
        </p>
      </footer>
    </main>
  );
}
