"use client";
import { useEffect, useState } from "react";
import { Activity, CheckCircle2, MinusCircle, AlertTriangle } from "lucide-react";
import { getStatus } from "@/lib/api";
import { CardSkeleton, ErrorState } from "@/components/States";

const DOT: Record<string, { icon: any; cls: string; label: string }> = {
  ok: { icon: CheckCircle2, cls: "text-pos", label: "Operational" },
  off: { icon: MinusCircle, cls: "text-ink-faint", label: "Not configured" },
  degraded: { icon: AlertTriangle, cls: "text-neg", label: "Degraded" },
};

export default function StatusPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setErr(null);
    getStatus()
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const overall = data?.status;

  return (
    <main className="mx-auto max-w-3xl px-4 pb-20 pt-28">
      <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
        <Activity className="h-7 w-7 text-indigo" /> System status
      </h1>
      {overall && (
        <div
          className={`mt-4 flex items-center gap-2 rounded-xl border px-4 py-3 text-sm ${
            overall === "ok"
              ? "border-pos/25 bg-pos/5 text-ink-dim"
              : "border-neg/30 bg-neg/10 text-neg"
          }`}
        >
          {overall === "ok" ? (
            <CheckCircle2 className="h-4 w-4 text-pos" />
          ) : (
            <AlertTriangle className="h-4 w-4" />
          )}
          {overall === "ok"
            ? "All systems operational."
            : "Some components are degraded."}
        </div>
      )}

      <div className="mt-6 flex flex-col gap-2">
        {loading && (
          <>
            <CardSkeleton />
            <CardSkeleton />
          </>
        )}
        {!loading && err && <ErrorState message={err} onRetry={load} />}
        {!loading &&
          data &&
          Object.entries(data.components as Record<string, any>).map(([name, c]) => {
            const d = DOT[c.status] ?? DOT.off;
            const Icon = d.icon;
            const detail = c.provider || c.backend || c.mode || c.guard || c.detail;
            return (
              <div
                key={name}
                className="card flex items-center justify-between p-4"
              >
                <div>
                  <p className="font-medium capitalize">{name.replace(/_/g, " ")}</p>
                  {detail && (
                    <p className="text-xs text-ink-dim">{String(detail)}</p>
                  )}
                </div>
                <span className={`flex items-center gap-1.5 text-sm ${d.cls}`}>
                  <Icon className="h-4 w-4" /> {d.label}
                </span>
              </div>
            );
          })}
      </div>
      <p className="mt-6 text-xs text-ink-faint">
        Point an uptime monitor (UptimeRobot free tier) at{" "}
        <code className="text-cyan">/status</code> — it returns HTTP 200 with a
        per-component readout. Optional services show &quot;Not configured&quot; on the
        free tier; that&apos;s expected, not an outage.
      </p>
    </main>
  );
}
