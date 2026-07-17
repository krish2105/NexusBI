"""SQL generator node — NL + retrieved schema -> a single safe SELECT.

Two paths, one contract:
  * LLM path (Groq/Ollama) — general; prompt is grounded ONLY in the retrieved
    schema/glossary and hard-constrained to a single read-only SELECT.
  * Deterministic path (zero key) — a grounded synthesizer that assembles SQL
    from the planner's intent using the real join graph + glossary canonical SQL.
    It never invents identifiers, so its output always passes the safety layer.

Either way the output is handed to the safety gate before it can execute.
"""
from __future__ import annotations

import re

from app.agents.planner import plan_question
from app.config import settings
from app.llm.client import get_llm
from app.rag.retriever import RetrievedSchema

# Undirected join graph derived from schema_relationships.csv.
_EDGES: dict[frozenset[str], str] = {
    frozenset({"order_items", "orders"}): "order_items.order_id = orders.order_id",
    frozenset({"order_items", "products"}): "order_items.product_id = products.product_id",
    frozenset({"order_items", "sellers"}): "order_items.seller_id = sellers.seller_id",
    frozenset({"products", "categories"}): "products.category_id = categories.category_id",
    frozenset({"orders", "regions"}): "orders.region_id = regions.region_id",
    frozenset({"orders", "customers"}): "orders.customer_id = customers.customer_id",
    frozenset({"payments", "orders"}): "payments.order_id = orders.order_id",
    frozenset({"reviews", "orders"}): "reviews.order_id = orders.order_id",
}
_ADJ: dict[str, set[str]] = {}
for _pair in _EDGES:
    a, b = tuple(_pair)
    _ADJ.setdefault(a, set()).add(b)
    _ADJ.setdefault(b, set()).add(a)

# metric output alias -> monthly_kpis native column (time-series fast path)
_KPI_COL = {
    "merchandise_revenue": "merchandise_value",
    "gross_order_value": "gross_order_value",
    "order_count": "order_count",
    "units_sold": "units_sold",
    "freight_value": "freight_value",
    "unique_customer_count": "unique_customer_count",
    "payment_value": "payment_value",
    "average_order_value": "average_gross_order_value",
    "average_review_score": "average_review_score",
}


def _bfs_path(root: str, target: str) -> list[str]:
    if root == target:
        return [root]
    seen = {root}
    queue = [[root]]
    while queue:
        path = queue.pop(0)
        for nxt in _ADJ.get(path[-1], ()):
            if nxt in seen:
                continue
            new = path + [nxt]
            if nxt == target:
                return new
            seen.add(nxt)
            queue.append(new)
    return []


def _plan_joins(required: set[str], root: str) -> tuple[str, list[str], list[str]]:
    """Return (root_table, [JOIN clauses], [unresolved tables])."""
    included = {root}
    edges_needed: set[frozenset[str]] = set()
    unresolved: list[str] = []
    for t in required:
        if t == root:
            continue
        path = _bfs_path(root, t)
        if not path:
            unresolved.append(t)
            continue
        for i in range(len(path) - 1):
            edges_needed.add(frozenset({path[i], path[i + 1]}))
            included.add(path[i + 1])

    # Emit JOINs so each table appears only after a neighbour already in FROM.
    joins: list[str] = []
    placed = {root}
    pending = set(edges_needed)
    progress = True
    while pending and progress:
        progress = False
        for edge in list(pending):
            a, b = tuple(edge)
            newcomer = None
            if a in placed and b not in placed:
                newcomer = b
            elif b in placed and a not in placed:
                newcomer = a
            if newcomer:
                joins.append(f"JOIN {newcomer} ON {_EDGES[edge]}")
                placed.add(newcomer)
                pending.discard(edge)
                progress = True
    return root, joins, unresolved


def _default_limit(top_n: int | None) -> int:
    return top_n or 10_000


