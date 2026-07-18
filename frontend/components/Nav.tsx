"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Menu, Sparkles, X } from "lucide-react";

const LINKS = [
  { href: "/briefing", label: "Briefing" },
  { href: "/app", label: "Workspace" },
  { href: "/dashboards", label: "Dashboards" },
  { href: "/segments", label: "Segments" },
  { href: "/monitors", label: "Monitors" },
  { href: "/trust", label: "Trust" },
  { href: "/connections", label: "Data" },
];

export default function Nav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setOpen(false);
  }, [path]);

  // Lock body scroll while the drawer is open.
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const isActive = (href: string) => path === href || path?.startsWith(href + "/");

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

        {/* desktop links */}
        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`focus-ring relative rounded-lg px-3 py-1.5 text-sm transition-colors ${
                isActive(l.href) ? "text-ink" : "text-ink-dim hover:text-ink"
              }`}
            >
              {isActive(l.href) && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 -z-10 rounded-lg bg-white/[0.06]"
                />
              )}
              <span className="relative">{l.label}</span>
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/app"
            className="focus-ring hidden rounded-lg bg-ai-gradient px-4 py-1.5 text-sm font-medium text-white shadow-glow sm:block"
          >
            Launch
          </Link>
          {/* mobile hamburger — hidden on md+ */}
          <button
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="focus-ring grid h-9 w-9 place-items-center rounded-lg border border-line text-ink-dim md:hidden"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      {/* mobile drawer */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
              className="fixed inset-0 -z-10 bg-base/90 backdrop-blur-md md:hidden"
            />
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              className="absolute inset-x-4 top-[4.75rem] rounded-2xl border border-line bg-surface p-2 shadow-2xl md:hidden"
            >
              <div className="flex flex-col">
                {LINKS.map((l) => (
                  <Link
                    key={l.href}
                    href={l.href}
                    className={`focus-ring rounded-lg px-4 py-3 text-sm transition-colors ${
                      isActive(l.href)
                        ? "bg-white/[0.06] text-ink"
                        : "text-ink-dim hover:bg-white/[0.04] hover:text-ink"
                    }`}
                  >
                    {l.label}
                  </Link>
                ))}
                <Link
                  href="/app"
                  className="focus-ring mt-1 rounded-lg bg-ai-gradient px-4 py-3 text-center text-sm font-medium text-white"
                >
                  Launch workspace
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
