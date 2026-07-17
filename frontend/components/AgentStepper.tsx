"use client";
import { motion } from "motion/react";
import { Check, Loader2, ShieldAlert } from "lucide-react";
import { PIPELINE_STEPS, type AgentEvent } from "@/lib/types";

type StepState = "idle" | "running" | "ok" | "blocked" | "skipped";

export default function AgentStepper({
  events,
  active,
}: {
  events: AgentEvent[];
  active: boolean;
}) {
  const stateFor = (node: string): StepState => {
    const evs = events.filter((e) => e.node === node);
    if (!evs.length) return "idle";
    const last = evs[evs.length - 1];
    if (last.status === "blocked") return "blocked";
    if (last.status === "ok") return "ok";
    if (last.status === "skipped") return "skipped";
    return "running";
  };

  return (
    <div className="flex flex-col gap-1">
      {PIPELINE_STEPS.map((step, i) => {
        const s = stateFor(step.node);
        const visible = active || events.length > 0;
        return (
          <motion.div
            key={step.node}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: visible ? 1 : 0.35, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className="flex items-center gap-3 rounded-lg px-2 py-1.5"
          >
            <span
              className={`grid h-6 w-6 place-items-center rounded-full border text-[11px] transition-colors ${
                s === "ok"
                  ? "border-pos/40 bg-pos/15 text-pos"
                  : s === "running"
                    ? "border-indigo/50 bg-indigo/15 text-indigo"
                    : s === "blocked"
                      ? "border-neg/40 bg-neg/15 text-neg"
                      : "border-line bg-surface text-ink-faint"
              }`}
            >
              {s === "ok" ? (
                <Check className="h-3.5 w-3.5" />
              ) : s === "running" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : s === "blocked" ? (
                <ShieldAlert className="h-3.5 w-3.5" />
              ) : (
                i + 1
              )}
            </span>
            <span
              className={`text-sm ${
                s === "idle" ? "text-ink-faint" : "text-ink"
              }`}
            >
              {step.label}
              {step.node === "sql_validator" && s === "ok" && (
                <span className="ml-2 text-xs text-pos">safe ✓</span>
              )}
            </span>
          </motion.div>
        );
      })}
    </div>
  );
}
