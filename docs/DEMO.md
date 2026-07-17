# Nexus BI — 90-second demo script

A tight walkthrough for a Loom/GIF or a live interview. Total ~90s.

### 0 · Setup (once)
```bash
cd backend && python -m app.db.seed_demo && uvicorn app.main:app --reload   # :8000
cd frontend && npm run dev                                                   # :3000
```

### 1 · The hook (10s) — landing
Open **http://localhost:3000**. The "data landscape" hero animates in; a query
beam sweeps across. Say the line: *"Ask your data anything — Nexus writes the SQL,
runs it, forecasts what's next, and explains it."*

### 2 · The wow (35s) — a live question
Go to **/app**, click **"Show monthly merchandise revenue over time"** (or type it).
Point at, in order as they light up:
- the **AgentStepper** — Planning → Retrieving schema → Writing SQL → **Validating** → Running → Forecasting → Narrating;
- the **SQL block** with the green **✓ validated read-only** badge — *"every query is proven safe before it runs"*;
- the **line chart** with the shaded **forecast cone** and any **anomaly** markers;
- the **narrated insight** + **confidence gauge** springing to its value.

Shareable-link tip: `http://localhost:3000/app?q=Top 5 categories by merchandise revenue`
auto-runs the question — great for the recording.

### 3 · The differentiator (25s) — safety
Type **"delete all orders from the database"** → the red **"Blocked by the safety
layer"** card appears, citing the NL intent screen. Say: *"Destructive queries are
impossible by construction — read-only role, AST allow-listing, injection defense.
100% of adversarial queries are blocked in eval."*

Open **/history** → show the **append-only audit log** with the blocked verdict.

### 4 · The proof (20s) — receipts
Open **/connections** → the **"How accurate is Nexus?"** panel: 100% adversarial
blocked, 100% data integrity, forecast MAPE, RAG recall. Say: *"Measured, not
asserted — and enforced in CI: the build fails if the safety block rate drops
below 100%."*

### One-liner to close
*"LangGraph-style multi-agent pipeline, hybrid-RAG schema grounding, a five-layer
text-to-SQL safety layer, Prophet-style forecasting + IsolationForest anomalies —
fully deterministic where it counts, free-tier native, zero API keys required."*
