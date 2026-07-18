"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { LayoutGrid, ArrowRight, Sparkles, Loader2, Wand2 } from "lucide-react";
import Link from "next/link";
import { generateDashboard } from "@/lib/api";

const IDEAS = [
  "An executive overview",
  "A delivery performance dashboard",
  "Sales dashboard for the North region",
  "Customer insights",
];

export default function Dashboards() {
  const [dashboards, setDashboards] = useState<any[]>([]);
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const load = () =>
    fetch("/api/dashboards")
      .then((r) => r.json())
      .then((d) => setDashboards(d.dashboards || []))
      .catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const generate = async (d: string) => {
    if (!d.trim() || busy) return;
    setBusy(true);
    try {
      const res = await generateDashboard(d.trim());
      router.push(`/dashboards/${res.dashboard_id}`);
    } catch {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
        <LayoutGrid className="h-7 w-7 text-indigo" /> Dashboards
      </h1>
      <p className="mt-2 text-ink-dim">
        Describe a dashboard in plain English — Nexus composes it by running a
        themed set of safe queries and pinning the results.
      </p>

      {/* NL generator */}
      <div className="mt-6">
        <div className="glass flex items-center gap-2 rounded-2xl p-2 shadow-glow">
          <Wand2 className="ml-2 h-5 w-5 shrink-0 text-indigo" />
          <input
            ref={inputRef}
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && generate(desc)}
            placeholder="Describe a dashboard… (e.g. a delivery dashboard for the North region)"
            className="focus-ring w-full bg-transparent px-1 py-2.5 text-[15px] text-ink placeholder:text-ink-faint focus:outline-none"
            disabled={busy}
          />
          <button
            onClick={() => generate(desc)}
            disabled={busy}
            className="focus-ring flex shrink-0 items-center gap-1.5 rounded-xl bg-ai-gradient px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {busy ? "Composing…" : "Generate"}
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {IDEAS.map((ex) => (
            <button
              key={ex}
              onClick={() => generate(ex)}
              disabled={busy}
              className="rounded-full border border-line bg-surface/60 px-3 py-1.5 text-xs text-ink-dim transition-colors hover:border-indigo/40 hover:text-ink disabled:opacity-50"
            >
              {ex}
            </button>
          ))}
        </div>
        {busy && (
          <p className="mt-3 flex items-center gap-2 text-sm text-ink-dim">
            <span className="h-2 w-2 animate-pulse rounded-full bg-indigo" />
            Running the queries and composing your dashboard…
          </p>
        )}
      </div>

      {/* existing dashboards */}
      {dashboards.length > 0 && (
        <div className="mt-10">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-faint">
            Your dashboards
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {dashboards.map((d, i) => (
              <motion.div
                key={d.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link
                  href={`/dashboards/${d.id}`}
                  className="card gradient-border relative block p-5 hover:shadow-glow"
                >
                  <p className="font-medium">{d.name}</p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-ink-faint">
                    Open <ArrowRight className="h-3 w-3" />
                  </p>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
