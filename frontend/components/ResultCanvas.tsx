"use client";
import { motion } from "motion/react";
import { Database, Clock, ShieldAlert, Pin } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import AutoChart from "./AutoChart";
import SqlBlock from "./SqlBlock";
import InsightCard from "./InsightCard";
import KpiCard from "./KpiCard";

export default function ResultCanvas({
  result,
  onPin,
}: {
  result: AnalysisResult;
  onPin?: (r: AnalysisResult) => void;
}) {
  if (result.blocked) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="card flex items-start gap-3 border-neg/30 p-5"
      >
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-neg" />
        <div>
          <p className="font-medium text-neg">Blocked by the safety layer</p>
          <p className="mt-1 text-sm text-ink-dim">{result.narrative}</p>
          {result.validation_errors?.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-xs text-ink-faint">
              {result.validation_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      </motion.div>
    );
  }

  const kpi = result.chart_spec.type === "kpi";
  const kpiCol = (result.chart_spec.encodings.value as string) || result.columns[0];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col gap-4"
    >
      <div className="card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3 text-xs text-ink-faint">
            <span className="flex items-center gap-1">
              <Database className="h-3.5 w-3.5" />
              {result.result_meta.row_count ?? result.rows.length} rows
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {result.result_meta.latency_ms ?? 0} ms
            </span>
            <span className="rounded-full border border-line px-2 py-0.5">
              engine: {result.generator}
            </span>
          </div>
          {onPin && (
            <button
              onClick={() => onPin(result)}
              className="focus-ring flex items-center gap-1 rounded-lg border border-line px-2.5 py-1 text-xs text-ink-dim hover:border-indigo/40 hover:text-ink"
            >
              <Pin className="h-3.5 w-3.5" /> Pin
            </button>
          )}
        </div>
        {kpi ? (
          <KpiCard label={kpiCol} value={Number(result.rows[0]?.[kpiCol] ?? 0)} />
        ) : (
          <AutoChart result={result} />
        )}
      </div>

      {result.sql && <SqlBlock sql={result.sql} validated />}
      <InsightCard result={result} />
    </motion.div>
  );
}
