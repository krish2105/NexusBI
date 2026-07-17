<div align="center">

# Nexus BI — Autonomous Business Analyst Copilot

**Ask your data anything. Nexus writes the SQL, runs the numbers, forecasts what's next, and tells you what it means — in seconds.**

Agentic Decision Intelligence · five-layer text-to-SQL safety · hybrid-RAG schema grounding · Prophet-style forecasting + IsolationForest anomalies · free-tier native, **zero API keys required**.

</div>

---

## What it does

Connect a database, ask a question in plain English, and a multi-agent pipeline plans the analysis, generates **provably safe** read-only SQL, validates and executes it, forecasts the trend, flags anomalies, auto-selects the chart, and returns a narrated, confidence-scored insight — with the SQL fully visible.

Built and evaluated on the **real Olist Brazilian e-commerce dataset** — 99,441 orders, 112,650 items, 96,096 shoppers (2016–2018).

## Measured results (`make eval`)

| Suite | Result |
|---|---|
| **SQL safety** | **100%** (29/29) adversarial queries blocked, control allowed |
| **Text-to-SQL** | 100% data-integrity; ~49% zero-key generator execution accuracy (higher with a Groq key) |
| **Forecast** | Holt-Winters backtest, MAPE on a 3-month holdout |
| **RAG** | ~85% table recall on the labeled question set |
| **Tests** | `56 passed` — safety rules, read-only enforcement, graph, API |

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

### Upgrades (all optional, all free)
- **General LLM:** set `GROQ_API_KEY` (free at console.groq.com) — the SQL generator and narrator switch to `llama-3.3-70b`. Or run **Ollama** locally.
- **Production Postgres:** `docker compose up -d`, load the data package's `load_postgres.sql` + `read_only_role.sql` into `demo-db`, and set `DEMO_TARGET_URL` to the read-only DSN.
- **Local embeddings:** `pip install sentence-transformers` and set `USE_EMBEDDINGS=true`.

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
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — agent graph + two-DB separation
- **[`docs/VIVA.md`](docs/VIVA.md)** — interview Q&A

## Deploy
- **Backend → Render** (Docker): `render.yaml` included. Note free-tier cold starts.
- **Frontend → Vercel** (zero-config): set `NEXT_PUBLIC_API_URL` to the Render URL.

## Stack
FastAPI · sqlglot · LangGraph-style graph · statsmodels · scikit-learn · Groq/Ollama (optional) · Next.js 14 · Motion · Lenis · Recharts · Tailwind.

## Data & license
Derived from the **Brazilian E-Commerce Public Dataset by Olist** (Kaggle), CC BY-NC-SA 4.0. This is a non-commercial portfolio project. See `backend/data/olist/LICENSE_DATA.md`.
