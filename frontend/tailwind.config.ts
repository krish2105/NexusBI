import type { Config } from "tailwindcss";

// Every color resolves to a CSS variable declared in globals.css, so the whole
// app re-themes off <html data-theme="light|dark"> — including alpha utilities
// like bg-pos/10, because the variables hold raw RGB channels.
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: v("base"),
        surface: v("surface"),
        "surface-2": v("surface-2"),
        line: v("line"),
        ink: v("ink"),
        "ink-dim": v("ink-dim"),
        "ink-faint": v("ink-faint"),
        indigo: v("indigo"),
        cyan: v("cyan"),
        pos: v("pos"),
        neg: v("neg"),
        amber: v("amber"),
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgb(var(--indigo) / 0.25), 0 8px 40px -8px rgb(var(--indigo) / 0.35)",
        card: "var(--card-shadow)",
      },
      backgroundImage: {
        "ai-gradient":
          "linear-gradient(135deg, rgb(var(--indigo)) 0%, rgb(var(--cyan)) 100%)",
        "grid-fade":
          "radial-gradient(ellipse 80% 60% at 50% 0%, rgb(var(--indigo) / var(--grid-fade-opacity)), transparent 70%)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgb(var(--amber) / 0.5)" },
          "70%": { boxShadow: "0 0 0 8px rgb(var(--amber) / 0)" },
          "100%": { boxShadow: "0 0 0 0 rgb(var(--amber) / 0)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        "pulse-ring": "pulse-ring 1.8s infinite",
      },
    },
  },
  plugins: [],
};
export default config;
