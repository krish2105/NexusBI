"use client";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Database, Table2, BookOpen, ShieldCheck, Gauge } from "lucide-react";
import { getSchema, getEvals } from "@/lib/api";

export default function Connections() {
  const [schema, setSchema] = useState<any>(null);
  const [evals, setEvals] = useState<any>(null);
  const [open, setOpen] = useState<string | null>("orders");

  useEffect(() => {
    getSchema().then(setSchema).catch(() => {});
    getEvals().then(setEvals).catch(() => {});
  }, []);

  const safety = evals?.sql_safety;
  const t2s = evals?.text2sql;
  const fc = evals?.forecast;

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <h1 className="text-3xl font-semibold tracking-tight">Connections & Catalog</h1>
      <p className="mt-2 text-ink-dim">
        The bundled read-only demo — the real Olist e-commerce warehouse (99,441 orders).
      </p>

      <div className="mt-6 flex items-center gap-3 rounded-xl border border-pos/25 bg-pos/5 px-4 py-3 text-sm">
        <ShieldCheck className="h-5 w-5 text-pos" />
        <span>
          <b>Demo — Olist e-commerce</b> · SQLite · connected read-only ·{" "}
          <span className="text-pos">writes rejected by construction</span>
        </span>
      </div>

      {/* Accuracy report */}
      {evals && (
        <section className="mt-8">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
            <Gauge className="h-5 w-5 text-indigo" /> How accurate is Nexus?
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Adversarial blocked" value={safety ? `${Math.round(safety.block_rate * 100)}%` : "—"} sub={safety ? `${safety.adversarial_blocked}/${safety.adversarial_total} cases` : ""} good />
            <Stat label="Data integrity" value={t2s ? `${Math.round(t2s.data_integrity_rate * 100)}%` : "—"} sub={t2s ? `${t2s.data_integrity_pass}/${t2s.total} evals` : ""} good />
            <Stat label="Generator accuracy" value={t2s ? `${Math.round(t2s.nexus_generator_execution_accuracy * 100)}%` : "—"} sub="zero-key engine" />
            <Stat label="Forecast MAPE" value={fc ? `${fc.MAPE_pct}%` : "—"} sub={fc?.method || ""} />
          </div>
        </section>
      )}

      {/* Schema explorer */}
      {schema && (
        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_360px]">
          <section>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
              <Table2 className="h-5 w-5 text-indigo" /> Tables ({schema.tables.length})
            </h2>
            <div className="flex flex-col gap-2">
              {schema.tables.map((t: any) => (
                <div key={t.name} className="card overflow-hidden">
                  <button
                    onClick={() => setOpen(open === t.name ? null : t.name)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left"
                  >
                    <span className="flex items-center gap-2 font-mono text-sm">
                      <Database className="h-4 w-4 text-ink-faint" />
                      {t.name}
                    </span>
                    <span className="text-xs text-ink-faint">{t.columns.length} cols</span>
                  </button>
                  {open === t.name && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      className="border-t border-line px-4 py-3"
                    >
                      <p className="mb-2 text-xs italic text-ink-faint">{t.grain}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {t.columns.map((c: any) => (
                          <span
                            key={c.name}
                            title={c.definition}
                            className="rounded-md border border-line bg-surface/60 px-2 py-0.5 font-mono text-[11px] text-ink-dim"
                          >
                            {c.name}
                            <span className="text-ink-faint"> :{c.type.toLowerCase()}</span>
                          </span>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
              <BookOpen className="h-5 w-5 text-indigo" /> Business glossary
            </h2>
            <div className="flex flex-col gap-2">
              {schema.glossary.map((g: any) => (
                <div key={g.term} className="card p-3">
                  <p className="text-sm font-medium">{g.term}</p>
                  <p className="mt-0.5 text-xs text-ink-dim">{g.definition}</p>
                  <code className="mt-1 block overflow-x-auto rounded bg-[#0E1117] px-2 py-1 font-mono text-[11px] text-cyan">
                    {g.canonical_sql}
                  </code>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function Stat({ label, value, sub, good }: { label: string; value: string; sub: string; good?: boolean }) {
  return (
    <div className="card p-4">
      <p className={`font-mono text-2xl font-semibold ${good ? "text-pos" : "gradient-text"}`}>{value}</p>
      <p className="mt-1 text-sm">{label}</p>
      <p className="text-xs text-ink-faint">{sub}</p>
    </div>
  );
}
