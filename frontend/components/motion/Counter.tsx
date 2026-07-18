"use client";
import { useEffect, useRef } from "react";
import {
  animate,
  useInView,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from "motion/react";
import { motion } from "motion/react";

/** Counts from 0 to `to` when scrolled into view. */
export default function Counter({
  to,
  prefix = "",
  suffix = "",
  duration = 1.6,
  className,
}: {
  to: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) =>
    `${prefix}${Math.round(v).toLocaleString()}${suffix}`,
  );

  useEffect(() => {
    if (!inView) return;
    if (reduced) {
      mv.set(to);
      return;
    }
    const controls = animate(mv, to, { duration, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [inView, reduced, to, duration, mv]);

  return (
    <motion.span ref={ref} className={className}>
      {text}
    </motion.span>
  );
}
