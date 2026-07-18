"use client";
import { motion } from "motion/react";
import Link from "next/link";
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Telescope,
  GitBranch,
  RefreshCw,
  ArrowRight,
} from "lucide-react";
import { getBriefing } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { ErrorState } from "@/components/States";
import Sparkline from "@/components/Sparkline";
import type { Briefing, BriefingMetric } from "@/lib/types";

const COLOR = { good: "#34D399", bad: "#F87171", neutral: "#9BA3B4" } as const;

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function BriefingPage() {
  const { data: b, loading, error, reload } = useResource<Briefing>(() =>
    getBriefing(),
  );

  if (loading)
    return (
      <main className="grid min-h-screen place-items-center text-ink-dim">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-indigo" />
          Nexus is analysing your business…
        </div>
      </main>
    );

  if (error)
    return (
      <main className="mx-auto max-w-3xl px-4 pt-28">
        <ErrorState message={error.message} onRetry={reload} />
      </main>
    );

  if (!b?.available)
    return (
      <main className="mx-auto max-w-3xl px-4 pb-20 pt-28 text-center">
        <h1 className="text-2xl font-semibold">Daily Briefing</h1>
        <p className="mt-3 text-ink-dim">
          {b?.reason || "No time-series data to brief on for this connection."}
        </p>
      </main>
    );

  return (
    <main className="mx-auto max-w-4xl px-4 pb-24 pt-28">
      {/* header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1 text-xs text-ink-dim">
            <Sparkles className="h-3.5 w-3.5 text-indigo" /> Proactive · as of {b.as_of}
          </span>
          <button
            onClick={reload}
            className="focus-ring flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs text-ink-dim hover:text-ink"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">
          {greeting()}. Here&apos;s what changed.
        </h1>
        <p className="mt-3 max-w-2xl text-lg leading-relaxed text-ink">{b.headline}</p>
      </motion.div>

      {/* metric snapshot */}
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-faint">
          Metric snapshot
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {b.metrics.map((m, i) => (
            <MetricCard key={m.column} m={m} delay={i * 0.05} />
          ))}
        </div>
      </section>

      {/* what changed & why */}
      <section className="mt-10">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-faint">
          <GitBranch className="h-4 w-4 text-indigo" /> What changed & why
        </h2>
        <div className="flex flex-col gap-3">
          {b.what_changed.map((w, i) => (
            <motion.div
              key={w.label}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="card p-4"
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: COLOR[w.sentiment as keyof typeof COLOR] || COLOR.neutral }}
                />
                <span className="font-medium">{w.label}</span>
                <span
                  className="ml-auto font-mono text-sm"
                  style={{ color: COLOR[w.sentiment as keyof typeof COLOR] || COLOR.neutral }}
                >
                  {w.mom_pct > 0 ? "+" : ""}
                  {w.mom_pct}%
                </span>
              </div>
              <p className="mt-1.5 text-sm text-ink-dim">{w.narrative}</p>
              {w.rootcause?.available && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {w.rootcause.contributors.slice(0, 4).map((c) => (
                    <span
                      key={c.member}
                      className="rounded-md border border-line bg-surface/60 px-2 py-0.5 font-mono text-[11px]"
                      style={{ color: c.delta >= 0 ? COLOR.good : COLOR.bad }}
                    >
                      {c.member} {c.delta >= 0 ? "+" : ""}
                      {Math.round(c.delta).toLocaleString()}
                    </span>
                  ))}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </section>

      {/* watchouts + outlook */}
      <div className="mt-10 grid gap-6 md:grid-cols-2">
        <section>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-faint">
            <AlertTriangle className="h-4 w-4 text-amber" /> Watchouts
          </h2>
          <div className="flex flex-col gap-2">
            {b.watchouts.length === 0 && (
              <p className="text-sm text-ink-faint">Nothing flagged — all clear.</p>
            )}
            {b.watchouts.map((w, i) => (
              <div
                key={i}
                className={`card border-l-2 p-3 text-sm ${
                  w.severity === "high" ? "border-l-neg" : "border-l-amber"
                }`}
              >
                {w.message}
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-faint">
            <Telescope className="h-4 w-4 text-indigo" /> Forecast outlook
          </h2>
          <div className="card gradient-border relative p-4">
            <p className="text-sm text-ink">
              {b.forecast_outlook || "Not enough data to forecast."}
            </p>
            <Link
              href="/app?q=Show monthly merchandise revenue over time"
              className="mt-3 inline-flex items-center gap-1.5 text-xs text-cyan hover:underline"
            >
              Explore the trend in the workspace <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </section>
      </div>

      <p className="mt-8 text-center text-[11px] text-ink-faint">{b.generated_note}</p>
    </main>
  );
}

function MetricCard({ m, delay }: { m: BriefingMetric; delay: number }) {
  const Icon = m.direction === "up" ? TrendingUp : m.direction === "down" ? TrendingDown : Minus;
  const c = COLOR[m.sentiment];
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="card relative p-4"
    >
      {m.anomaly && (
        <span className="absolute right-3 top-3 flex items-center gap-1 rounded-full bg-amber/15 px-1.5 py-0.5 text-[10px] text-amber">
          <AlertTriangle className="h-3 w-3" /> anomaly
        </span>
      )}
      <p className="text-xs text-ink-dim">{m.label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold">{m.value_fmt}</p>
      <div className="mt-2 flex items-end justify-between">
        <span className="flex items-center gap-1 text-sm" style={{ color: c }}>
          <Icon className="h-3.5 w-3.5" />
          {m.mom_pct > 0 ? "+" : ""}
          {m.mom_pct}%
        </span>
        <Sparkline values={m.spark} color={c} />
      </div>
    </motion.div>
  );
}
