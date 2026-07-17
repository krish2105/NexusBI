"use client";
import { motion } from "motion/react";
import { AlertTriangle, Lightbulb, TrendingUp } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import ConfidenceGauge from "./ConfidenceGauge";

export default function InsightCard({ result }: { result: AnalysisResult }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="glass gradient-border relative rounded-2xl p-5"
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-ai-gradient">
          <Lightbulb className="h-4 w-4 text-white" />
        </span>
        <h3 className="text-sm font-semibold tracking-wide text-ink-dim">
          NARRATED INSIGHT
        </h3>
      </div>
      <p className="text-[15px] leading-relaxed text-ink">{result.narrative}</p>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-4">
        <ConfidenceGauge level={result.confidence} />
        {result.forecast && (
          <div className="flex items-center gap-2 text-xs text-ink-dim">
            <TrendingUp className="h-4 w-4 text-indigo" />
            {result.forecast.method}
          </div>
        )}
        {result.anomalies.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-amber">
            <AlertTriangle className="h-4 w-4" />
            {result.anomalies.length} anomaly point(s)
          </div>
        )}
      </div>

      {result.assumptions.length > 0 && (
        <div className="mt-3 rounded-lg border border-line bg-surface/60 p-3">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
            Assumptions
          </p>
          <ul className="list-inside list-disc space-y-0.5 text-xs text-ink-dim">
            {result.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </motion.div>
  );
}
