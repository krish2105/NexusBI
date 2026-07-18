"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

export type Theme = "dark" | "light";

const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({
  theme: "dark",
  toggle: () => {},
});

/** Matches the no-flash inline script in app/layout.tsx. */
const STORAGE_KEY = "nexus-theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // The inline <script> in layout.tsx has already stamped data-theme before
  // hydration, so read the resolved value instead of re-deriving it.
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    if (current === "light" || current === "dark") setTheme(current);
  }, []);

  // Follow OS preference live — but only while the user has no explicit choice.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      if (localStorage.getItem(STORAGE_KEY)) return;
      const next: Theme = mq.matches ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      setTheme(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      const root = document.documentElement;
      // Enable a brief color crossfade, then clean the class up.
      root.classList.add("theme-switching");
      root.dataset.theme = next;
      localStorage.setItem(STORAGE_KEY, next);
      window.setTimeout(() => root.classList.remove("theme-switching"), 400);
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
