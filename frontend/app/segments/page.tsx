"use client";
import { useEffect, useState } from "react";
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

const COLORS: Record<string, string> = {
  Champions: "#34D399",
  Loyal: "#22D3EE",
  "Potential Loyalist": "#818CF8",
  "New / Promising": "#A78BFA",
  "At Risk": "#FBBF24",
  "Can't Lose": "#FB923C",
  Hibernating: "#94A3B8",
  Lost: "#F87171",
};

export default function Segments() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getSegments().then(setData).catch(() => {});
  }, []);

  if (!data)
    return <main className="pt-28 text-center text-ink-dim">Loading segments…</main>;

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
                      background: (COLORS[s.segment] || "#6366F1") + "22",
                      color: COLORS[s.segment] || "#6366F1",
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
                <CartesianGrid stroke="#1B1F2A" />
                <XAxis
                  type="number"
                  dataKey="f"
                  name="frequency"
                  tick={{ stroke: "#5E6678", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#1B1F2A" }}
                />
                <YAxis
                  type="number"
                  dataKey="m"
                  name="monetary"
                  tick={{ stroke: "#5E6678", fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "#14171F",
                    border: "1px solid #242A38",
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  cursor={{ strokeDasharray: "3 3" }}
                />
                <Scatter data={data.scatter} fillOpacity={0.7}>
                  {data.scatter.map((p: any, i: number) => (
                    <Cell key={i} fill={COLORS[p.segment] || "#6366F1"} />
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
