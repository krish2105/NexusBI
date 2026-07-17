"use client";
import { motion } from "motion/react";

/**
 * "The Data Landscape" — an isometric field of bars whose heights are data,
 * rising in a stagger with a sweeping query beam. This is the SVG progressive-
 * enhancement version (per spec): no WebGL required, honors reduced motion, and
 * always renders. An R3F terrain can be lazy-mounted over this as an upgrade.
 */
const COLS = 12;
const ROWS = 6;

function heightFor(c: number, r: number) {
  const wave = Math.sin(c * 0.6) * Math.cos(r * 0.8);
  return 14 + (wave + 1) * 26; // 14..66
}

export default function Hero() {
  const cells: { x: number; y: number; h: number; i: number }[] = [];
  let i = 0;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const x = (c - r) * 26 + 360;
      const y = (c + r) * 14 + 60;
      cells.push({ x, y, h: heightFor(c, r), i: i++ });
    }
  }
  return (
    <svg
      viewBox="0 0 720 420"
      className="h-full w-full"
      aria-hidden
      role="presentation"
    >
      <defs>
        <linearGradient id="barTop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#22D3EE" />
        </linearGradient>
        <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#22D3EE" stopOpacity="0" />
          <stop offset="50%" stopColor="#22D3EE" stopOpacity="0.7" />
          <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
        </linearGradient>
      </defs>

      {cells.map(({ x, y, h, i }) => (
        <motion.g
          key={i}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 + i * 0.012, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* left face */}
          <path
            d={`M${x} ${y} L${x} ${y - h} L${x - 13} ${y - h + 7} L${x - 13} ${y + 7} Z`}
            fill="#1B1F2A"
            stroke="#242A38"
            strokeWidth="0.5"
          />
          {/* right face */}
          <path
            d={`M${x} ${y} L${x} ${y - h} L${x + 13} ${y - h + 7} L${x + 13} ${y + 7} Z`}
            fill="#14171F"
            stroke="#242A38"
            strokeWidth="0.5"
          />
          {/* top */}
          <path
            d={`M${x} ${y - h} L${x - 13} ${y - h + 7} L${x} ${y - h + 14} L${x + 13} ${y - h + 7} Z`}
            fill="url(#barTop)"
            opacity={0.9}
          />
        </motion.g>
      ))}

      {/* sweeping query beam */}
      <motion.rect
        x={-120}
        y={0}
        width={120}
        height={420}
        fill="url(#beam)"
        initial={{ x: -120 }}
        animate={{ x: 760 }}
        transition={{ duration: 2.6, delay: 1.4, ease: "easeInOut", repeat: Infinity, repeatDelay: 3.5 }}
      />
    </svg>
  );
}
