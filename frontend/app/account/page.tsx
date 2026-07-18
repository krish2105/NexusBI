"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CreditCard, KeyRound, Gauge, LogOut, Sparkles } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import {
  getAccount,
  setByoKey,
  clearByoKey,
  startCheckout,
  openBillingPortal,
} from "@/lib/api";
import { CardSkeleton, ErrorState } from "@/components/States";

function Meter({ used, limit, label }: { used: number; limit: number | null; label: string }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-ink-dim">
        <span>{label}</span>
        <span>
          {used}
          {limit != null ? ` / ${limit}` : " · unlimited"}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full ${pct >= 100 ? "bg-neg" : "bg-ai-gradient"}`}
          style={{ width: limit ? `${pct}%` : "100%", opacity: limit ? 1 : 0.4 }}
        />
      </div>
    </div>
  );
}

export default function AccountPage() {
  const { user, loading: authLoading, logout, refresh } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [keyInput, setKeyInput] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    getAccount()
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "failed"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);
  useEffect(() => {
    if (user) load();
  }, [user]);

  if (authLoading || !user) return null;

  const usage = data?.usage;
  const isPro = usage?.plan === "pro";

  const upgrade = async () => {
    setBusy(true);
    try {
      const r = await startCheckout();
      if (r.url) window.location.href = r.url;
      else alert("Billing isn't configured on this deployment yet.");
    } catch (e) {
      alert(e instanceof Error ? e.message : "checkout failed");
    } finally {
      setBusy(false);
    }
  };
  const manage = async () => {
    const r = await openBillingPortal();
    if (r.url) window.location.href = r.url;
  };
  const saveKey = async () => {
    setBusy(true);
    try {
      await setByoKey("groq", keyInput.trim());
      setKeyInput("");
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "failed to save key");
    } finally {
      setBusy(false);
    }
  };
  const removeKey = async () => {
    await clearByoKey();
    load();
  };

  return (
    <main className="mx-auto max-w-2xl px-4 pb-20 pt-28">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Account</h1>
        <button
          onClick={() => {
            logout();
            router.push("/");
          }}
          className="focus-ring flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-ink-dim hover:text-ink"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>
      <p className="mt-1 text-sm text-ink-dim">{user.email}</p>

      {loading && (
        <div className="mt-6 flex flex-col gap-3">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}
      {!loading && err && <div className="mt-6"><ErrorState message={err} onRetry={load} /></div>}

      {!loading && usage && (
        <div className="mt-6 flex flex-col gap-4">
          {/* plan + usage */}
          <div className="card p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Gauge className="h-5 w-5 text-indigo" />
                <span className="font-medium">Plan &amp; usage</span>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  isPro
                    ? "bg-ai-gradient text-white"
                    : "border border-line text-ink-dim"
                }`}
              >
                {isPro ? "Pro" : "Free"}
              </span>
            </div>
            <div className="flex flex-col gap-3">
              <Meter used={usage.queries_today} limit={usage.daily_query_limit} label="Queries today" />
              <Meter used={usage.connections} limit={usage.connection_limit} label="Connections" />
            </div>
          </div>

          {/* billing */}
          <div id="billing" className="card scroll-mt-28 p-5">
            <div className="mb-2 flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-cyan" />
              <span className="font-medium">Billing</span>
            </div>
            {!usage.billing_enabled ? (
              <p className="text-sm text-ink-dim">
                Billing isn&apos;t configured on this deployment — every account is on the
                full-featured Free tier. See <Link href="/pricing" className="text-cyan hover:underline">pricing</Link>.
              </p>
            ) : isPro ? (
              <div className="flex items-center justify-between">
                <p className="text-sm text-ink-dim">You&apos;re on Pro — thank you.</p>
                <button onClick={manage} className="focus-ring rounded-lg border border-line px-3 py-1.5 text-sm text-ink-dim hover:text-ink">
                  Manage billing
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <p className="text-sm text-ink-dim">Upgrade for unlimited queries, more connections, and BYO-LLM-key.</p>
                <button
                  onClick={upgrade}
                  disabled={busy}
                  className="focus-ring flex items-center gap-1.5 rounded-lg bg-ai-gradient px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  <Sparkles className="h-4 w-4" /> Upgrade to Pro
                </button>
              </div>
            )}
          </div>

          {/* BYO LLM key */}
          <div className="card p-5">
            <div className="mb-2 flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-amber" />
              <span className="font-medium">Bring your own LLM key</span>
            </div>
            <p className="mb-3 text-sm text-ink-dim">
              Add a Groq key to run SQL generation on your own account (your usage, your
              cost). Stored encrypted at rest.
              {usage.billing_enabled && !isPro && " Pro feature."}
            </p>
            {usage.byo_llm_key ? (
              <div className="flex items-center justify-between rounded-lg border border-pos/25 bg-pos/5 px-3 py-2">
                <span className="text-sm text-pos">A key is saved and active.</span>
                <button onClick={removeKey} className="focus-ring text-xs text-ink-dim hover:text-neg">
                  Remove
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <input
                  type="password"
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  placeholder="gsk_…"
                  className="focus-ring flex-1 rounded-lg border border-line bg-surface/60 px-3 py-2 font-mono text-sm"
                />
                <button
                  onClick={saveKey}
                  disabled={busy || keyInput.trim().length < 10}
                  className="focus-ring rounded-lg bg-ai-gradient px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  Save
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
