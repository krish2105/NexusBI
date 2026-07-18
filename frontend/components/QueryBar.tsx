"use client";
import { useRef, useState } from "react";
import { motion } from "motion/react";
import { ArrowUp, Sparkles } from "lucide-react";

const EXAMPLES = [
  "Top 5 product categories by merchandise revenue",
  "Show monthly merchandise revenue over time",
  "How many delivered orders are there?",
  "Payment value by payment type",
  "Late-delivery rate by customer state",
];

export default function QueryBar({
  onSubmit,
  busy,
  placeholder = "Ask your data anything…",
  showExamples = true,
}: {
  onSubmit: (q: string) => void;
  busy: boolean;
  placeholder?: string;
  showExamples?: boolean;
}) {
  const [value, setValue] = useState("");
  const btnRef = useRef<HTMLButtonElement>(null);
  const [mag, setMag] = useState({ x: 0, y: 0 });

  const submit = () => {
    if (!value.trim() || busy) return;
    onSubmit(value.trim());
    setValue("");
  };

  const onMove = (e: React.MouseEvent) => {
    const b = btnRef.current?.getBoundingClientRect();
    if (!b) return;
    setMag({ x: (e.clientX - (b.left + b.width / 2)) * 0.3, y: (e.clientY - (b.top + b.height / 2)) * 0.3 });
  };

  return (
    <div>
      <div className="glass flex items-center gap-2 rounded-2xl p-2 shadow-glow">
        <Sparkles className="ml-2 h-5 w-5 shrink-0 text-indigo" />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={placeholder}
          className="focus-ring w-full bg-transparent px-1 py-2.5 text-[15px] text-ink placeholder:text-ink-faint focus:outline-none"
          aria-label="Ask a business question"
        />
        <motion.button
          ref={btnRef}
          onMouseMove={onMove}
          onMouseLeave={() => setMag({ x: 0, y: 0 })}
          animate={{ x: mag.x, y: mag.y }}
          transition={{ type: "spring", stiffness: 220, damping: 14 }}
          onClick={submit}
          disabled={busy}
          className="focus-ring grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-ai-gradient text-white disabled:opacity-50"
          aria-label="Submit question"
        >
          <ArrowUp className="h-5 w-5" />
        </motion.button>
      </div>
      <div className={`mt-3 flex-wrap gap-2 ${showExamples ? "flex" : "hidden"}`}>
        {EXAMPLES.map((ex, i) => (
          <motion.button
            key={ex}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
            onClick={() => {
              setValue(ex);
              onSubmit(ex);
            }}
            disabled={busy}
            className="rounded-full border border-line bg-surface/60 px-3 py-1.5 text-xs text-ink-dim transition-colors hover:border-indigo/40 hover:text-ink disabled:opacity-50"
          >
            {ex}
          </motion.button>
        ))}
      </div>
    </div>
  );
}
