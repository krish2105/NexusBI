"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { Sparkles } from "lucide-react";

const LINKS = [
  { href: "/app", label: "Workspace" },
  { href: "/dashboards", label: "Dashboards" },
  { href: "/connections", label: "Connections" },
  { href: "/history", label: "History" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4"
    >
      <nav className="glass flex w-full max-w-6xl items-center justify-between rounded-2xl px-4 py-2.5">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-ai-gradient">
            <Sparkles className="h-4 w-4 text-white" />
          </span>
          <span className="tracking-tight">
            Nexus<span className="gradient-text"> BI</span>
          </span>
        </Link>
        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => {
            const active = path === l.href || path?.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`focus-ring rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  active ? "text-ink" : "text-ink-dim hover:text-ink"
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 -z-10 rounded-lg bg-white/[0.06]"
                  />
                )}
                <span className="relative">{l.label}</span>
              </Link>
            );
          })}
        </div>
        <Link
          href="/app"
          className="focus-ring rounded-lg bg-ai-gradient px-4 py-1.5 text-sm font-medium text-white shadow-glow"
        >
          Launch
        </Link>
      </nav>
    </motion.header>
  );
}
