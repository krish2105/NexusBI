"use client";
import { useChartTheme } from "@/lib/chartTheme";

export type SparkTone = "accent" | "good" | "bad" | "neutral";

export default function Sparkline({
  values,
  tone = "accent",
  width = 96,
  height = 28,
}: {
  values: number[];
  tone?: SparkTone;
  width?: number;
  height?: number;
}) {
  const c = useChartTheme();
  if (!values || values.length < 2) return null;
  const color =
    tone === "good"
      ? c.pos
      : tone === "bad"
        ? c.neg
        : tone === "neutral"
          ? c.neutral
          : c.cyan;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const pts = values
    .map((v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`)
    .join(" ");
  const last = values[values.length - 1];
  const lastY = height - ((last - min) / span) * height;
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width} cy={lastY} r={2} fill={color} />
    </svg>
  );
}
