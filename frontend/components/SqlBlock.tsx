"use client";
import { useState } from "react";
import { motion } from "motion/react";
import { Check, Copy, ShieldCheck } from "lucide-react";

const KEYWORDS =
  /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|JOIN|ON|LIMIT|AS|AND|OR|DESC|ASC|COUNT|SUM|AVG|ROUND|DISTINCT|WITH|CASE|WHEN|THEN|ELSE|END|NULLS|FIRST|LAST)\b/g;

function highlight(sql: string) {
  const esc = sql.replace(/</g, "&lt;");
  return esc
    .replace(KEYWORDS, '<span class="text-indigo">$1</span>')
    .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="text-cyan">$1</span>')
    .replace(/('[^']*')/g, '<span class="text-pos">$1</span>');
}

export default function SqlBlock({
  sql,
  validated = true,
}: {
  sql: string;
  validated?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-[#0E1117]">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="font-mono text-xs text-ink-faint">generated SQL</span>
        <div className="flex items-center gap-2">
          {validated && (
            <motion.span
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 20 }}
              className="flex items-center gap-1 rounded-full border border-pos/30 bg-pos/10 px-2 py-0.5 text-[11px] font-medium text-pos"
            >
              <ShieldCheck className="h-3 w-3" /> validated read-only
            </motion.span>
          )}
          <button
            onClick={copy}
            className="focus-ring flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink-dim hover:text-ink"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-pos" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed text-ink">
        <code dangerouslySetInnerHTML={{ __html: highlight(sql) }} />
      </pre>
    </div>
  );
}
