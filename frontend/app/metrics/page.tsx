"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  BadgeCheck,
  BookMarked,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  getMetrics,
  createMetric,
  updateMetric,
  deleteMetric,
  type Metric,
} from "@/lib/api";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/States";

const BLANK = {
  name: "",
  expression: "",
  base_table: "",
  alias: "",
  synonyms: "",
  description: "",
  certified: true,
};

export default function Metrics() {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState({ ...BLANK });
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const refresh = async () => setMetrics(await getMetrics());
  const load = () => {
    setLoading(true);
    setErr(null);
    refresh()
      .catch((e) => setErr(e instanceof Error ? e.message : "failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const add = async () => {
    if (!form.name || !form.expression || !form.base_table || !form.alias) {
      setFormErr("Name, expression, base table, and alias are all required.");
      return;
    }
    setBusy(true);
    setFormErr(null);
    try {
      await createMetric({
        name: form.name.trim(),
        expression: form.expression.trim(),
        base_table: form.base_table.trim(),
        alias: form.alias.trim(),
        synonyms: form.synonyms
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        description: form.description.trim() || undefined,
        certified: form.certified,
      });
      setForm({ ...BLANK });
      setShowForm(false);
      await refresh();
    } catch (e) {
      setFormErr(e instanceof Error ? e.message : "definition rejected");
    } finally {
      setBusy(false);
    }
  };

  const toggleCertify = async (m: Metric) => {
    await updateMetric(m.id, { certified: !m.certified });
    await refresh();
  };
  const remove = async (m: Metric) => {
    await deleteMetric(m.id);
    await refresh();
  };

  const certifiedCount = metrics.filter((m) => m.certified).length;

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
          <BookMarked className="h-7 w-7 text-indigo" /> Semantic Layer
        </h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="focus-ring flex items-center gap-2 rounded-xl bg-ai-gradient px-4 py-2 text-sm font-medium text-white"
        >
          <Plus className="h-4 w-4" /> Define metric
        </button>
      </div>
      <p className="mt-2 max-w-3xl text-ink-dim">
        Governed metric definitions — the one place to pin what{" "}
        <span className="text-ink">&quot;revenue&quot;</span> means. When a question names a
        metric (or a synonym), Nexus computes it from the{" "}
        <span className="text-ink">certified SQL expression</span> instead of guessing, and
        the answer shows which metric it used. Reused by every question, dashboard, and
        monitor.
      </p>

      <div className="mt-3 flex items-start gap-2 rounded-xl border border-pos/25 bg-pos/5 px-4 py-2.5 text-sm text-ink-dim">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-pos" />
        <p>
          Every definition is <span className="text-ink">safety-verified on save</span> — the
          expression is run through the same five-layer guard that gates every query and a
          dry-run EXPLAIN, so you can&apos;t define a metric that&apos;s unsafe, references a
          column that doesn&apos;t exist, or won&apos;t execute.
        </p>
      </div>

      {/* create form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="card mt-6 flex flex-col gap-3 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Name">
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Merchandise Revenue"
                    className="metric-input"
                  />
                </Field>
                <Field label="Output alias">
                  <input
                    value={form.alias}
                    onChange={(e) => setForm({ ...form, alias: e.target.value })}
                    placeholder="merchandise_revenue"
                    className="metric-input"
                  />
                </Field>
              </div>
              <Field label="Canonical SQL expression">
                <input
                  value={form.expression}
                  onChange={(e) => setForm({ ...form, expression: e.target.value })}
                  placeholder="ROUND(SUM(order_items.line_merchandise_value), 2)"
                  className="metric-input font-mono text-[13px]"
                />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Base table">
                  <input
                    value={form.base_table}
                    onChange={(e) => setForm({ ...form, base_table: e.target.value })}
                    placeholder="order_items"
                    className="metric-input"
                  />
                </Field>
                <Field label="Synonyms (comma-separated)">
                  <input
                    value={form.synonyms}
                    onChange={(e) => setForm({ ...form, synonyms: e.target.value })}
                    placeholder="revenue, sales, net revenue"
                    className="metric-input"
                  />
                </Field>
              </div>
              <Field label="Description">
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Sum of item prices, excluding freight."
                  className="metric-input"
                />
              </Field>
              <div className="flex items-center justify-between">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-dim">
                  <input
                    type="checkbox"
                    checked={form.certified}
                    onChange={(e) => setForm({ ...form, certified: e.target.checked })}
                    className="h-4 w-4 accent-indigo"
                  />
                  Mark as certified
                </label>
                <button
                  onClick={add}
                  disabled={busy}
                  className="focus-ring flex items-center gap-1.5 rounded-lg bg-ai-gradient px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  {busy ? "Verifying…" : "Save & verify"}
                </button>
              </div>
              {formErr && (
                <p className="rounded-lg border border-neg/30 bg-neg/10 px-3 py-2 text-xs text-neg">
                  Rejected by safety verification: {formErr}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <h2 className="mb-3 mt-8 text-lg font-medium">
        Metrics ({metrics.length}) ·{" "}
        <span className="text-pos">{certifiedCount} certified</span>
      </h2>

      <div className="grid gap-3 md:grid-cols-2">
        {loading && (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        )}
        {!loading && err && <ErrorState message={err} onRetry={load} />}
        {!loading && !err && metrics.length === 0 && (
          <EmptyState
            icon={BookMarked}
            title="No metrics defined"
            hint="Define your first governed metric above."
          />
        )}
        {!loading &&
          metrics.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="card flex flex-col p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{m.name}</p>
                    {m.certified && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-pos/30 bg-pos/10 px-2 py-0.5 text-[10px] font-medium text-pos">
                        <BadgeCheck className="h-3 w-3" /> Certified
                      </span>
                    )}
                  </div>
                  {m.description && (
                    <p className="mt-0.5 text-xs text-ink-dim">{m.description}</p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    onClick={() => toggleCertify(m)}
                    title={m.certified ? "Revoke certification" : "Certify"}
                    className={`focus-ring rounded-lg border px-2 py-1 text-[11px] ${
                      m.certified
                        ? "border-line text-ink-dim hover:text-ink"
                        : "border-pos/40 text-pos hover:bg-pos/10"
                    }`}
                  >
                    {m.certified ? "Revoke" : "Certify"}
                  </button>
                  <button
                    onClick={() => remove(m)}
                    aria-label="Delete metric"
                    className="focus-ring rounded-lg border border-line p-1.5 text-ink-dim hover:border-neg/40 hover:text-neg"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              <pre className="mt-3 overflow-x-auto rounded-lg border border-line bg-surface/60 px-3 py-2 font-mono text-[12px] text-cyan">
                {m.expression}
              </pre>
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className="rounded-md border border-line px-1.5 py-0.5 text-ink-faint">
                  from {m.base_table}
                </span>
                {m.synonyms.map((s) => (
                  <span
                    key={s}
                    className="rounded-md bg-white/[0.04] px-1.5 py-0.5 text-ink-dim"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
      </div>

      <style jsx global>{`
        .metric-input {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid var(--line, rgba(255, 255, 255, 0.08));
          background: rgba(255, 255, 255, 0.03);
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
        }
        .metric-input:focus {
          outline: 2px solid rgba(99, 102, 241, 0.5);
          outline-offset: 1px;
        }
      `}</style>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
        {label}
      </label>
      {children}
    </div>
  );
}
