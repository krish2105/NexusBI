# Text-to-SQL Safety Layer — Five-Layer Defense in Depth

> **Soundbite.** Text-to-SQL's real risk isn't a wrong answer — it's a *destructive* or *exfiltrating* query. Nexus makes destructive queries impossible **by construction**: a read-only role, `sqlglot` AST allow-listing, and input-injection defense mean the worst case is a query that returns nothing, never one that harms the database.

**Measured result:** `100% (29/29)` adversarial cases blocked, control question allowed — reproducible with `make eval` (`backend/evals/sql_safety_report.json`) against the package's `sql_safety_eval_cases.csv`. Unit tests exercise every rejection rule independently (`backend/tests/test_sql_validator.py`, `test_sanitizer.py`, `test_readonly_pool.py`).

A generated query must clear **all five layers** before a single row is read. Each layer is independent, so a bypass of one is caught by the next.

**Where the code lives.** Layers 2–4 are pure, database-independent rules, so they live in **[`sqlguard`](https://github.com/krish2105/sqlguard)** — our MIT-licensed OSS package, pinned in `backend/requirements.txt`. Nexus *dogfoods* it: the guard defending this app is the same artifact anyone `pip install`s, so there is exactly one implementation and no chance of drift (a test asserts the rules resolve to the installed package). Layers 1 and 5 need a live connection, so they stay in the app. `app/sqlsafety/` is a thin adapter that applies Nexus's row cap, execution dialect, and the L2/L3 labels used below.

---

## Layer 1 — Read-only by construction  ·  `app/db/target_pool.py`

The ultimate backstop: even if every other layer failed, the engine itself refuses writes.

- **SQLite demo** — opened with a `mode=ro&immutable=1` URI **and** `PRAGMA query_only = ON`.
- **Postgres production** — the session is forced to `default_transaction_read_only = on` inside a read-only transaction, using the least-privilege `nexus_readonly` role (`data/olist/read_only_role.sql`: `SELECT`-only grants, `statement_timeout = 8s`).

Verified test: `DELETE FROM orders` raises `ReadOnlyExecutionError` at the engine.

## Layer 2 — AST validation  ·  `sqlguard.validator`

Deterministic, no LLM. The SQL is parsed with **`sqlglot`** and **rejected unless proven safe**:

- exactly **one** statement (blocks `;`-chaining and comment-smuggling like `SELECT 1 /*..*/; DELETE ...`);
- the top node is a `SELECT` / `WITH … SELECT` / set-operation of SELECTs;
- **no forbidden node anywhere in the tree** — `Insert, Update, Delete, Merge, Drop, Alter, Create, TruncateTable, Grant, Copy, Command, Into`. This catches write-producing CTEs (`WITH x AS (DELETE … RETURNING *) …`) and `SELECT … INTO`;
- **no dangerous functions** — `pg_sleep`, `pg_read_file`, `dblink`, `lo_import`, … (deny-list + `pg_`/`dblink`/`lo_` prefixes);
- **no system catalogs** — `pg_catalog`, `information_schema`, `pg_shadow`, `pg_authid`, any `pg_*` table.

Case obfuscation (`dRoP tAbLe`) is normalized away by the parser before checks run.

## Layer 3 — Allow-list + limits  ·  `sqlguard.policy`

The allow-list is built from the **live introspected schema** on connect (`app/db/introspect.py`), so it always matches reality.

- Every referenced **table** must be on the allow-list → rejects hallucinated tables (`employee_payroll`).
- Every **column** must exist on its table → rejects hallucinated columns (`orders.customer_password`), with alias/output-alias/CTE resolution so valid analytics (`ORDER BY order_count`) aren't false-flagged.
- A **`LIMIT`** is injected if absent and clamped to the row cap (10,000) if too large.
- Execution enforces a **statement timeout** and **result-size cap**.

## Layer 4 — NL-input injection defense  ·  `sqlguard.sanitizer`

The *question itself* is untrusted and is screened **before** it reaches the generator. Deterministic, explainable intent rules cover: prompt-injection ("ignore your instructions", "developer mode", "reveal the system prompt"), destructive intent, system-catalog probing, dangerous functions, credential/exfiltration requests, tenant-escape, and resource-abuse / unbounded scans. The screen is **allow-list-aware**, so it flags probes for tables/columns that don't exist without blocking legitimate questions. The generator prompt also structurally delimits schema/instructions from the user question so injected text can't override the system contract.

## Layer 5 — Dry-run + capped repair loop  ·  `app/agents/graph.py`

Before committing, the validated SQL is `EXPLAIN`-ed to catch planning errors cheaply. If validation **or** explain fails, structured errors are returned to `sql_generator` for a **capped repair (≤ 2 attempts)**. After the cap, Nexus fails gracefully — **it never executes unvalidated SQL.**

---

## Audit  ·  `app/db/app_store.py` (`audit_log`, append-only)

Every generated SQL, its verdict, and every executed query (actor, row count, latency, verdict) are written to an append-only `audit_log`. The store exposes only append + read for it — no update/delete path exists (tested in `test_audit.py`). This is both a security control and a demo feature (see the History page).

## Why this design

The LLM only **plans and narrates**. It never computes numbers and its SQL is treated as untrusted until it clears Layers 2–3 and the Layer-5 dry-run. Determinism where it matters (validation, limits, ML) + bounded autonomy (read-only, logged, explained) is the production-grade posture the 2026 market calls "dynamic execution with deterministic guardrails."
