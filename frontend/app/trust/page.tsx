"use client";
import { motion } from "motion/react";
import {
  ShieldCheck,
  Lock,
  Scale,
  ThumbsUp,
  CheckCircle2,
  XCircle,
  Activity,
} from "lucide-react";
import { getTrust } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { ErrorState, PageLoading } from "@/components/States";

const reveal = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.5 },
};

export default function Trust() {
  const { data: t, loading, error, reload, slow } = useResource<any>(() => getTrust());
  if (loading) return <PageLoading slow={slow} />;
  if (error || !t)
    return (
      <main className="mx-auto max-w-6xl px-4 pt-28">
        <ErrorState message={error?.message} onRetry={reload} />
      </main>
    );

  const pct = (v: any) => (v == null ? "—" : `${Math.round(v * 100)}%`);
  const safety = t.safety || {};
  const acc = t.accuracy || {};
  const gov = t.governance || {};
  const fb = t.feedback || {};
  const obs = t.observability || {};
  const fc = t.forecast || {};

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
      {acc.spider_execution_accuracy != null && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Spider/BIRD EX"
            value={pct(acc.spider_execution_accuracy)}
            sub={`execution accuracy · ${acc.spider_generator_mode ?? "deterministic"}`}
          />
        </div>
      )}

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
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-line bg-surface/50 px-3 py-2 text-xs text-ink-dim">
            <Activity className={`h-4 w-4 ${obs.tracing_enabled ? "text-pos" : "text-ink-faint"}`} />
            {obs.tracing_enabled
              ? "Full observability — every query traced (Langfuse)"
              : "Tracing off — set LANGFUSE_* keys to enable full observability"}
            <span className="ml-auto rounded-full border border-line px-2 py-0.5 text-[10px] uppercase text-ink-faint">
              engine: {obs.llm_provider || "deterministic"}
            </span>
          </div>
        </motion.div>
      </section>

      {/* forecast head-to-head */}
      {fc.grains && Object.keys(fc.grains).length > 0 && (
        <section className="mt-8">
          <h2 className="mb-1 text-lg font-medium">
            Forecast head-to-head — measured, not asserted
          </h2>
          <p className="mb-3 text-sm text-ink-dim">
            Rolling-origin (walk-forward) backtest, errors pooled across folds. A
            model must beat the seasonal-naive reference to matter.
            {fc.lstm_reproducible != null && (
              <span className="ml-1">
                LSTM variant{" "}
                {fc.torch_available ? "active" : "off (install requirements-ml.txt)"}
                {fc.torch_available &&
                  `, reproducible: ${fc.lstm_reproducible ? "yes" : "no"}`}
                .
              </span>
            )}
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            {Object.entries(fc.grains).map(([grain, g]: any) => (
              <div key={grain} className="card p-0">
                <div className="flex items-center justify-between border-b border-line px-4 py-2">
                  <span className="font-medium capitalize">{grain} revenue</span>
                  <span className="text-xs text-ink-faint">
                    {g.n_origins} folds × {g.holdout}
                  </span>
                </div>
                <table className="w-full text-left text-sm">
                  <thead className="text-ink-dim">
                    <tr>
                      <th className="px-4 py-1.5 font-medium">Engine</th>
                      <th className="px-4 py-1.5 font-medium">RMSE</th>
                      <th className="px-4 py-1.5 font-medium">MAPE</th>
                      <th className="px-4 py-1.5 font-medium">95% cov</th>
                    </tr>
                  </thead>
                  <tbody>
                    {["seasonal_naive", "holtwinters", "lstm"].map((name) => {
                      const m = g.engines?.[name];
                      const win = g.best === name;
                      const partial = m && m.comparable === false;
                      return (
                        <tr key={name} className="border-t border-line">
                          <td className={`px-4 py-1.5 ${win ? "font-medium text-pos" : ""}`}>
                            {win && "★ "}
                            {name.replace("_", "-")}
                            {partial && (
                              <span className="ml-1 text-[10px] text-ink-faint">
                                ({m.folds}/{g.n_origins} folds · indicative)
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-1.5 font-mono text-xs">
                            {m ? Math.round(m.rmse).toLocaleString() : "—"}
                          </td>
                          <td className="px-4 py-1.5 font-mono text-xs">
                            {m?.mape_pct != null ? `${m.mape_pct}%` : "—"}
                          </td>
                          <td className="px-4 py-1.5 font-mono text-xs text-ink-faint">
                            {m?.band_coverage_95 != null
                              ? `${Math.round(m.band_coverage_95 * 100)}%`
                              : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </section>
      )}

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
