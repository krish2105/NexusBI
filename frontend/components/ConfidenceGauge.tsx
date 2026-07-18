"use client";
import { motion } from "motion/react";
import type { Confidence } from "@/lib/types";
import { useChartTheme } from "@/lib/chartTheme";

const MAP: Record<Confidence, { v: number; tone: "pos" | "amber" | "neg"; label: string }> = {
  HIGH: { v: 0.92, tone: "pos", label: "High" },
  MEDIUM: { v: 0.62, tone: "amber", label: "Medium" },
  LOW: { v: 0.32, tone: "neg", label: "Low" },
};

export default function ConfidenceGauge({ level }: { level: Confidence }) {
  const c = useChartTheme();
  const { v, tone, label } = MAP[level] ?? MAP.LOW;
  const color = c[tone];
  const r = 26;
  const circ = 2 * Math.PI * r;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-16 w-16">
        <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
          <circle cx="32" cy="32" r={r} fill="none" stroke={c.track} strokeWidth="6" />
          <motion.circle
            cx="32"
            cy="32"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: circ * (1 - v) }}
            transition={{ type: "spring", stiffness: 90, damping: 18 }}
          />
        </svg>
        <span className="absolute inset-0 grid place-items-center text-sm font-semibold">
          {Math.round(v * 100)}
        </span>
      </div>
      <div>
        <p className="text-xs text-ink-faint">Confidence</p>
        <p className="font-medium" style={{ color }}>
          {label}
        </p>
      </div>
    </div>
  );
}
