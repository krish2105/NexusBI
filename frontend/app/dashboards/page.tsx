"use client";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { LayoutGrid, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function Dashboards() {
  const [dashboards, setDashboards] = useState<any[]>([]);
  useEffect(() => {
    fetch("/api/dashboards")
      .then((r) => r.json())
      .then((d) => setDashboards(d.dashboards || []))
      .catch(() => {});
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
        <LayoutGrid className="h-7 w-7 text-indigo" /> Dashboards
      </h1>
      <p className="mt-2 text-ink-dim">
        Pin any answer from the workspace. Dashboards re-run their pinned queries
        against live data every time you open them.
      </p>

      {dashboards.length === 0 ? (
        <div className="mt-10 grid place-items-center rounded-2xl border border-dashed border-line py-20 text-center">
          <div>
            <p className="text-lg font-medium">No dashboards yet</p>
            <p className="mt-1 text-sm text-ink-dim">
              Ask a question, then hit <b>Pin</b> to create your first one.
            </p>
            <Link
              href="/app"
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-ai-gradient px-4 py-2.5 text-sm font-medium text-white shadow-glow"
            >
              Open the workspace <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      ) : (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {dashboards.map((d, i) => (
            <motion.div
              key={d.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Link href={`/dashboards/${d.id}`} className="card gradient-border relative block p-5 hover:shadow-glow">
                <p className="font-medium">{d.name}</p>
                <p className="mt-1 text-xs text-ink-faint">Live · click to open</p>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </main>
  );
}
