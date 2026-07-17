"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "motion/react";
import AutoChart from "@/components/AutoChart";
import KpiCard from "@/components/KpiCard";
import type { AnalysisResult } from "@/lib/types";

export default function DashboardDetail() {
  const { id } = useParams<{ id: string }>();
  const [dash, setDash] = useState<any>(null);

  useEffect(() => {
    fetch(`/api/dashboards/${id}`)
      .then((r) => r.json())
      .then(setDash)
      .catch(() => {});
  }, [id]);

  if (!dash) return <main className="pt-28 text-center text-ink-dim">Loading…</main>;

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <h1 className="text-3xl font-semibold tracking-tight">{dash.name}</h1>
      <p className="mt-2 text-sm text-ink-dim">
        Re-run live · {dash.items?.length || 0} pinned insight(s)
      </p>
      <div className="mt-8 grid auto-rows-[minmax(0,1fr)] gap-4 md:grid-cols-2">
        {(dash.items || []).map((item: any, i: number) => {
          const r: AnalysisResult = item.result;
          if (!r) return null;
          const kpi = r.chart_spec?.type === "kpi";
          const kpiCol = (r.chart_spec?.encodings?.value as string) || r.columns?.[0];
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.06 }}
              className="card p-5"
            >
              <p className="mb-3 text-sm text-ink-dim">{item.question}</p>
              {kpi ? (
                <KpiCard label={kpiCol} value={Number(r.rows?.[0]?.[kpiCol] ?? 0)} />
              ) : (
                <AutoChart result={r} />
              )}
              <p className="mt-3 text-xs text-ink-faint">{r.narrative}</p>
            </motion.div>
          );
        })}
      </div>
    </main>
  );
}
