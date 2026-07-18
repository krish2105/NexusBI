"""Follow-up resolution — turns a conversation into a real analyst dialogue.

A follow-up ("now drill into the North region", "break it down by category",
"top 10 instead", "why did it drop?") is interpreted as *the previous turn's
analysis plus a delta*. We carry the prior plan forward and apply the change,
producing a resolved standalone question + a seed plan the SQL synthesizer
consumes — so follow-ups reuse the exact same grounded, safety-checked pipeline.

Deterministic and explainable (each turn reports what it inherited and changed);
an LLM, when configured, can additionally rewrite gnarlier references, but the
deterministic resolver handles the common analyst moves on its own.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.agents.planner import (DIMENSIONS, _TOPN, _TOPN_WORD, _NUMBER_WORDS,
                               _TIME_WORDS, _match_dimension, plan_question)
from app.db.target_pool import TargetPool

_CUE = re.compile(
    r"\b(it|its|that|those|these|them|this|instead|rather|now|then|also|too|"
    r"as well|what about|how about|drill|break\s+(?:it\s+)?down|filter|just|only|"
    r"same|compare|overall|across|for the|in the|within)\b", re.I)
_WHY = re.compile(
    r"\b(why|what\s+(?:caused|drove|explains|happened)|reason|cause|driver|"
    r"explain\s+the)\b", re.I)
_RESET_FILTERS = re.compile(
    r"\b(overall|across all|all regions|everything|remove\s+(?:the\s+)?filter|"
    r"reset|whole|entire)\b", re.I)
_EXPLICIT_METRIC = re.compile(
    r"\b(revenue|merchandise|gross|freight|units?|orders?|customers?|shoppers?|"
    r"review score|payment value|average order value|aov)\b", re.I)


# --- grounded filter-value catalog (curated low-cardinality dimensions) ------
# (column_fqn, table, distinct-query, matcher-kind)
_FILTER_DIMS = [
    ("regions.macroregion_name_en", "regions",
     "SELECT DISTINCT macroregion_name_en AS v FROM regions", "phrase"),
    ("regions.state_name_pt", "regions",
     "SELECT DISTINCT state_name_pt AS v FROM regions", "phrase"),
    ("regions.state_code", "regions",
     "SELECT DISTINCT state_code AS v FROM regions", "code"),
    ("payments.payment_type", "payments",
     "SELECT DISTINCT payment_type AS v FROM payments", "phrase"),
    ("orders.order_status", "orders",
     "SELECT DISTINCT order_status AS v FROM orders", "phrase"),
    ("categories.category_name_en", "categories",
     "SELECT DISTINCT category_name_en AS v FROM categories", "phrase"),
]


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(s).strip().lower())


@lru_cache(maxsize=8)
def _filter_catalog(url: str) -> tuple:
    """List of (column_fqn, table, value, normalized, kind). Cached per connection."""
    pool = TargetPool(url=url)
    live = {t.lower() for t in pool.list_tables()}
    out: list = []
    for col, table, q, kind in _FILTER_DIMS:
        if table not in live:
            continue
        try:
            for r in pool.execute(q + " LIMIT 500").rows:
                v = r["v"]
                if v is None:
                    continue
                out.append((col, table, str(v), _norm(v), kind))
        except Exception:  # noqa: BLE001
            continue
    return tuple(out)


def _detect_scope_filters(question: str, url: str) -> list[dict]:
    """Match grounded dimension values in the question -> WHERE predicates."""
    nq = _norm(question)
    found: list[dict] = []
    seen: set = set()
    for col, table, value, nval, kind in _filter_catalog(url):
        if len(nval) < 2:
            continue
        hit = False
        if kind == "code":
            # 2-letter state codes: match only as standalone UPPERCASE tokens.
            hit = re.search(rf"\b{re.escape(value)}\b", question) is not None \
                and value.isupper()
        else:
            hit = re.search(rf"\b{re.escape(nval)}\b", nq) is not None
        key = (col, value)
        if hit and key not in seen:
            seen.add(key)
            found.append({"sql": f"{col} = '{value}'", "label": value,
                          "table": table})
    return found


def _explicit_metric(question: str) -> dict | None:
    """Return a metric ONLY if one is explicitly named (no default)."""
    from app.agents.planner import METRICS
    ql = question.lower()
    if not _EXPLICIT_METRIC.search(ql):
        return None
    for term in sorted(METRICS, key=len, reverse=True):
        if term in ql:
            return {**METRICS[term], "term": term}
    return None


@dataclass
class FollowupResolution:
    is_followup: bool
    mode: str                         # "fresh" | "refine" | "why"
    standalone_question: str
    seed_plan: dict | None = None
    inherited: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    why_context: dict | None = None


def is_followup(question: str, history: list[dict]) -> bool:
    if not history:
        return False
    ql = question.lower()
    if _WHY.search(ql):
        return True
    if _CUE.search(ql):
        return True
    tokens = re.findall(r"[a-z0-9]+", ql)
    if len(tokens) <= 4:
        return True
    # "by category" style (dimension change, no fresh metric anchor)
    if _match_dimension(question) and not re.search(r"\bhow many\b|\btotal\b", ql):
        return True
    return False


def _describe_plan(plan: dict) -> str:
    parts = [plan["metric"]["alias"].replace("_", " ")]
    if plan.get("shape") == "timeseries":
        parts.append("monthly")
    elif plan.get("dimension"):
        parts.append(f"by {plan['dimension']['label']}")
    if plan.get("top_n"):
        parts.append(f"(top {plan['top_n']})")
    if plan.get("filters"):
        parts.append("for " + ", ".join(f["label"] for f in plan["filters"]))
    return " ".join(parts)


def resolve(question: str, history: list[dict], url: str) -> FollowupResolution:
    """History = compact per-turn context (oldest first), each with a 'context'
    holding the resolved plan of that turn."""
    prior = None
    for turn in reversed(history or []):
        if (turn.get("context") or {}).get("plan"):
            prior = turn["context"]["plan"]
            break

    if prior is None or not is_followup(question, history):
        return FollowupResolution(is_followup=False, mode="fresh",
                                  standalone_question=question)

    # --- "why did it change?" -> root-cause branch ---
    if _WHY.search(question.lower()):
        return FollowupResolution(
            is_followup=True, mode="why",
            standalone_question=f"why did {prior['metric']['alias'].replace('_',' ')} "
                                "change",
            why_context={"plan": prior})

    # --- refine: carry prior plan forward, apply the delta ---
    plan = copy.deepcopy(prior)
    inherited = [f"metric: {plan['metric']['alias']}"]
    if plan.get("dimension"):
        inherited.append(f"grouped by {plan['dimension']['label']}")
    if plan.get("filters"):
        inherited.append("filters: " + ", ".join(f["label"] for f in plan["filters"]))
    changed: list[str] = []
    ql = question.lower()

    new_metric = _explicit_metric(question)
    if new_metric and new_metric["alias"] != plan["metric"]["alias"]:
        plan["metric"] = new_metric
        changed.append(f"metric → {new_metric['alias']}")

    # Re-pivot only on explicit grouping intent ("by/per/break down by <dim>");
    # a bare dimension noun (e.g. "North region") is a scope filter, not a pivot.
    if re.search(r"\b(by|per|break\s+(?:it\s+)?down\s+by|grouped?\s+by|split\s+by|"
                 r"across)\b", ql):
        new_dim = _match_dimension(question)
        if new_dim and (not plan.get("dimension")
                        or new_dim["label"] != plan["dimension"]["label"]):
            plan["dimension"] = new_dim
            plan["shape"] = "groupby"
            changed.append(f"grouped by {new_dim['label']}")

    if _TIME_WORDS.search(question):
        plan["shape"] = "timeseries"
        changed.append("monthly trend")

    for m in (_TOPN.search(question), _TOPN_WORD.search(question)):
        if m:
            g = m.group(1)
            plan["top_n"] = _NUMBER_WORDS.get(g.lower(), None) or int(g) \
                if g.isdigit() else _NUMBER_WORDS.get(g.lower())
            if plan["top_n"]:
                changed.append(f"top {plan['top_n']}")
            break

    if _RESET_FILTERS.search(question):
        if plan.get("filters"):
            plan["filters"] = []
            changed.append("cleared filters")
    else:
        for f in _detect_scope_filters(question, url):
            if not any(x["sql"] == f["sql"] for x in plan.get("filters", [])):
                plan.setdefault("filters", []).append(f)
                changed.append(f"scoped to {f['label']}")

    if not changed:
        changed.append("re-ran previous analysis")

    plan["intent_summary"] = _describe_plan(plan)
    return FollowupResolution(
        is_followup=True, mode="refine",
        standalone_question=_describe_plan(plan),
        seed_plan=plan, inherited=inherited, changed=changed)
