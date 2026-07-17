"use client";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AnalysisResult } from "@/lib/types";

const AX = { stroke: "#5E6678", fontSize: 11 };
const GRID = "#1B1F2A";

const tip = {
  contentStyle: {
    background: "#14171F",
    border: "1px solid #242A38",
    borderRadius: 10,
    fontSize: 12,
  },
  labelStyle: { color: "#9BA3B4" },
};

function fmt(n: number) {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return `${n}`;
}

export default function AutoChart({ result }: { result: AnalysisResult }) {
  const { chart_spec, rows, forecast, anomalies } = result;
  const enc = chart_spec.encodings;

  if (chart_spec.type === "line") {
    const x = enc.x as string;
    const y = enc.y as string;
    const anomIdx = new Set((anomalies || []).map((a) => a.index));
    const hist = rows.map((r, i) => ({
      label: r[x],
      actual: r[y],
      anomaly: anomIdx.has(i) ? r[y] : null,
    }));
    const fc =
      forecast?.periods.map((p, i) => ({
        label: p,
        forecast: forecast.point[i],
        band: [forecast.lower[i], forecast.upper[i]] as [number, number],
      })) || [];
    const data = [...hist, ...fc];
    return (
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="label" tick={AX} tickLine={false} axisLine={{ stroke: GRID }} />
          <YAxis tick={AX} tickLine={false} axisLine={false} tickFormatter={fmt} width={44} />
          <Tooltip {...tip} />
          <defs>
            <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366F1" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#6366F1" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Area
            dataKey="band"
            stroke="none"
            fill="url(#bandFill)"
            isAnimationActive
            connectNulls
          />
          <Line
            dataKey="actual"
            stroke="#22D3EE"
            strokeWidth={2.2}
            dot={false}
            isAnimationActive
            animationDuration={900}
          />
          <Line
            dataKey="forecast"
            stroke="#6366F1"
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
          />
          <Scatter dataKey="anomaly" fill="#FBBF24" shape="circle" />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  if (chart_spec.type === "bar" || chart_spec.type === "grouped_bar") {
    const x = enc.x as string;
    const y = Array.isArray(enc.y) ? (enc.y[0] as string) : (enc.y as string);
    const data = rows.slice(0, 20).map((r) => ({ label: String(r[x]), value: r[y] }));
    return (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="label"
            tick={AX}
            tickLine={false}
            axisLine={{ stroke: GRID }}
            interval={0}
            angle={data.length > 6 ? -25 : 0}
            textAnchor={data.length > 6 ? "end" : "middle"}
            height={data.length > 6 ? 60 : 30}
          />
          <YAxis tick={AX} tickLine={false} axisLine={false} tickFormatter={fmt} width={44} />
          <Tooltip {...tip} cursor={{ fill: "rgba(99,102,241,0.08)" }} />
          <defs>
            <linearGradient id="barFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366F1" />
              <stop offset="100%" stopColor="#22D3EE" />
            </linearGradient>
          </defs>
          <Bar
            dataKey="value"
            fill="url(#barFill)"
            radius={[6, 6, 0, 0]}
            isAnimationActive
            animationDuration={800}
          />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (chart_spec.type === "scatter") {
    const x = enc.x as string;
    const y = enc.y as string;
    const data = rows.map((r) => ({ x: r[x], y: r[y] }));
    return (
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} />
          <XAxis dataKey="x" tick={AX} tickLine={false} axisLine={{ stroke: GRID }} tickFormatter={fmt} />
          <YAxis dataKey="y" tick={AX} tickLine={false} axisLine={false} tickFormatter={fmt} width={44} />
          <Tooltip {...tip} />
          <Scatter data={data} fill="#22D3EE" />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  // Fallback compact table
  return (
    <div className="max-h-[300px] overflow-auto rounded-lg border border-line">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-surface-2 text-ink-dim">
          <tr>
            {result.columns.map((c) => (
              <th key={c} className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 50).map((r, i) => (
            <tr key={i} className="border-t border-line">
              {result.columns.map((c) => (
                <td key={c} className="px-3 py-1.5 font-mono text-[13px]">
                  {String(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
