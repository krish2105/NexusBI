"use client";
import { motion } from "motion/react";
import type { Confidence } from "@/lib/types";

const MAP: Record<Confidence, { v: number; color: string; label: string }> = {
  HIGH: { v: 0.92, color: "#34D399", label: "High" },
  MEDIUM: { v: 0.62, color: "#FBBF24", label: "Medium" },
  LOW: { v: 0.32, color: "#F87171", label: "Low" },
};

export default function ConfidenceGauge({ level }: { level: Confidence }) {
  const { v, color, label } = MAP[level] ?? MAP.LOW;
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-16 w-16">
        <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
          <circle cx="32" cy="32" r={r} fill="none" stroke="#242A38" strokeWidth="6" />
          <motion.circle
            cx="32"
            cy="32"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={{ strokeDashoffset: c * (1 - v) }}
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
