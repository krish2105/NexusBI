"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { User, LogOut, CreditCard, ChevronDown } from "lucide-react";
import { useAuth } from "./AuthProvider";

export default function AuthNav() {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const path = usePathname();

  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  if (loading) return <div className="h-8 w-8 rounded-lg bg-white/[0.04]" />;

  if (!user) {
    return (
      <Link
        href="/login"
        className="focus-ring hidden rounded-lg px-3 py-1.5 text-sm text-ink-dim hover:text-ink sm:block"
      >
        Sign in
      </Link>
    );
  }

  const initial = user.email[0]?.toUpperCase() ?? "?";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="focus-ring flex items-center gap-1.5 rounded-lg border border-line px-1.5 py-1 text-sm text-ink-dim hover:text-ink"
        aria-label="Account menu"
      >
        <span className="grid h-6 w-6 place-items-center rounded-md bg-ai-gradient text-xs font-semibold text-white">
          {initial}
        </span>
        <ChevronDown className="h-3.5 w-3.5" />
      </button>
      {open && (
        <div className="absolute right-0 top-11 w-56 rounded-xl border border-line bg-surface p-1.5 shadow-2xl">
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium text-ink">{user.email}</p>
            <p className="text-[11px] uppercase tracking-wide text-ink-faint">
              {user.plan} plan
            </p>
          </div>
          <div className="my-1 h-px bg-line" />
          <Link
            href="/account"
            className="focus-ring flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-dim hover:bg-white/[0.04] hover:text-ink"
          >
            <User className="h-4 w-4" /> Account
          </Link>
          <Link
            href="/account#billing"
            className="focus-ring flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-dim hover:bg-white/[0.04] hover:text-ink"
          >
            <CreditCard className="h-4 w-4" /> Billing
          </Link>
          <button
            onClick={() => {
              logout();
              router.push("/");
            }}
            className="focus-ring flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-dim hover:bg-white/[0.04] hover:text-neg"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
