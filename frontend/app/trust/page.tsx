"use client";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import {
  ShieldCheck,
  Lock,
  Scale,
  ThumbsUp,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { getTrust } from "@/lib/api";

const reveal = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.5 },
};

export default function Trust() {
  const [t, setT] = useState<any>(null);
  useEffect(() => {
    getTrust().then(setT).catch(() => {});
  }, []);
  if (!t) return <main className="pt-28 text-center text-ink-dim">Loading…</main>;

  const pct = (v: any) => (v == null ? "—" : `${Math.round(v * 100)}%`);
  const safety = t.safety || {};
  const acc = t.accuracy || {};
  const gov = t.governance || {};
  const fb = t.feedback || {};

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <div className="inline-flex items-center gap-2 rounded-full border border-pos/30 bg-pos/10 px-3 py-1 text-xs font-medium text-pos">
        <Lock className="h-3.5 w-3.5" /> Trust Center
      </div>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">
        Why you can trust the answers
      </h1>
      <p className="mt-2 max-w-2xl text-ink-dim">
        Nexus is decision-intelligence software, not a chatbot. The LLM plans and
        narrates; the database and deterministic ML compute every number — and
        every query is guarded, logged, and measured.
      </p>

      {/* headline metrics */}
      <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Adversarial blocked" value={pct(safety.block_rate)} sub={`${safety.adversarial_blocked ?? 0}/${safety.adversarial_total ?? 0} cases`} good />
        <Metric label="Data integrity" value={pct(acc.data_integrity_rate)} sub="validated SQL vs labels" good />
        <Metric label="Forecast MAPE" value={acc.forecast_mape_pct != null ? `${acc.forecast_mape_pct}%` : "—"} sub="3-month backtest" />
        <Metric label="RAG table recall" value={pct(acc.rag_table_recall)} sub="schema grounding" />
      </div>

      {/* principles */}
      <section className="mt-10 grid gap-4 md:grid-cols-2">
        <motion.div {...reveal} className="card p-6">
          <h2 className="flex items-center gap-2 text-lg font-medium">
            <ShieldCheck className="h-5 w-5 text-pos" /> Bounded autonomy
          </h2>
          <ul className="mt-3 space-y-2">
            {(t.principles || []).map((p: string) => (
              <li key={p} className="flex items-start gap-2 text-sm text-ink-dim">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-pos" />
                {p}
              </li>
            ))}
          </ul>
        </motion.div>

        <motion.div {...reveal} className="card p-6">
          <h2 className="flex items-center gap-2 text-lg font-medium">
            <Scale className="h-5 w-5 text-indigo" /> Governance (this instance)
          </h2>
          <div className="mt-4 grid grid-cols-3 gap-3 text-center">
            <Stat n={gov.queries_executed ?? 0} l="executed" />
            <Stat n={gov.queries_blocked ?? 0} l="blocked" tone="neg" />
            <Stat n={gov.audit_entries ?? 0} l="audit log" />
          </div>
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-line bg-surface/50 px-3 py-2 text-xs text-ink-dim">
            <ThumbsUp className="h-4 w-4 text-pos" />
            {fb.total > 0
              ? `${Math.round((fb.satisfaction_rate || 0) * 100)}% satisfaction across ${fb.total} ratings`
              : "No feedback yet — rate answers in the workspace."}
          </div>
        </motion.div>
      </section>

      {/* safety eval detail */}
      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">
          Safety red-team — every adversarial case & the control that blocked it
        </h2>
        <div className="card max-h-[420px] overflow-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-surface-2 text-ink-dim">
              <tr>
                <th className="px-4 py-2 font-medium">Case</th>
                <th className="px-4 py-2 font-medium">Attack class</th>
                <th className="px-4 py-2 font-medium">Result</th>
                <th className="px-4 py-2 font-medium">Control</th>
              </tr>
            </thead>
            <tbody>
              {(safety.cases || []).map((c: any) => (
                <tr key={c.case_id} className="border-t border-line">
                  <td className="px-4 py-2 font-mono text-xs">{c.case_id}</td>
                  <td className="px-4 py-2 text-ink-dim">{c.attack_class}</td>
                  <td className="px-4 py-2">
                    {c.got === c.expected ? (
                      <span className="inline-flex items-center gap-1 text-pos">
                        <CheckCircle2 className="h-3.5 w-3.5" /> {c.got}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-neg">
                        <XCircle className="h-3.5 w-3.5" /> {c.got}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-ink-faint">{c.control || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value, sub, good }: any) {
  return (
    <div className="card p-4">
      <p className={`font-mono text-2xl font-semibold ${good ? "text-pos" : "gradient-text"}`}>
        {value}
      </p>
      <p className="mt-1 text-sm">{label}</p>
      <p className="text-xs text-ink-faint">{sub}</p>
    </div>
  );
}

function Stat({ n, l, tone }: { n: number; l: string; tone?: string }) {
  return (
    <div>
      <p className={`font-mono text-2xl font-semibold ${tone === "neg" ? "text-neg" : "text-ink"}`}>
        {n.toLocaleString()}
      </p>
      <p className="text-xs text-ink-faint">{l}</p>
    </div>
  );
}
