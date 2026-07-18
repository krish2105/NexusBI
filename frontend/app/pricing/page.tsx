"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Sparkles } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { startCheckout } from "@/lib/api";

const FREE = [
  "50 questions per day",
  "Up to 2 connections",
  "Zero-key deterministic engine",
  "Full 5-layer SQL safety guard",
  "Forecasts, anomalies, segments, dashboards",
  "Governed semantic layer",
];
const PRO = [
  "Unlimited questions",
  "Unlimited connections",
  "Bring your own LLM key (better accuracy)",
  "Everything in Free",
  "Priority support",
];

export default function PricingPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const upgrade = async () => {
    if (!user) {
      router.push("/signup");
      return;
    }
    setBusy(true);
    try {
      const r = await startCheckout();
      if (r.url) window.location.href = r.url;
      else router.push("/account");
    } catch {
      router.push("/account");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-3xl px-4 pb-24 pt-28">
      <div className="text-center">
        <h1 className="text-4xl font-semibold tracking-tight">Simple pricing</h1>
        <p className="mt-2 text-ink-dim">
          The free tier is the whole product, not a teaser. Upgrade only when you outgrow
          the caps.
        </p>
      </div>

      <div className="mt-10 grid gap-5 sm:grid-cols-2">
        {/* Free */}
        <div className="card flex flex-col p-6">
          <h2 className="text-lg font-medium">Free</h2>
          <p className="mt-1 text-3xl font-semibold">
            $0<span className="text-base font-normal text-ink-dim">/mo</span>
          </p>
          <ul className="mt-5 flex flex-col gap-2 text-sm text-ink-dim">
            {FREE.map((f) => (
              <li key={f} className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-ink-faint" /> {f}
              </li>
            ))}
          </ul>
          <button
            onClick={() => router.push(user ? "/app" : "/signup")}
            className="focus-ring mt-6 rounded-lg border border-line py-2.5 text-sm font-medium text-ink hover:bg-white/[0.04]"
          >
            {user ? "Go to workspace" : "Get started free"}
          </button>
        </div>

        {/* Pro */}
        <div className="card gradient-border relative flex flex-col p-6">
          <span className="absolute right-5 top-5 rounded-full bg-ai-gradient px-2.5 py-0.5 text-[11px] font-medium text-white">
            Most capable
          </span>
          <h2 className="text-lg font-medium">Pro</h2>
          <p className="mt-1 text-3xl font-semibold">
            $29<span className="text-base font-normal text-ink-dim">/seat/mo</span>
          </p>
          <ul className="mt-5 flex flex-col gap-2 text-sm text-ink-dim">
            {PRO.map((f) => (
              <li key={f} className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan" /> {f}
              </li>
            ))}
          </ul>
          <button
            onClick={upgrade}
            disabled={busy}
            className="focus-ring mt-6 flex items-center justify-center gap-1.5 rounded-lg bg-ai-gradient py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" /> {user ? "Upgrade to Pro" : "Start with Pro"}
          </button>
        </div>
      </div>

      <p className="mt-8 text-center text-xs text-ink-faint">
        Prices in USD. Cancel anytime. Read-only by design — Nexus never writes to your
        database. See the <a href="/legal#terms" className="text-ink-dim hover:underline">Terms</a>.
      </p>
    </main>
  );
}
