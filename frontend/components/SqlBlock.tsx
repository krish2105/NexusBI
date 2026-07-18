"use client";
import { useState } from "react";
import { motion } from "motion/react";
import { Check, Copy, ShieldCheck } from "lucide-react";

const KEYWORDS =
  /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|JOIN|ON|LIMIT|AS|AND|OR|DESC|ASC|COUNT|SUM|AVG|ROUND|DISTINCT|WITH|CASE|WHEN|THEN|ELSE|END|NULLS|FIRST|LAST)\b/g;

// Fixed colors on purpose: the code panel stays dark in BOTH themes, so the
// syntax palette must not follow the page tokens.
function highlight(sql: string) {
  const esc = sql.replace(/</g, "&lt;");
  return esc
    .replace(KEYWORDS, '<span style="color:#A5B4FC">$1</span>')
    .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span style="color:#67E8F9">$1</span>')
    .replace(/('[^']*')/g, '<span style="color:#6EE7B7">$1</span>');
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
    <div className="code-panel overflow-hidden rounded-xl">
      <div className="flex items-center justify-between border-b border-[#242A38] px-3 py-2">
        <span className="font-mono text-xs text-[#5E6678]">generated SQL</span>
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
            className="focus-ring flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[#9BA3B4] hover:text-[#E7EAF0]"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-[#34D399]" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed text-[#E7EAF0]">
        <code dangerouslySetInnerHTML={{ __html: highlight(sql) }} />
      </pre>
    </div>
  );
}
