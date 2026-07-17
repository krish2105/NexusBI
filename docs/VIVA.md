# Nexus BI — Viva / Interview Q&A

**1. How do you stop a text-to-SQL system from running destructive queries?**
Defense-in-depth, five independent layers (`docs/SQL_SAFETY.md`): a read-only DB role (worst case is a no-op), `sqlglot` AST validation allowing only single-statement SELECTs, table/column allow-listing built from live introspection (also catches hallucinated columns), an NL-input injection screen, and a capped repair loop that never executes unvalidated SQL. Measured: **100% of adversarial queries blocked** in eval.

**2. Why not let the LLM compute the numbers?**
LLMs hallucinate figures. Nexus makes the LLM *plan and narrate only*; the database computes aggregates and scikit-learn/statsmodels compute forecasts and anomalies — so every number is real and reproducible. That determinism boundary is the whole point.

**3. Why RAG over the schema instead of dumping it in the prompt?**
Real warehouses have hundreds of columns; dumping them is slow, costly, and hurts accuracy. Hybrid-retrieving only the relevant tables/columns + glossary (grounded by the glossary's `required_tables`) keeps prompts small and cuts hallucinated schema. RAG table recall is measured in `rag_report.json`.

**4. Why a graph over a simple chain?**
Explicit typed state, a conditional **repair loop** when SQL fails validation, clean routing into the ML nodes, and streamable node transitions for the live UI. It's modelled as LangGraph's `StateGraph`; the bundled runtime also works without the dependency.

**5. What is "bounded autonomy" here?**
It executes read queries autonomously but *cannot mutate data by construction*, surfaces its SQL + assumptions + confidence for every answer, and logs everything to an append-only audit. Dynamic execution with deterministic guardrails.

**6. How do you know it's accurate? (measured, not asserted — `make eval`)**
- **Safety:** 29/29 adversarial blocked, control allowed.
- **Text-to-SQL:** 100% data-integrity (validated SQL vs labeled row counts); the zero-key deterministic generator reaches ~49% execution accuracy on a mixed easy/medium/hard set — a free Groq/Ollama key raises coverage over the hard CTE/window-function questions.
- **Forecast:** backtest MAPE/RMSE on a 3-month holdout of the monthly revenue series.
- **RAG:** table recall / full-grounding rate on the labeled question set.

**7. Real-world data handling?**
The Olist package preserves genuine anomalies (partial boundary months, order/payment mismatches, missing timestamps). The forecaster **trims partial boundary periods** before modeling (a real analyst move) and the narrator reads the clean series — so a tail of incomplete months doesn't produce a misleading "declined 100%".

**8. How would you scale it (v2)?**
MySQL/BigQuery dialects via `sqlglot`, multi-tenant row-level security (the policy layer already has the hook), a feedback loop that learns from corrected queries, caching of frequent questions, and role-based data access.
