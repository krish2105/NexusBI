"use client";
import { motion } from "motion/react";
import { GitBranch, TrendingDown, TrendingUp } from "lucide-react";
import type { RootCause } from "@/lib/types";

function fmt(n: number) {
  const a = Math.abs(n);
  if (a >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (a >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return n.toFixed(0);
}

export default function RootCauseCard({ rc }: { rc: RootCause }) {
  const up = rc.total_change >= 0;
  const maxDelta = Math.max(...rc.contributors.map((c) => Math.abs(c.delta)), 1);

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-ai-gradient">
          <GitBranch className="h-4 w-4 text-white" />
        </span>
        <h3 className="text-sm font-semibold tracking-wide text-ink-dim">
          ROOT-CAUSE · by {rc.decomposition_dimension}
        </h3>
        <span
          className={`ml-auto flex items-center gap-1 text-sm font-medium ${
            up ? "text-pos" : "text-neg"
          }`}
        >
          {up ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
          {up ? "+" : ""}
          {rc.pct_change}%
        </span>
      </div>

      <div className="mb-4 flex items-center gap-3 text-sm text-ink-dim">
        <span className="font-mono">{rc.period_from}</span>
        <span className="font-mono text-ink">{fmt(rc.total_from)}</span>
        <span className="text-ink-faint">→</span>
        <span className="font-mono">{rc.period_to}</span>
        <span className="font-mono text-ink">{fmt(rc.total_to)}</span>
        <span className={`ml-auto font-mono ${up ? "text-pos" : "text-neg"}`}>
          {up ? "+" : ""}
          {fmt(rc.total_change)}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {rc.contributors.map((c, i) => {
          const pos = c.delta >= 0;
          const w = (Math.abs(c.delta) / maxDelta) * 100;
          return (
            <motion.div
              key={c.member}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-3"
            >
              <span className="w-36 shrink-0 truncate text-xs text-ink-dim" title={c.member}>
                {c.member}
              </span>
              <div className="relative h-5 flex-1 overflow-hidden rounded bg-surface-2">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${w}%` }}
                  transition={{ duration: 0.6, delay: i * 0.05 }}
                  className={`absolute inset-y-0 left-0 rounded ${
                    pos ? "bg-pos/50" : "bg-neg/50"
                  }`}
                />
              </div>
              <span
                className={`w-20 shrink-0 text-right font-mono text-xs ${
                  pos ? "text-pos" : "text-neg"
                }`}
              >
                {pos ? "+" : ""}
                {fmt(c.delta)}
              </span>
              {c.contribution_pct != null && (
                <span className="w-14 shrink-0 text-right text-[11px] text-ink-faint">
                  {c.contribution_pct > 0 ? "" : ""}
                  {c.contribution_pct}%
                </span>
              )}
            </motion.div>
          );
        })}
      </div>
      <p className="mt-3 border-t border-line pt-3 text-[11px] text-ink-faint">
        Contribution % is each member&apos;s share of the total change (negative % means
        it moved against the overall direction).
      </p>
    </div>
  );
}
