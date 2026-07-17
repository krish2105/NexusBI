"use client";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Sparkles } from "lucide-react";
import QueryBar from "@/components/QueryBar";
import AgentStepper from "@/components/AgentStepper";
import ResultCanvas from "@/components/ResultCanvas";
import { streamQuery, createDashboard, pinToDashboard } from "@/lib/api";
import type { AgentEvent, AnalysisResult } from "@/lib/types";

export default function Workspace() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const ask = async (q: string) => {
    setBusy(true);
    setResult(null);
    setEvents([]);
    setQuestion(q);
    try {
      const final = await streamQuery(q, (ev) => setEvents((p) => [...p, ev]));
      setResult(final);
    } catch (e) {
      setToast("Could not reach the Nexus backend. Is it running on :8000?");
    } finally {
      setBusy(false);
    }
  };

  // Shareable insight links: /app?q=... auto-runs the question on load.
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) ask(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pin = async (r: AnalysisResult) => {
    try {
      const dash = await createDashboard("Exec Overview");
      await pinToDashboard(dash.id, r.query_id);
      setToast("Pinned to a new dashboard →");
      setTimeout(() => setToast(null), 2600);
    } catch {
      setToast("Pin failed.");
    }
  };

  return (
    <main className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 gap-6 px-4 pb-16 pt-28 lg:grid-cols-[340px_1fr]">
      {/* left: query + pipeline */}
      <div className="flex flex-col gap-6">
        <QueryBar onSubmit={ask} busy={busy} />
        <div className="card p-4">
          <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
            <Sparkles className="h-3.5 w-3.5 text-indigo" /> Analysis pipeline
          </p>
          <AgentStepper events={events} active={busy} />
        </div>
      </div>

      {/* right: canvas */}
      <div className="min-w-0">
        <AnimatePresence mode="wait">
          {result ? (
            <motion.div key="result">
              <p className="mb-3 text-sm text-ink-dim">
                <span className="text-ink-faint">You asked:</span> {question}
              </p>
              <ResultCanvas result={result} onPin={pin} />
            </motion.div>
          ) : busy ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid h-64 place-items-center text-ink-dim"
            >
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 animate-pulse rounded-full bg-indigo" />
                Nexus is analysing your question…
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid h-64 place-items-center text-center"
            >
              <div>
                <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-ai-gradient shadow-glow">
                  <Sparkles className="h-6 w-6 text-white" />
                </div>
                <p className="text-lg font-medium">Ask a question to begin</p>
                <p className="mt-1 text-sm text-ink-dim">
                  Nexus writes safe SQL, runs it, forecasts, and explains the result.
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="glass fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl px-4 py-2.5 text-sm"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
