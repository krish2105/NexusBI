"use client";
import { motion } from "motion/react";
import { Users } from "lucide-react";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { getSegments } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { ErrorState, PageLoading } from "@/components/States";
import { tooltipProps, useChartTheme } from "@/lib/chartTheme";

export default function Segments() {
  const { data, loading, error, reload } = useResource<any>(() => getSegments());
  const chart = useChartTheme();
  const COLORS = chart.segments;

  if (loading) return <PageLoading />;
  if (error || !data)
    return (
      <main className="mx-auto max-w-6xl px-4 pt-28">
        <ErrorState message={error?.message} onRetry={reload} />
      </main>
    );

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
        <Users className="h-7 w-7 text-indigo" /> Customer Segments
      </h1>
      <p className="mt-2 text-ink-dim">
        RFM segmentation — quintile scoring on{" "}
        {data.columns_used
          ? `recency (${data.columns_used.recency}), frequency (${data.columns_used.frequency}), monetary (${data.columns_used.monetary})`
          : "recency, frequency, monetary"}{" "}
        across {data.total_customers?.toLocaleString()} customers. Deterministic ML —
        no LLM involved.
      </p>

      {!data.available ? (
        <p className="mt-8 text-ink-dim">{data.reason}</p>
      ) : (
        <>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {data.segments.map((s: any, i: number) => (
              <motion.div
                key={s.segment}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="card p-4"
              >
                <div className="flex items-center justify-between">
                  <span
                    className="rounded-full px-2 py-0.5 text-xs font-medium"
                    style={{
                      background: (COLORS[s.segment] || chart.indigo) + "22",
                      color: COLORS[s.segment] || chart.indigo,
                    }}
                  >
                    {s.segment}
                  </span>
                  <span className="font-mono text-sm text-ink-dim">{s.pct}%</span>
                </div>
                <p className="mt-2 font-mono text-2xl font-semibold">
                  {s.count.toLocaleString()}
                </p>
                <div className="mt-2 flex gap-3 text-[11px] text-ink-faint">
                  <span>R {s.avg_recency_days}d</span>
                  <span>F {s.avg_frequency}</span>
                  <span>M {s.avg_monetary}</span>
                </div>
              </motion.div>
            ))}
          </div>

          <div className="card mt-6 p-5">
            <p className="mb-3 text-sm text-ink-dim">
              Frequency × Monetary (sampled), coloured by segment
            </p>
            <ResponsiveContainer width="100%" height={340}>
              <ScatterChart margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                <CartesianGrid stroke={chart.grid} />
                <XAxis
                  type="number"
                  dataKey="f"
                  name="frequency"
                  tick={{ fill: chart.axis, fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: chart.grid }}
                />
                <YAxis
                  type="number"
                  dataKey="m"
                  name="monetary"
                  tick={{ fill: chart.axis, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  {...tooltipProps(chart)}
                  cursor={{ strokeDasharray: "3 3", stroke: chart.axis }}
                />
                <Scatter data={data.scatter} fillOpacity={0.7}>
                  {data.scatter.map((p: any, i: number) => (
                    <Cell key={i} fill={COLORS[p.segment] || chart.indigo} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </main>
  );
}
