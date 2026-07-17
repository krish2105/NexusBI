import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0B0D12",
        surface: "#14171F",
        "surface-2": "#1B1F2A",
        line: "#242A38",
        ink: "#E7EAF0",
        "ink-dim": "#9BA3B4",
        "ink-faint": "#5E6678",
        indigo: "#6366F1",
        cyan: "#22D3EE",
        pos: "#34D399",
        neg: "#F87171",
        amber: "#FBBF24",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(99,102,241,0.25), 0 8px 40px -8px rgba(99,102,241,0.35)",
        card: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 12px 40px -16px rgba(0,0,0,0.6)",
      },
      backgroundImage: {
        "ai-gradient": "linear-gradient(135deg, #6366F1 0%, #22D3EE 100%)",
        "grid-fade":
          "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(99,102,241,0.12), transparent 70%)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(251,191,36,0.5)" },
          "70%": { boxShadow: "0 0 0 8px rgba(251,191,36,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(251,191,36,0)" },
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