def synthesize_sql(question: str, plan: dict) -> tuple[str, str, list[str]]:
    """Deterministic grounded synthesis. Returns (sql, explanation, assumptions)."""
    metric = plan["metric"]
    dimension = plan["dimension"]
    shape = plan["shape"]
    filters = plan["filters"]
    top_n = plan["top_n"]
    assumptions = list(plan.get("assumptions", []))
    alias = metric["alias"]

    # --- time series (monthly) ---
    if shape == "timeseries":
        col = _KPI_COL.get(alias)
        if col:
            assumptions.append("Monthly grain resolved from the pre-aggregated "
                               "monthly_kpis view (2016-09 .. 2018-10).")
            sql = (f"SELECT year_month, {col} AS {alias}\n"
                   f"FROM monthly_kpis\nORDER BY year_month\nLIMIT 10000")
            return sql, f"Monthly {alias} time series from monthly_kpis.", assumptions
        # generic monthly grouping via dates
        shape = "groupby"
        dimension = {"table": "dates", "col": "dates.year_month", "label": "year_month"}

    # --- group-by dimension ---
    if shape == "groupby":
        if dimension is None:
            dimension = {"table": "categories", "col": "categories.category_name_en",
                         "label": "category_name_en"}
        required = {metric["base"], dimension["table"]}
        if filters:
            required.add("orders")
        root = "order_items" if "order_items" in required else metric["base"]
        root, joins, unresolved = _plan_joins(required, root)
        where = f"\nWHERE {' AND '.join(f['sql'] for f in filters)}" if filters else ""
        join_block = ("\n" + "\n".join(joins)) if joins else ""
        limit = _default_limit(top_n)
        sql = (f"SELECT {dimension['col']} AS {dimension['label']}, "
               f"{metric['expr']} AS {alias}\n"
               f"FROM {root}{join_block}{where}\n"
               f"GROUP BY {dimension['col']}\n"
               f"ORDER BY {alias} DESC\nLIMIT {limit}")
        expl = (f"{alias} grouped by {dimension['label']}"
                + (f", top {top_n}" if top_n else "")
                + (", " + " & ".join(f['label'] for f in filters) if filters else "")
                + ".")
        return sql, expl, assumptions

    # --- scalar ---
    required = {metric["base"]}
    if filters:
        required.add("orders")
    root = "order_items" if "order_items" in required else metric["base"]
    root, joins, _ = _plan_joins(required, root)
    where = f"\nWHERE {' AND '.join(f['sql'] for f in filters)}" if filters else ""
    join_block = ("\n" + "\n".join(joins)) if joins else ""
    sql = (f"SELECT {metric['expr']} AS {alias}\n"
           f"FROM {root}{join_block}{where}\nLIMIT 10000")
    expl = f"Total {alias}" + (" (" + ", ".join(f['label'] for f in filters) + ")"
                               if filters else "") + "."
    return sql, expl, assumptions


# --- LLM path ---------------------------------------------------------------
_SYSTEM = """You are a careful analytics SQL generator for a READ-ONLY Postgres warehouse.
Rules you must never break:
- Produce exactly ONE statement, a single SELECT (or WITH ... SELECT). Never DDL/DML.
- Use ONLY tables and columns present in the provided schema. Never invent names.
- List explicit columns (no SELECT * for wide tables) and always include a LIMIT.
- Prefer the business-glossary canonical SQL for metrics.
Return ONLY the SQL, no prose, no markdown fences."""


def _extract_sql(text: str) -> str:
    text = re.sub(r"```(?:sql)?", "", text, flags=re.I).strip("` \n")
    # take up to first semicolon / end
    return text.split(";")[0].strip()


def generate_sql(question: str, schema: RetrievedSchema,
                 plan: dict | None = None) -> dict:
    plan = plan or plan_question(question)
    llm = get_llm()

    if llm.is_llm:  # pragma: no cover - requires a provider
        user = (f"{schema.prompt_block()}\n\n# QUESTION\n{question}\n\n"
                f"# INTENT (advisory)\n{plan.get('intent_summary','')}\n\nSQL:")
        try:
            resp = llm.complete(_SYSTEM, user, temperature=0.0)
            sql = _extract_sql(resp.text)
            if sql.lower().startswith(("select", "with")):
                return {"sql": sql, "explanation": "LLM-generated, grounded in "
                        "retrieved schema.", "assumptions": plan.get("assumptions", []),
                        "generator": llm.provider, "plan": plan}
        except Exception:  # noqa: BLE001 - fall back deterministically
            pass

    sql, expl, assumptions = synthesize_sql(question, plan)
    return {"sql": sql, "explanation": expl, "assumptions": assumptions,
            "generator": "deterministic", "plan": plan}


def repair_sql(question: str, schema: RetrievedSchema, plan: dict,
               errors: list[str]) -> dict:
    """Repair attempt after a validation failure (Layer 5)."""
    llm = get_llm()
    if llm.is_llm:  # pragma: no cover
        user = (f"{schema.prompt_block()}\n\n# QUESTION\n{question}\n\n"
                f"# YOUR PREVIOUS SQL WAS REJECTED\n{'; '.join(errors)}\n\n"
                f"Fix it. Return ONLY corrected SQL:")
        try:
            resp = llm.complete(_SYSTEM, user, temperature=0.0)
            sql = _extract_sql(resp.text)
            if sql.lower().startswith(("select", "with")):
                return {"sql": sql, "explanation": "Repaired after validation feedback.",
                        "assumptions": plan.get("assumptions", []),
                        "generator": llm.provider, "plan": plan}
        except Exception:  # noqa: BLE001
            pass
    # Deterministic path is already grounded; re-synthesize as a safe fallback.
    sql, expl, assumptions = synthesize_sql(question, plan)
    return {"sql": sql, "explanation": expl + " (resynthesized)",
            "assumptions": assumptions, "generator": "deterministic", "plan": plan}
