"use client";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Sparkles, Plus } from "lucide-react";
import QueryBar from "@/components/QueryBar";
import AgentStepper from "@/components/AgentStepper";
import TurnCard from "@/components/TurnCard";
import ConnectionPicker from "@/components/ConnectionPicker";
import {
  streamQuery,
  createConversation,
  createDashboard,
  pinToDashboard,
} from "@/lib/api";
import type { AgentEvent, AnalysisResult } from "@/lib/types";

interface Turn {
  question: string;
  result: AnalysisResult;
}

export default function Workspace() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [connectionId, setConnectionId] = useState("demo");
  const convRef = useRef<string | null>(null);
  const connRef = useRef("demo");
  connRef.current = connectionId;
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, pending, events]);

  // Shareable links: /app?q=... auto-runs the question on load.
  const ranRef = useRef(false);
  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) ask(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ask = async (q: string) => {
    setBusy(true);
    setPending(q);
    setEvents([]);
    try {
      if (!convRef.current) {
        const conv = await createConversation(connRef.current);
        convRef.current = conv.id;
      }
      const final = await streamQuery(
        q,
        (ev) => setEvents((p) => [...p, ev]),
        connRef.current,
        convRef.current,
      );
      if (final) setTurns((p) => [...p, { question: q, result: final }]);
    } catch {
      setToast("Could not reach the Nexus backend. Is it running on :8000?");
    } finally {
      setBusy(false);
      setPending(null);
      setEvents([]);
    }
  };

  const newConversation = () => {
    convRef.current = null;
    setTurns([]);
    setEvents([]);
    setPending(null);
  };

  const switchConnection = (id: string) => {
    setConnectionId(id);
    newConversation(); // a thread belongs to one dataset
  };

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

  const empty = turns.length === 0 && !pending;

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 pb-40 pt-24">
      {/* controls */}
      <div className="sticky top-20 z-30 -mx-4 mb-4 flex items-center gap-2 bg-base/80 px-4 py-2 backdrop-blur">
        <div className="flex-1">
          <ConnectionPicker value={connectionId} onChange={switchConnection} />
        </div>
        {turns.length > 0 && (
          <button
            onClick={newConversation}
            className="focus-ring flex shrink-0 items-center gap-1.5 rounded-xl border border-line bg-surface/60 px-3 py-2 text-sm text-ink-dim hover:text-ink"
          >
            <Plus className="h-4 w-4" /> New chat
          </button>
        )}
      </div>

      {/* thread */}
      <div className="flex flex-1 flex-col gap-8">
        {empty && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid flex-1 place-items-center py-16 text-center"
          >
            <div>
              <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-ai-gradient shadow-glow">
                <Sparkles className="h-6 w-6 text-white" />
              </div>
              <p className="text-lg font-medium">Start a conversation with your data</p>
              <p className="mt-1 text-sm text-ink-dim">
                Ask a question, then follow up — &ldquo;now just the North region&rdquo;,
                &ldquo;break it down by category&rdquo;, &ldquo;why did it change?&rdquo;
              </p>
            </div>
          </motion.div>
        )}

        {turns.map((t, i) => (
          <TurnCard
            key={i}
            question={t.question}
            result={t.result}
            onPin={pin}
            onFollowup={ask}
          />
        ))}

        {/* active turn */}
        <AnimatePresence>
          {pending && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-3"
            >
              <p className="text-[15px] font-medium text-ink">{pending}</p>
              <div className="card p-4">
                <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                  <Sparkles className="h-3.5 w-3.5 text-indigo" /> Analysing…
                </p>
                <AgentStepper events={events} active />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* input (pinned) */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-base/80 backdrop-blur">
        <div className="mx-auto max-w-3xl px-4 py-4">
          <QueryBar
            onSubmit={ask}
            busy={busy}
            placeholder={
              turns.length > 0
                ? "Ask a follow-up… (e.g. why did it change?)"
                : "Ask your data anything…"
            }
            showExamples={empty}
          />
        </div>
      </div>

      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="glass fixed bottom-28 left-1/2 z-50 -translate-x-1/2 rounded-xl px-4 py-2.5 text-sm"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
