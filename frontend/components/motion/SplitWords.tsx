"use client";
import { motion, useReducedMotion } from "motion/react";

/**
 * Per-word rise-and-clip reveal for hero headlines. Words stay real text
 * (screen readers and crawlers see the sentence, not spans of letters).
 */
export default function SplitWords({
  text,
  className,
  delay = 0,
  stagger = 0.07,
}: {
  text: string;
  className?: string;
  delay?: number;
  stagger?: number;
}) {
  const reduced = useReducedMotion();
  const words = text.split(" ");
  return (
    <span className={className} aria-label={text} role="text">
      {words.map((w, i) => (
        <span key={i} className="inline-block overflow-hidden pb-[0.08em] align-bottom">
          <motion.span
            className="inline-block will-change-transform"
            initial={reduced ? false : { y: "110%" }}
            animate={{ y: 0 }}
            transition={{
              delay: delay + i * stagger,
              duration: 0.65,
              ease: [0.22, 1, 0.36, 1],
            }}
            aria-hidden
          >
            {w}
          </motion.span>
          {i < words.length - 1 ? " " : null}
        </span>
      ))}
    </span>
  );
}
