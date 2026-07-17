"use client";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { History as HistoryIcon, ShieldCheck, ShieldAlert } from "lucide-react";
import { getHistory, getAudit } from "@/lib/api";

export default function HistoryPage() {
  const [queries, setQueries] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);

  useEffect(() => {
    getHistory().then(setQueries).catch(() => {});
    getAudit().then(setAudit).catch(() => {});
  }, []);

  const badge = (c: string) =>
    c === "HIGH" ? "text-pos" : c === "MEDIUM" ? "text-amber" : "text-neg";

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
        <HistoryIcon className="h-7 w-7 text-indigo" /> Query history & audit
      </h1>
      <p className="mt-2 text-ink-dim">
        Every question, its generated SQL, confidence — and an append-only audit of
        every executed and blocked query.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-lg font-medium">Questions</h2>
          <div className="flex flex-col gap-2">
            {queries.length === 0 && <p className="text-sm text-ink-faint">No queries yet.</p>}
            {queries.map((q, i) => (
              <motion.div
                key={q.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="card p-4"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm">{q.question}</p>
                  {q.confidence && (
                    <span className={`text-xs font-medium ${badge(q.confidence)}`}>
                      {q.confidence}
                    </span>
                  )}
                </div>
                {q.sql && (
                  <code className="mt-2 block overflow-x-auto rounded bg-[#0E1117] px-2 py-1 font-mono text-[11px] text-ink-dim">
                    {q.sql.replace(/\s+/g, " ").slice(0, 140)}
                  </code>
                )}
              </motion.div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium">Audit log</h2>
          <div className="flex flex-col gap-1.5">
            {audit.map((a) => (
              <div
                key={a.id}
                className="flex items-center gap-3 rounded-lg border border-line bg-surface/40 px-3 py-2 text-xs"
              >
                {a.verdict === "BLOCK" ? (
                  <ShieldAlert className="h-4 w-4 shrink-0 text-neg" />
                ) : (
                  <ShieldCheck className="h-4 w-4 shrink-0 text-pos" />
                )}
                <span className="font-mono text-ink-dim">{a.action}</span>
                {a.row_count != null && (
                  <span className="text-ink-faint">{a.row_count} rows</span>
                )}
                {a.latency_ms != null && (
                  <span className="ml-auto text-ink-faint">{a.latency_ms} ms</span>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
