"use client";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowRight,
  ShieldCheck,
  Brain,
  LineChart,
  Database,
  Sparkles,
  Lock,
} from "lucide-react";
import Hero from "@/components/Hero";

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

const STATS = [
  { k: "100%", v: "adversarial queries blocked in eval" },
  { k: "99,441", v: "real Olist orders, live" },
  { k: "5-layer", v: "text-to-SQL safety" },
  { k: "$0", v: "free-tier, no billed keys" },
];

export default function Landing() {
  return (
    <main className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />

      {/* Hero */}
      <section className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-8 px-4 pb-16 pt-32 lg:grid-cols-2 lg:pt-40">
        <div>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1 text-xs text-ink-dim"
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan" />
            Agentic Decision Intelligence · bounded autonomy
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.05 }}
            className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl"
          >
            Ask your data
            <br />
            <span className="gradient-text">anything.</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="mt-5 max-w-md text-lg text-ink-dim"
          >
            Nexus writes the SQL, runs the numbers, forecasts what&apos;s next, and
            tells you what it means — in seconds. No analyst required.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25 }}
            className="mt-8 flex flex-wrap items-center gap-3"
          >
            <Link
              href="/app"
              className="focus-ring group flex items-center gap-2 rounded-xl bg-ai-gradient px-5 py-3 font-medium text-white shadow-glow"
            >
              Launch the workspace
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/connections"
              className="focus-ring flex items-center gap-2 rounded-xl border border-line px-5 py-3 text-ink-dim hover:text-ink"
            >
              <Database className="h-4 w-4" /> Explore the data
            </Link>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, delay: 0.2 }}
          className="relative aspect-[720/420] w-full"
        >
          <Hero />
        </motion.div>
      </section>

      {/* Stats */}
      <section className="mx-auto max-w-6xl px-4 py-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {STATS.map((s, i) => (
            <motion.div key={s.v} {...reveal} transition={{ ...reveal.transition, delay: i * 0.06 }} className="card p-5">
              <p className="font-mono text-2xl font-semibold gradient-text">{s.k}</p>
              <p className="mt-1 text-xs text-ink-dim">{s.v}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-6xl px-4 py-20">
        <motion.h2 {...reveal} className="text-center text-3xl font-semibold tracking-tight">
          From question to decision in <span className="gradient-text">five seconds</span>
        </motion.h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.title}
              {...reveal}
              transition={{ ...reveal.transition, delay: i * 0.1 }}
              className="card gradient-border relative p-6"
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
      <section className="mx-auto max-w-6xl px-4 pb-24">
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
                  <div key={l} className="flex items-center gap-2 text-sm">
                    <span className="grid h-6 w-6 place-items-center rounded-full border border-pos/40 bg-pos/10 text-[11px] text-pos">
                      L{i + 1}
                    </span>
                    <span className="text-ink-dim">{l}</span>
                  </div>
                ),
              )}
            </div>
          </div>
        </motion.div>
      </section>

      <footer className="border-t border-line py-8 text-center text-xs text-ink-faint">
        <p className="flex items-center justify-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-indigo" /> Nexus BI · built on the real
          Olist e-commerce dataset · free-tier native
        </p>
      </footer>
    </main>
  );
}
