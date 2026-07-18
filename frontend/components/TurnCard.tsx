"use client";
import { motion } from "motion/react";
import { CornerDownRight, MessageSquare } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import ResultCanvas from "./ResultCanvas";

export default function TurnCard({
  question,
  result,
  onPin,
  onFollowup,
}: {
  question: string;
  result: AnalysisResult;
  onPin?: (r: AnalysisResult) => void;
  onFollowup?: (q: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col gap-3"
    >
      {/* the user's question */}
      <div className="flex items-start gap-2">
        <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg border border-line bg-surface">
          <MessageSquare className="h-3.5 w-3.5 text-ink-dim" />
        </span>
        <div>
          <p className="text-[15px] font-medium text-ink">{question}</p>
          {result.resolved_question && (
            <p className="mt-0.5 flex items-center gap-1 text-xs text-ink-faint">
              <CornerDownRight className="h-3 w-3" />
              interpreted as: {result.resolved_question}
            </p>
          )}
        </div>
      </div>

      <ResultCanvas result={result} onPin={onPin} />

      {/* one-click follow-ups */}
      {onFollowup && result.suggested_followups?.length > 0 && !result.blocked && (
        <div className="flex flex-wrap gap-2 pl-8">
          {result.suggested_followups.map((f) => (
            <button
              key={f}
              onClick={() => onFollowup(f)}
              className="focus-ring rounded-full border border-line bg-surface/60 px-3 py-1.5 text-xs text-ink-dim transition-colors hover:border-indigo/40 hover:text-ink"
            >
              {f}
            </button>
          ))}
        </div>
      )}
    </motion.div>
  );
}
