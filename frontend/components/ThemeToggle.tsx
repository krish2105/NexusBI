"use client";
import { motion } from "motion/react";
import { useTheme } from "./ThemeProvider";

const RAYS = [0, 45, 90, 135, 180, 225, 270, 315];

/**
 * Sun ⇄ moon morph: one disc whose masking "bite" slides in for the crescent,
 * rays that scale/fade out. Pattern per 21st.dev's animated-theme-toggle
 * family, implemented natively on Motion so it follows our token system.
 */
export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
      className="focus-ring grid h-9 w-9 place-items-center rounded-lg border border-line text-ink-dim transition-colors hover:text-ink"
    >
      <motion.svg
        viewBox="0 0 24 24"
        className="h-[18px] w-[18px]"
        initial={false}
        animate={{ rotate: dark ? -40 : 0 }}
        transition={{ type: "spring", stiffness: 200, damping: 18 }}
      >
        <mask id="moon-bite">
          <rect x="0" y="0" width="24" height="24" fill="#fff" />
          {/* the bite that turns the disc into a crescent */}
          <motion.circle
            r="8"
            fill="#000"
            initial={false}
            animate={{ cx: dark ? 17 : 30, cy: dark ? 6 : 0 }}
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
          />
        </mask>
        <motion.circle
          cx="12"
          cy="12"
          fill="currentColor"
          mask="url(#moon-bite)"
          initial={false}
          animate={{ r: dark ? 8 : 5 }}
          transition={{ type: "spring", stiffness: 200, damping: 20 }}
        />
        <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          {RAYS.map((deg) => (
            <motion.line
              key={deg}
              x1="12"
              y1="3.2"
              x2="12"
              y2="5.2"
              transform={`rotate(${deg} 12 12)`}
              initial={false}
              animate={{ opacity: dark ? 0 : 1, scale: dark ? 0.4 : 1 }}
              transition={{ duration: 0.25, delay: dark ? 0 : 0.15 }}
              style={{ transformOrigin: "12px 12px" }}
            />
          ))}
        </g>
      </motion.svg>
    </button>
  );
}
