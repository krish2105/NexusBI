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
import { tooltipProps, useChartTheme } from "@/lib/chartTheme";

function fmt(n: number) {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return `${n}`;
}

export default function AutoChart({ result }: { result: AnalysisResult }) {
  const c = useChartTheme();
  const { chart_spec, rows, forecast, anomalies } = result;
  const enc = chart_spec.encodings;

  const AX = { fill: c.axis, fontSize: 11 };
  const tip = tooltipProps(c);

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
          <CartesianGrid stroke={c.grid} vertical={false} />
          <XAxis dataKey="label" tick={AX} tickLine={false} axisLine={{ stroke: c.grid }} />
          <YAxis tick={AX} tickLine={false} axisLine={false} tickFormatter={fmt} width={44} />
          <Tooltip {...tip} />
          <defs>
            <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.indigo} stopOpacity={c.bandOpacity[0]} />
              <stop offset="100%" stopColor={c.indigo} stopOpacity={c.bandOpacity[1]} />
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
            stroke={c.cyan}
            strokeWidth={2.2}
            dot={false}
            isAnimationActive
            animationDuration={900}
          />
          <Line
            dataKey="forecast"
            stroke={c.indigo}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
          />
          <Scatter dataKey="anomaly" fill={c.amber} shape="circle" />
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
          <CartesianGrid stroke={c.grid} vertical={false} />
          <XAxis
            dataKey="label"
            tick={AX}
            tickLine={false}
            axisLine={{ stroke: c.grid }}
            interval={0}
            angle={data.length > 6 ? -25 : 0}
            textAnchor={data.length > 6 ? "end" : "middle"}
            height={data.length > 6 ? 60 : 30}
          />
          <YAxis tick={AX} tickLine={false} axisLine={false} tickFormatter={fmt} width={44} />
          <Tooltip {...tip} cursor={{ fill: c.cursorFill }} />
          <defs>
            <linearGradient id="barFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.indigo} />
              <stop offset="100%" stopColor={c.cyan} />
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
          <CartesianGrid stroke={c.grid} />
          <XAxis dataKey="x" tick={AX} tickLine={false} axisLine={{ stroke: c.grid }} tickFormatter={fmt} />
          <YAxis dataKey="y" tick={AX} tickLine={false} axisLine={false} tickFormatter={fmt} width={44} />
          <Tooltip {...tip} />
          <Scatter data={data} fill={c.cyan} />
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
            {result.columns.map((col) => (
              <th key={col} className="px-3 py-2 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 50).map((r, i) => (
            <tr key={i} className="border-t border-line">
              {result.columns.map((col) => (
                <td key={col} className="px-3 py-1.5 font-mono text-[13px]">
                  {String(r[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
