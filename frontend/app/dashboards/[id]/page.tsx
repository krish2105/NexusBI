"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "motion/react";
import { RefreshCw, LayoutGrid } from "lucide-react";
import AutoChart from "@/components/AutoChart";
import KpiCard from "@/components/KpiCard";
import type { AnalysisResult } from "@/lib/types";

export default function DashboardDetail() {
  const { id } = useParams<{ id: string }>();
  const [dash, setDash] = useState<any>(null);
  const [live, setLive] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    (fresh: boolean) => {
      setLoading(true);
      // Fast render from stored payloads; "Refresh (live)" re-runs against data.
      fetch(`/api/dashboards/${id}?live=${fresh}`)
        .then((r) => r.json())
        .then(setDash)
        .catch(() => {})
        .finally(() => setLoading(false));
    },
    [id],
  );
  useEffect(() => {
    load(false);
  }, [load]);

  if (!dash && loading)
    return <main className="pt-28 text-center text-ink-dim">Composing dashboard…</main>;
  if (!dash) return <main className="pt-28 text-center text-ink-dim">Not found.</main>;

  const items = (dash.items || []).filter((it: any) => it.result);

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
            <LayoutGrid className="h-7 w-7 text-indigo" /> {dash.name}
          </h1>
          <p className="mt-2 text-sm text-ink-dim">
            {items.length} insight(s){live ? " · live" : " · cached"}
          </p>
        </div>
        <button
          onClick={() => {
            setLive(true);
            load(true);
          }}
          disabled={loading}
          className="focus-ring flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs text-ink-dim hover:text-ink disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh (live)
        </button>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item: any, i: number) => {
          const r: AnalysisResult = item.result;
          const kpi = r.chart_spec?.type === "kpi";
          const kpiCol = (r.chart_spec?.encodings?.value as string) || r.columns?.[0];
          // bento: KPIs are compact (1 col); charts span 2.
          const span = kpi ? "lg:col-span-1 sm:col-span-1" : "lg:col-span-2 sm:col-span-2";
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05 }}
              className={`card flex flex-col p-5 ${span}`}
            >
              <p className="mb-3 text-sm font-medium text-ink-dim">{item.question}</p>
              {kpi ? (
                <div className="flex flex-1 items-center justify-center">
                  <KpiCard label={kpiCol} value={Number(r.rows?.[0]?.[kpiCol] ?? 0)} />
                </div>
              ) : (
                <AutoChart result={r} />
              )}
              <p className="mt-3 line-clamp-2 text-xs text-ink-faint">{r.narrative}</p>
            </motion.div>
          );
        })}
      </div>
    </main>
  );
}
