"use client";
import { useTheme } from "@/components/ThemeProvider";

/**
 * Concrete per-theme colors for SVG-rendered charts (recharts sets fill/stroke
 * as attributes, where CSS variables are unreliable — so charts consume this
 * hook and re-render on toggle instead).
 */
const DARK = {
  axis: "#5E6678",
  grid: "#1B1F2A",
  tooltipBg: "#14171F",
  tooltipBorder: "#242A38",
  label: "#9BA3B4",
  indigo: "#6366F1",
  cyan: "#22D3EE",
  pos: "#34D399",
  neg: "#F87171",
  amber: "#FBBF24",
  neutral: "#9BA3B4",
  track: "#242A38",
  cursorFill: "rgba(99,102,241,0.08)",
  bandOpacity: [0.25, 0.02] as readonly [number, number],
  segments: {
    Champions: "#34D399",
    Loyal: "#22D3EE",
    "Potential Loyalist": "#818CF8",
    "New / Promising": "#A78BFA",
    "At Risk": "#FBBF24",
    "Can't Lose": "#FB923C",
    Hibernating: "#94A3B8",
    Lost: "#F87171",
  } as Record<string, string>,
};

const LIGHT: typeof DARK = {
  axis: "#949CAD",
  grid: "#E6E9F2",
  tooltipBg: "#FFFFFF",
  tooltipBorder: "#E0E4EE",
  label: "#5A6478",
  indigo: "#4F46E5",
  cyan: "#0E7490",
  pos: "#059669",
  neg: "#DC2626",
  amber: "#D97706",
  neutral: "#64748B",
  track: "#E0E4EE",
  cursorFill: "rgba(79,70,229,0.07)",
  bandOpacity: [0.18, 0.02] as readonly [number, number],
  segments: {
    Champions: "#059669",
    Loyal: "#0E7490",
    "Potential Loyalist": "#4F46E5",
    "New / Promising": "#7C3AED",
    "At Risk": "#D97706",
    "Can't Lose": "#EA580C",
    Hibernating: "#64748B",
    Lost: "#DC2626",
  },
};

export type ChartTheme = typeof DARK;

export function useChartTheme(): ChartTheme {
  const { theme } = useTheme();
  return theme === "light" ? LIGHT : DARK;
}

/** Shared recharts Tooltip props, themed. */
export function tooltipProps(c: ChartTheme) {
  return {
    contentStyle: {
      background: c.tooltipBg,
      border: `1px solid ${c.tooltipBorder}`,
      borderRadius: 10,
      fontSize: 12,
      boxShadow: "0 8px 24px -8px rgba(0,0,0,0.25)",
    },
    labelStyle: { color: c.label },
    itemStyle: { color: c.label },
  };
}
