<div align="center">

# Nexus BI — Autonomous Business Analyst Copilot

**Ask your data anything. Nexus writes the SQL, runs the numbers, forecasts what's next, and tells you what it means — in seconds.**

Agentic Decision Intelligence · five-layer text-to-SQL safety · hybrid-RAG schema grounding · Prophet-style forecasting + IsolationForest anomalies · free-tier native, **zero API keys required**.

[![CI](https://github.com/krish2105/NexusBI/actions/workflows/ci.yml/badge.svg)](https://github.com/krish2105/NexusBI/actions/workflows/ci.yml)
![safety](https://img.shields.io/badge/adversarial%20queries%20blocked-100%25-34D399)
![tests](https://img.shields.io/badge/backend%20tests-96%20passing-6366F1)
![free tier](https://img.shields.io/badge/API%20keys-0%20required-22D3EE)
![license](https://img.shields.io/badge/data-CC%20BY--NC--SA%204.0-9BA3B4)

![Nexus BI](docs/img/landing.png)

</div>

---

## What it does

Connect a database, ask a question in plain English, and a multi-agent pipeline plans the analysis, generates **provably safe** read-only SQL, validates and executes it, forecasts the trend, flags anomalies, auto-selects the chart, and returns a narrated, confidence-scored insight — with the SQL fully visible.

Built and evaluated on the **real Olist Brazilian e-commerce dataset** — 99,441 orders, 112,650 items, 96,096 shoppers (2016–2018).

**Bring your own data:** upload a CSV in the workspace and Nexus builds an instant read-only warehouse you can question with the same five-layer safety guard — and a **schema-agnostic zero-key synthesizer** grounds SQL against *any* table (no LLM key needed).

**Conversational multi-turn analysis:** the workspace is a thread, not one-shot Q&A. Ask a question, then follow up in plain English — *"now just the North region"*, *"break it down by state"*, *"top 3"*, *"why did it change?"*. Nexus carries the prior analysis forward and applies the delta (scope / pivot / metric / time), and **"why?" runs a real contribution/root-cause decomposition** attributing a period-over-period change to specific members ("watches_gifts drove 45% of the dip"). Deterministic and grounded — the follow-up resolver reuses the exact same safety-checked pipeline.

**Proactive Daily Briefing** (`/briefing`) — insight *without being asked*. Nexus analyzes the business on its own: for each key metric it computes the latest complete period, the MoM change, a forecast, and an anomaly flag; ranks what moved most; **root-causes the biggest revenue swing**; and narrates an executive briefing ("Late-delivery rate up 132% in August; revenue down 5%, driven by watches_gifts −23,936"). It's the autonomous-analyst payoff — forecasting + anomaly + monitors + root-cause in one proactive report. Deterministic; a cron can deliver it daily.

**Decision Intelligence suite:**
- **Customer Segments** (`/segments`) — real RFM segmentation (quintile scoring on recency/frequency/monetary → Champions, Loyal, At Risk, Hibernating…). Deterministic ML.
- **Monitors & Alerts** (`/monitors`) — save a question to watch; a robust median+MAD check raises an alert when the latest period deviates from its baseline. Schedule via cron hitting `POST /monitors/run-all`.
- **Trust Center** (`/trust`) — safety red-team results, live governance counts (executed vs blocked, audit size), accuracy metrics, and feedback satisfaction — trust as a product surface.
- **Feedback loop** — 👍/👎 on every answer; approved (question→SQL) pairs become verified few-shot examples that improve future generation.

## Measured results (`make eval`)

| Suite | Result |
|---|---|
| **SQL safety** | **100%** (29/29) adversarial queries blocked, control allowed |
| **Text-to-SQL** | 100% data-integrity; ~49% zero-key generator execution accuracy (higher with a Groq key) |
| **Forecast** | Holt-Winters backtest, MAPE on a 3-month holdout |
| **RAG** | ~85% table recall on the labeled question set |
| **Tests** | `96 passed` — safety rules, read-only enforcement, graph, API, hardening |
| **CI** | GitHub Actions runs tests **and fails the build if the safety block rate drops below 100%** |

## Quickstart — runs in ~1 minute, no keys, no Postgres

```bash
# 1) Backend  (SQLite demo seeded from the real Olist CSVs; deterministic engine)
cd backend
pip install -r requirements.txt
python -m app.db.seed_demo            # load the real data into SQLite (~4s)
uvicorn app.main:app --reload         # http://localhost:8000  (/docs, /health)

# 2) Frontend
cd ../frontend
cp .env.example .env
npm install
npm run dev                           # http://localhost:3000

# 3) (optional) tests + eval reports
cd ../backend && python -m pytest && python -m evals.run_evals
```

Open **http://localhost:3000/app**, click an example chip, and watch the agent build the answer. Try *"delete all orders"* to see the safety layer block it.

**Shareable insight links** (auto-run the question — great for a demo/recording):
- `…/app?q=Show monthly merchandise revenue over time` → live chart + forecast
- `…/app?q=Top 5 categories by merchandise revenue` → grounded join + insight
- `…/app?q=delete all orders` → the safety layer blocks it

See **[`docs/DEMO.md`](docs/DEMO.md)** for a 90-second walkthrough script.

### Upgrades (all optional, all free)
- **General LLM:** set `GROQ_API_KEY` (free at console.groq.com) — the SQL generator and narrator switch to `llama-3.3-70b`. Or run **Ollama** locally. Re-run `python -m evals.run_evals` with the key set to see the accuracy lift over the zero-key baseline, broken down by question difficulty.
- **Observability:** set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` (free at cloud.langfuse.com) — every query gets a full trace with a child span per agent node (latency, generator used, safety verdict). No-op with zero overhead when unset.
- **Production Postgres:** `docker compose up -d`, load the data package's `load_postgres.sql` + `read_only_role.sql` into `demo-db`, and set `DEMO_TARGET_URL` to the read-only DSN.
- **Local embeddings:** `pip install sentence-transformers` and set `USE_EMBEDDINGS=true`.

### Deploy live
See **[`docs/DEPLOY.md`](docs/DEPLOY.md)** for the full runbook: Groq + Langfuse setup, Render backend deploy (from the included `render.yaml` blueprint, Docker-verified locally), and Vercel frontend deploy — ~20 minutes end to end.

## Architecture (short version)

```
Next.js (Vercel)  ──REST + SSE──►  FastAPI (Render)
                                     └─ agent graph: planner → schema_retriever(RAG)
                                        → sql_generator → sql_validator (SAFETY GATE)
                                        → executor (READ-ONLY pool) → analyst
                                        → forecaster/anomaly (ML) → narrator
   app metadata ─► App DB (SQLite / Supabase)      user data ─► READ-ONLY target DB
```

Two databases, kept strictly separate. The LLM only plans and narrates — the database computes aggregates and scikit-learn/statsmodels compute forecasts, so every number is real. Full writeups:

- **[`docs/SQL_SAFETY.md`](docs/SQL_SAFETY.md)** — the five-layer defense (the centerpiece)
- **[`docs/SECURITY.md`](docs/SECURITY.md)** — threat model + platform hardening (SSRF, DSN encryption, tenant isolation, rate limits)
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — agent graph + two-DB separation
- **[`docs/DEMO.md`](docs/DEMO.md)** — 90-second walkthrough script
- **[`docs/DEPLOY.md`](docs/DEPLOY.md)** — go-live runbook (Groq, Langfuse, Render, Vercel)
- **[`docs/VIVA.md`](docs/VIVA.md)** — interview Q&A

## Deploy
- **Backend → Render** (Docker): `render.yaml` included and Docker-build-verified locally (image builds, seeds the real data, and serves `/health` + a real query correctly). Note free-tier cold starts.
- **Frontend → Vercel** (zero-config): set `NEXT_PUBLIC_API_URL` to the Render URL; the frontend calls the backend directly with CORS (not proxied) so SSE streams reliably in production — verified end-to-end in-browser against a live cross-origin backend.
- Full steps: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Stack
FastAPI · sqlglot · LangGraph-style graph · statsmodels · scikit-learn · Groq/Ollama (optional) · Next.js 14 · Motion · Lenis · Recharts · Tailwind.

## Data & license
Derived from the **Brazilian E-Commerce Public Dataset by Olist** (Kaggle), CC BY-NC-SA 4.0. This is a non-commercial portfolio project. See `backend/data/olist/LICENSE_DATA.md`.
