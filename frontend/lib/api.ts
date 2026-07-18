import type { AgentEvent, AnalysisResult } from "./types";

// Local dev: same-origin "/api/*" proxied to the backend via next.config.mjs
// rewrites (no CORS needed, works out of the box with `npm run dev`).
//
// Production (frontend on Vercel, backend on Render): call the backend
// DIRECTLY from the browser using NEXT_PUBLIC_API_URL, with the backend's
// CORS_ORIGINS allowing the Vercel domain. This is deliberate — proxying an
// SSE stream through a serverless rewrite to an external origin is not a
// guaranteed-reliable pattern across hosts, whereas a direct CORS'd fetch to
// the backend streams exactly as it does in local dev.
const BASE = process.env.NEXT_PUBLIC_API_URL
  ? process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")
  : "/api";

export async function createConversation(connectionId = "demo", title?: string) {
  const r = await fetch(`${BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ connection_id: connectionId, title }),
  });
  return (await r.json()) as { id: string };
}

export async function submitQuery(
  question: string,
  connectionId = "demo",
  conversationId?: string | null,
) {
  const r = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      connection_id: connectionId,
      conversation_id: conversationId ?? null,
    }),
  });
  if (!r.ok) throw new Error("submit failed");
  return (await r.json()) as { query_id: string; stream_url: string };
}

/** Stream live agent-step events over SSE via fetch (POST-then-GET pattern). */
export async function streamQuery(
  question: string,
  onEvent: (ev: AgentEvent) => void,
  connectionId = "demo",
  conversationId?: string | null,
): Promise<AnalysisResult | null> {
  const { query_id } = await submitQuery(question, connectionId, conversationId);
  const res = await fetch(`${BASE}/query/${query_id}/stream`);
  if (!res.body) throw new Error("no stream body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: AnalysisResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const dataLine = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const json = dataLine.slice(5).trim();
      if (!json || json === "{}") continue;
      try {
        const ev = JSON.parse(json) as AgentEvent;
        onEvent(ev);
        if (ev.node === "final") final = ev.result as AnalysisResult;
      } catch {
        /* ignore partial */
      }
    }
  }
  return final;
}

export async function runQuerySync(question: string, connectionId = "demo") {
  const r = await fetch(`${BASE}/query/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, connection_id: connectionId }),
  });
  return (await r.json()) as AnalysisResult;
}

export async function getSchema(connectionId = "demo") {
  const r = await fetch(`${BASE}/connections/${connectionId}/schema`);
  return await r.json();
}

export async function getHistory() {
  const r = await fetch(`${BASE}/history`);
  return (await r.json()).queries as any[];
}

export async function getAudit() {
  const r = await fetch(`${BASE}/audit`);
  return (await r.json()).audit as any[];
}

export async function getConnections() {
  const r = await fetch(`${BASE}/connections`);
  return (await r.json()).connections as any[];
}

export async function connectDatabase(name: string, targetUrl: string) {
  const r = await fetch(`${BASE}/connections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, target_url: targetUrl, read_only_confirmed: true }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || "connection failed");
  return body;
}

export async function uploadCsv(files: FileList | File[], name: string) {
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append("files", f));
  fd.append("name", name);
  const r = await fetch(`${BASE}/connections/upload`, { method: "POST", body: fd });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || "upload failed");
  }
  return await r.json();
}

export async function getEvals() {
  const r = await fetch(`${BASE}/evals`);
  return await r.json();
}

export async function getDashboards() {
  const r = await fetch(`${BASE}/dashboards`);
  if (!r.ok) throw new Error("failed to load dashboards");
  return (await r.json()).dashboards as any[];
}

export async function createDashboard(name: string) {
  const r = await fetch(`${BASE}/dashboards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return await r.json();
}

export async function generateDashboard(description: string, connectionId = "demo") {
  const r = await fetch(`${BASE}/dashboards/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, connection_id: connectionId }),
  });
  if (!r.ok) throw new Error("generation failed");
  return await r.json();
}

export async function pinToDashboard(dashboardId: string, queryId: string) {
  const r = await fetch(`${BASE}/dashboards/${dashboardId}/pin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query_id: queryId }),
  });
  return await r.json();
}

// --- Decision Intelligence suite ---
export async function sendFeedback(queryId: string, rating: "up" | "down", note?: string) {
  const r = await fetch(`${BASE}/query/${queryId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating, note }),
  });
  return await r.json();
}

export async function getSegments(connectionId = "demo") {
  const r = await fetch(`${BASE}/insights/segments?connection_id=${connectionId}`);
  return await r.json();
}

export async function getTrust() {
  const r = await fetch(`${BASE}/trust/summary`);
  return await r.json();
}

export async function getBriefing(connectionId = "demo") {
  const r = await fetch(`${BASE}/briefing?connection_id=${connectionId}`);
  return await r.json();
}

export async function getMonitors() {
  const r = await fetch(`${BASE}/monitors`);
  return (await r.json()).monitors as any[];
}

export async function createMonitor(name: string, question: string, connectionId = "demo") {
  const r = await fetch(`${BASE}/monitors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, question, connection_id: connectionId }),
  });
  return await r.json();
}

export async function runMonitor(id: string) {
  const r = await fetch(`${BASE}/monitors/${id}/run`, { method: "POST" });
  return await r.json();
}

export async function runAllMonitors() {
  const r = await fetch(`${BASE}/monitors/run-all`, { method: "POST" });
  return await r.json();
}

export async function getAlerts() {
  const r = await fetch(`${BASE}/alerts`);
  return (await r.json()).alerts as any[];
}

// --- Semantic layer (governed metrics) ---
export type Metric = {
  id: string;
  connection_id: string;
  name: string;
  expression: string;
  base_table: string;
  alias: string;
  synonyms: string[];
  description: string | null;
  certified: boolean;
};

export async function getMetrics(connectionId = "demo") {
  const r = await fetch(`${BASE}/metrics?connection_id=${connectionId}`);
  return (await r.json()).metrics as Metric[];
}

export async function createMetric(
  body: Partial<Metric> & { name: string; expression: string; base_table: string; alias: string },
  connectionId = "demo",
) {
  const r = await fetch(`${BASE}/metrics?connection_id=${connectionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = j.detail;
    const msg = d?.reasons?.join("; ") || d?.detail || d?.error || "definition rejected";
    throw new Error(msg);
  }
  return j as Metric;
}

export async function updateMetric(
  id: string,
  body: Partial<Metric>,
  connectionId = "demo",
) {
  const r = await fetch(`${BASE}/metrics/${id}?connection_id=${connectionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = j.detail;
    const msg = d?.reasons?.join("; ") || d?.detail || d?.error || "update rejected";
    throw new Error(msg);
  }
  return j as Metric;
}

export async function deleteMetric(id: string, connectionId = "demo") {
  const r = await fetch(`${BASE}/metrics/${id}?connection_id=${connectionId}`, {
    method: "DELETE",
  });
  return await r.json();
}
