# Nexus BI — Architecture

## The two-database separation (critical)

Nexus keeps two databases completely apart:

| DB | Holds | Access | Code |
|---|---|---|---|
| **App DB** | connections, query history, dashboards, glossary, **append-only audit** | read/write | `app/db/app_store.py` (SQLite locally; Supabase Postgres in prod) |
| **Target DB** | the data being *analyzed* (the Olist warehouse) | **read-only pool** | `app/db/target_pool.py` |

They never mix. The app writes metadata; the target is only ever read, through the read-only pool.

## The agent graph (`app/agents/graph.py`)

A bounded-autonomy decision pipeline with a safety gate and a capped repair loop. Every node transition is streamed to the UI over SSE.

```
START
  └─ guard            (Layer 4: NL injection/intent screen — pre-LLM)
  └─ planner          decompose question -> metric / dimension / grain / filters / top-N; record assumptions; block write-intent
  └─ schema_retriever RAG over the semantic catalog -> only the relevant tables/columns + glossary
  └─ sql_generator    deterministic synthesizer (zero-key) OR LLM (Groq/Ollama), grounded in retrieved schema
  └─ sql_validator    SAFETY GATE (Layers 2+3) + Layer-5 EXPLAIN
        ├─ invalid & repairs<2  -> back to sql_generator (repair loop)
        ├─ repair cap hit       -> END (graceful error, nothing executed)
        └─ valid                -> executor
  └─ executor         run validated SQL through the READ-ONLY pool (timeout + row cap)
  └─ analyst          chart_selector picks line/bar/scatter/KPI from the result shape
  └─ forecaster       (if time series) Holt-Winters / OLS point + 95% bands  [ML]
  └─ anomaly          IsolationForest / STL residual outliers                [ML]
  └─ narrator         business-framed insight grounded ONLY in the real numbers; sets confidence
  └─ final
```

Implemented as an explicit streaming state machine (`AnalysisState`, `app/agents/state.py`) so it runs with or without `langgraph` installed; a thin LangGraph adapter can wrap `run_analysis` for checkpointing/resumability.

## Determinism boundary (why the numbers are trustworthy)

The LLM **only plans and narrates**. Everything quantitative is deterministic code:
- SQL **validation, allow-listing, LIMIT** — `app/sqlsafety/`
- **aggregates** — computed by the database, not the model
- **forecast / anomaly / chart choice** — `app/ml/` (statsmodels, scikit-learn, heuristics)

So every figure is real and reproducible; the model never invents a number.

## RAG semantic layer (`app/rag/`)

`catalog.py` builds a semantic catalog from the real `data_dictionary.csv` (types + definitions), `business_glossary.csv` (metric → canonical SQL), and the live introspected schema (authoritative columns + sample values). `retriever.py` does hybrid lexical retrieval fused with glossary-`required_tables` grounding (optional local `bge-small` embeddings via RRF), returning only what the generator needs — small prompts, no hallucinated schema. Mirrors the pgvector production design at zero dependency cost.

## Free-tier stack

| Concern | Choice | Cost |
|---|---|---|
| LLM | Groq free / Ollama / **deterministic** | Free / none |
| Embeddings, reranker | `sentence-transformers` bge (local, optional) | Free |
| App DB | SQLite local / Supabase Postgres + pgvector | Free |
| Target DB | SQLite demo / Postgres (Neon/Supabase) read-only | Free |
| Forecast / anomaly | statsmodels / scikit-learn (local) | Free |
| Backend host | Render free (Docker) | Free |
| Frontend host | Vercel free | Free |

## Frontend (`frontend/`)

Next.js 14 App Router · TypeScript · Tailwind · **Motion** · **Lenis** · **Recharts** · lucide. "Calm Intelligence" dark design system. The `/app` workspace streams the agent pipeline over SSE (`AgentStepper`), shows the generated SQL with a `✓ validated read-only` badge (`SqlBlock`), draws the chart with forecast bands + anomaly markers (`AutoChart`), and reveals a narrated `InsightCard` with a `ConfidenceGauge`. Dev proxies `/api/*` to the backend (`next.config.mjs`).
