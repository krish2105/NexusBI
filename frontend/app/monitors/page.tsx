"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Bell, Play, Plus, Radar, AlertTriangle, CheckCircle2 } from "lucide-react";
import {
  getMonitors,
  getAlerts,
  createMonitor,
  runMonitor,
  runAllMonitors,
} from "@/lib/api";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/States";

export default function Monitors() {
  const [monitors, setMonitors] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [question, setQuestion] = useState("Show monthly merchandise revenue over time");
  const [busy, setBusy] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // Post-mutation refresh (doesn't flip the initial-load skeleton).
  const refresh = async () => {
    const [m, a] = await Promise.all([getMonitors(), getAlerts()]);
    setMonitors(m);
    setAlerts(a);
  };
  const load = () => {
    setLoading(true);
    setErr(null);
    refresh()
      .catch((e) => setErr(e instanceof Error ? e.message : "failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const add = async () => {
    if (!name.trim() || !question.trim()) return;
    setBusy(true);
    try {
      await createMonitor(name.trim(), question.trim());
      setName("");
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const runOne = async (id: string) => {
    await runMonitor(id);
    await refresh();
  };
  const runAll = async () => {
    setRunningAll(true);
    try {
      await runAllMonitors();
      await refresh();
    } finally {
      setRunningAll(false);
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
          <Radar className="h-7 w-7 text-indigo" /> Monitors & Alerts
        </h1>
        <button
          onClick={runAll}
          disabled={runningAll}
          className="focus-ring flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm text-ink-dim hover:text-ink disabled:opacity-50"
        >
          <Play className="h-4 w-4" /> {runningAll ? "Running…" : "Run all now"}
        </button>
      </div>
      <p className="mt-2 text-ink-dim">
        Save a question to watch. Nexus re-runs it on a schedule and raises an alert
        when the latest period deviates from its baseline. Schedule via cron hitting{" "}
        <code className="text-cyan">POST /monitors/run-all</code>.
      </p>

      {/* create */}
      <div className="card mt-6 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Monitor name (e.g. Revenue watch)"
          className="focus-ring rounded-lg border border-line bg-surface/60 px-3 py-2 text-sm sm:w-48"
        />
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Question to watch…"
          className="focus-ring flex-1 rounded-lg border border-line bg-surface/60 px-3 py-2 text-sm"
        />
        <button
          onClick={add}
          disabled={busy}
          className="focus-ring flex items-center justify-center gap-1.5 rounded-lg bg-ai-gradient px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          <Plus className="h-4 w-4" /> Add monitor
        </button>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        {/* monitors */}
        <section>
          <h2 className="mb-3 text-lg font-medium">Monitors ({monitors.length})</h2>
          <div className="flex flex-col gap-2">
            {loading && (
              <>
                <CardSkeleton />
                <CardSkeleton />
              </>
            )}
            {!loading && err && (
              <ErrorState message={err} onRetry={load} />
            )}
            {!loading && !err && monitors.length === 0 && (
              <EmptyState
                icon={Radar}
                title="No monitors yet"
                hint="Add a question above to watch a metric on a schedule."
              />
            )}
            {!loading &&
              monitors.map((m) => (
              <div key={m.id} className="card flex items-center justify-between p-4">
                <div className="min-w-0">
                  <p className="font-medium">{m.name}</p>
                  <p className="truncate text-xs text-ink-dim">{m.question}</p>
                  <p className="mt-0.5 text-[11px] text-ink-faint">
                    {m.last_status
                      ? `last run: ${m.last_status}`
                      : "never run"}{" "}
                    · {m.schedule}
                  </p>
                </div>
                <button
                  onClick={() => runOne(m.id)}
                  className="focus-ring ml-3 flex shrink-0 items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-xs text-ink-dim hover:border-indigo/40 hover:text-ink"
                >
                  <Play className="h-3.5 w-3.5" /> Run
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* alerts */}
        <section>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
            <Bell className="h-5 w-5 text-amber" /> Alert inbox ({alerts.length})
          </h2>
          <div className="flex flex-col gap-2">
            {loading && <CardSkeleton />}
            {!loading && !err && alerts.length === 0 && (
              <div className="flex items-center gap-2 rounded-xl border border-pos/25 bg-pos/5 px-4 py-3 text-sm text-ink-dim">
                <CheckCircle2 className="h-4 w-4 text-pos" /> No alerts — all monitored
                metrics are within range.
              </div>
            )}
            <AnimatePresence>
              {alerts.map((a) => (
                <motion.div
                  key={a.id}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`card border-l-2 p-4 ${
                    a.severity === "high" ? "border-l-neg" : "border-l-amber"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <AlertTriangle
                      className={`h-4 w-4 ${
                        a.severity === "high" ? "text-neg" : "text-amber"
                      }`}
                    />
                    <span className="text-sm font-medium">{a.monitor_name}</span>
                    <span
                      className={`ml-auto rounded-full px-2 py-0.5 text-[10px] uppercase ${
                        a.severity === "high"
                          ? "bg-neg/15 text-neg"
                          : "bg-amber/15 text-amber"
                      }`}
                    >
                      {a.severity}
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm text-ink-dim">{a.message}</p>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </section>
      </div>
    </main>
  );
}
