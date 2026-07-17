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


# --- generic (schema-agnostic) synthesizer for uploaded / arbitrary data -----
import re as _re

_NUMERIC_TYPES = ("INT", "REAL", "NUMERIC", "FLOAT", "DOUBLE", "DECIMAL", "BIGINT")
_DATEISH = _re.compile(r"(date|time|_at$|timestamp|year_month|period|month|year)", _re.I)
_ID_LIKE = _re.compile(r"(^id$|_id$|code|zip|postal|phone|lat|lng|longitude|latitude"
                       r"|number|_no$|uuid|guid)", _re.I)
_VALUEISH = _re.compile(r"(value|amount|total|revenue|sales|price|cost|qty|quantity"
                        r"|sum|spend|profit|margin)", _re.I)
_RATEISH = _re.compile(r"(rate|ratio|avg|average|mean|score|percent|pct)", _re.I)
_TOKEN = _re.compile(r"[a-z0-9]+")


def _toks(s: str) -> set[str]:
    return set(_TOKEN.findall(s.lower()))


def _sing(t: str) -> str:
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


def _col_matches(colname: str, q_tokens: set[str]) -> bool:
    """Fuzzy singular/plural-aware match of a column against question tokens."""
    q_stems = {_sing(t) for t in q_tokens}
    for ct in _toks(colname):
        if len(ct) < 3:
            continue
        if ct in q_tokens or _sing(ct) in q_stems:
            return True
    return False


def is_olist_schema(schema: RetrievedSchema) -> bool:
    names = {t.lower() for t in schema.table_names()}
    return "order_items" in names or "orders" in names


def _classify_cols(table):
    dates, numerics, texts = [], [], []
    for c in table.columns:
        t = (c.data_type or "TEXT").upper()
        is_num = any(t.startswith(p) or p in t for p in _NUMERIC_TYPES)
        if _DATEISH.search(c.name):
            dates.append(c.name)
        elif is_num and not _ID_LIKE.search(c.name):
            numerics.append(c.name)
        elif not is_num:
            texts.append(c.name)
    return dates, numerics, texts


def synthesize_generic(question: str, plan: dict, schema: RetrievedSchema
                       ) -> tuple[str, str, list[str]]:
    """Build a grounded single-table query for an arbitrary schema."""
    q_tokens = _toks(question)
    assumptions: list[str] = []

    # 1) Base table: best column/name overlap with the question.
    def tscore(t):
        s = len(_toks(t.name) & q_tokens) * 2
        s += sum(1 for c in t.columns if _toks(c.name) & q_tokens)
        return s
    table = max(schema.tables, key=tscore)
    if tscore(table) == 0:
        assumptions.append(f"Question didn't name a table; used '{table.name}'.")
    dates, numerics, texts = _classify_cols(table)

    # 2) Metric. Aggregation intent comes from the QUESTION first, then the column.
    mentioned_num = next((c for c in numerics if _col_matches(c, q_tokens)), None)
    wants_count = bool(_re.search(r"\b(how many|count|number of|rows?)\b", question, _re.I))
    q_wants_avg = bool(_re.search(r"\b(average|avg|mean)\b", question, _re.I))
    q_wants_sum = bool(_re.search(r"\b(total|sum)\b", question, _re.I))

    if wants_count and not mentioned_num:
        col = None
    elif mentioned_num:
        col = mentioned_num
    elif numerics:
        col = next((c for c in numerics if _VALUEISH.search(c)), numerics[0])
    else:
        col = None

    if col is None:
        metric_expr, alias = "COUNT(*)", "row_count"
    else:
        if q_wants_avg:
            agg = "AVG"
        elif q_wants_sum:
            agg = "SUM"
        elif _RATEISH.search(col):
            agg = "AVG"
        else:
            agg = "SUM"
        metric_expr = (f'ROUND(AVG("{col}"), 2)' if agg == "AVG" else f'{agg}("{col}")')
        alias = f"{agg.lower()}_{col}".lower()

    # 3) Dimension.
    mentioned_text = next((c for c in texts if _col_matches(c, q_tokens)), None)
    is_time = plan.get("is_time_series") and dates
    top_n = plan.get("top_n")
    if is_time:
        dim, dim_label, order = f'"{dates[0]}"', dates[0], "ASC"
    elif mentioned_text:
        dim, dim_label, order = f'"{mentioned_text}"', mentioned_text, "DESC"
    elif (top_n or _re.search(r"\bby\b|\bper\b|\beach\b|top\b", question, _re.I)) and texts:
        dim, dim_label, order = f'"{texts[0]}"', texts[0], "DESC"
        assumptions.append(f"Grouped by '{texts[0]}' (first categorical column).")
    else:
        dim = None

    tbl = f'"{table.name}"'
    if dim is None:
        sql = f"SELECT {metric_expr} AS {alias}\nFROM {tbl}\nLIMIT 10000"
        return sql, f"{alias} across {table.name}.", assumptions

    limit = top_n or 50
    order_by = alias if order == "DESC" else dim
    sql = (f"SELECT {dim} AS {dim_label}, {metric_expr} AS {alias}\n"
           f"FROM {tbl}\nGROUP BY {dim}\n"
           f"ORDER BY {order_by} {order}\nLIMIT {limit}")
    return sql, f"{alias} by {dim_label} from {table.name}.", assumptions


def synthesize_sql(question: str, plan: dict,
                   schema: RetrievedSchema | None = None) -> tuple[str, str, list[str]]:
    """Deterministic grounded synthesis. Returns (sql, explanation, assumptions).

    Uses the Olist-tuned metric/dimension library when the connection is the
    Olist star schema; otherwise falls back to the schema-agnostic synthesizer so
    zero-key generation still works on arbitrary uploaded data.
    """
    if schema is not None and not is_olist_schema(schema):
        return synthesize_generic(question, plan, schema)

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


def _vetted_examples_block(limit: int = 3) -> str:
    """Few-shot (question -> SQL) pairs verified via 👍 feedback. Closes the loop:
    answers users approved make future generation better."""
    try:
        from app.db.app_store import get_store

        ex = get_store().vetted_examples(limit)
    except Exception:  # noqa: BLE001 - never break generation on this
        ex = []
    if not ex:
        return ""
    lines = ["\n# VERIFIED EXAMPLES (approved by users — follow their style)"]
    for e in ex:
        if e.get("sql"):
            lines.append(f"Q: {e['question']}\nSQL: {e['sql']}")
    return "\n".join(lines)


def _extract_sql(text: str) -> str:
    text = re.sub(r"```(?:sql)?", "", text, flags=re.I).strip("` \n")
    # take up to first semicolon / end
    return text.split(";")[0].strip()


def generate_sql(question: str, schema: RetrievedSchema,
                 plan: dict | None = None) -> dict:
    plan = plan or plan_question(question)
    llm = get_llm()

    if llm.is_llm:  # pragma: no cover - requires a provider
        few_shot = _vetted_examples_block()
        user = (f"{schema.prompt_block()}\n{few_shot}\n\n# QUESTION\n{question}\n\n"
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

    sql, expl, assumptions = synthesize_sql(question, plan, schema)
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
    sql, expl, assumptions = synthesize_sql(question, plan, schema)
    return {"sql": sql, "explanation": expl + " (resynthesized)",
            "assumptions": assumptions, "generator": "deterministic", "plan": plan}
