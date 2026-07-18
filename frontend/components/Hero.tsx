"use client";
import { useRef } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "motion/react";
import { useChartTheme } from "@/lib/chartTheme";

/**
 * "The Data Landscape" — an isometric field of bars whose heights are data,
 * rising in a stagger with a sweeping query beam, tilting gently toward the
 * cursor. SVG progressive-enhancement: no WebGL, honors reduced motion,
 * always renders, re-themes via the chart palette.
 */
const COLS = 12;
const ROWS = 6;

function heightFor(c: number, r: number) {
  const wave = Math.sin(c * 0.6) * Math.cos(r * 0.8);
  return 14 + (wave + 1) * 26; // 14..66
}

export default function Hero() {
  const theme = useChartTheme();
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  // Pointer-driven tilt (springed; zeroed for reduced motion / touch).
  const mx = useMotionValue(0.5);
  const my = useMotionValue(0.5);
  const rotX = useSpring(useTransform(my, [0, 1], [5, -5]), {
    stiffness: 120,
    damping: 18,
  });
  const rotY = useSpring(useTransform(mx, [0, 1], [-7, 7]), {
    stiffness: 120,
    damping: 18,
  });

  const onMove = (e: React.PointerEvent) => {
    if (reduced || e.pointerType === "touch") return;
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    mx.set((e.clientX - r.left) / r.width);
    my.set((e.clientY - r.top) / r.height);
  };
  const onLeave = () => {
    mx.set(0.5);
    my.set(0.5);
  };

  const cells: { x: number; y: number; h: number; i: number; diag: number }[] = [];
  let i = 0;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const x = (c - r) * 26 + 360;
      const y = (c + r) * 14 + 60;
      cells.push({ x, y, h: heightFor(c, r), i: i++, diag: c + r });
    }
  }

  return (
    <motion.div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{
        rotateX: reduced ? 0 : rotX,
        rotateY: reduced ? 0 : rotY,
        transformPerspective: 900,
      }}
      className="h-full w-full will-change-transform"
    >
      <svg viewBox="0 0 720 420" className="h-full w-full" aria-hidden role="presentation">
        <defs>
          <linearGradient id="barTop" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={theme.indigo} />
            <stop offset="100%" stopColor={theme.cyan} />
          </linearGradient>
        </defs>

        {cells.map(({ x, y, h, i, diag }) => (
          <motion.g
            key={i}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 + i * 0.012, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          >
            {/* left face */}
            <path
              d={`M${x} ${y} L${x} ${y - h} L${x - 13} ${y - h + 7} L${x - 13} ${y + 7} Z`}
              className="fill-surface-2 stroke-line"
              strokeWidth="0.5"
            />
            {/* right face */}
            <path
              d={`M${x} ${y} L${x} ${y - h} L${x + 13} ${y - h + 7} L${x + 13} ${y + 7} Z`}
              className="fill-surface stroke-line"
              strokeWidth="0.5"
            />
            {/* top */}
            <path
              d={`M${x} ${y - h} L${x - 13} ${y - h + 7} L${x} ${y - h + 14} L${x + 13} ${y - h + 7} Z`}
              fill="url(#barTop)"
              opacity={0.9}
            />
            {/* query wave: a cyan pulse travelling diagonally across the tops */}
            {!reduced && (
              <motion.path
                d={`M${x} ${y - h} L${x - 13} ${y - h + 7} L${x} ${y - h + 14} L${x + 13} ${y - h + 7} Z`}
                fill={theme.cyan}
                initial={{ opacity: 0 }}
                animate={{ opacity: [0, 0.85, 0] }}
                transition={{
                  duration: 1.1,
                  delay: 1.6 + diag * 0.13,
                  repeat: Infinity,
                  repeatDelay: 4.9,
                  ease: "easeInOut",
                }}
              />
            )}
          </motion.g>
        ))}
      </svg>
    </motion.div>
  );
}
