"use client";
import { useEffect, useState } from "react";
import { motion, useMotionValue, animate } from "motion/react";

export default function KpiCard({ label, value }: { label: string; value: number }) {
  const mv = useMotionValue(0);
  const [display, setDisplay] = useState("0");
  useEffect(() => {
    const controls = animate(mv, value, {
      duration: 1.1,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        setDisplay(
          v >= 1000
            ? Math.round(v).toLocaleString()
            : v.toLocaleString(undefined, { maximumFractionDigits: 2 }),
        );
      },
    });
    return () => controls.stop();
  }, [value, mv]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      className="card flex flex-col items-center justify-center gap-2 p-8"
    >
      <span className="font-mono text-5xl font-semibold tracking-tight gradient-text">
        {display}
      </span>
      <span className="text-sm uppercase tracking-wide text-ink-dim">
        {label.replace(/_/g, " ")}
      </span>
    </motion.div>
  );
}
