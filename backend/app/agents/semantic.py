"""Semantic layer — governed, certified metric definitions.

A *metric* is a business-meaningful measure (revenue, order count, AOV) pinned to
a **canonical SQL expression + base table + synonyms**. When a question names a
governed metric (by name or synonym), Nexus computes it from the *certified*
definition instead of the planner's best guess — so an answer hits the number the
business has agreed on, and the UI can show which certified metric was used.

This is the enterprise-BI wedge (LookML / dbt-metrics / Cube): one governed place
to define "what revenue means", reused by every question, every dashboard, every
monitor. Definitions live in the app store (per-connection, user-editable); this
module owns the *seed* for the Olist demo and the *resolution* logic.

The resolved metric is shaped exactly like a planner metric (``expr``/``base``/
``alias``/``term``) so it drops straight into ``plan["metric"]`` and flows through
the existing deterministic synthesizer + five-layer safety gate unchanged.
"""
from __future__ import annotations

import re

# Seed metrics for the Olist demo connection — the hardcoded planner library,
# promoted to first-class *certified* definitions with business names + synonyms.
# (name, expression, base_table, alias, [synonyms], description)
DEMO_METRIC_SEED: list[dict] = [
    {"name": "Merchandise Revenue",
     "expression": "ROUND(SUM(order_items.line_merchandise_value), 2)",
     "base_table": "order_items", "alias": "merchandise_revenue",
     "synonyms": ["revenue", "sales", "merchandise revenue", "net revenue",
                  "product revenue"],
     "description": "Sum of item prices, excluding freight. The default revenue "
                    "definition — what the business means by 'revenue'."},
    {"name": "Gross Order Value",
     "expression": "ROUND(SUM(order_items.line_total_value), 2)",
     "base_table": "order_items", "alias": "gross_order_value",
     "synonyms": ["gross order value", "gross value", "gmv", "gross merchandise value"],
     "description": "Merchandise value plus freight — total transacted value."},
    {"name": "Freight Revenue",
     "expression": "ROUND(SUM(order_items.freight_value), 2)",
     "base_table": "order_items", "alias": "freight_value",
     "synonyms": ["freight", "shipping", "shipping revenue", "freight cost"],
     "description": "Sum of freight (shipping) charges."},
    {"name": "Units Sold",
     "expression": "COUNT(*)", "base_table": "order_items", "alias": "units_sold",
     "synonyms": ["units sold", "units", "items sold", "quantity"],
     "description": "Count of order-line items."},
    {"name": "Order Count",
     "expression": "COUNT(DISTINCT orders.order_id)", "base_table": "orders",
     "alias": "order_count",
     "synonyms": ["order count", "orders", "number of orders", "how many orders"],
     "description": "Distinct orders."},
    {"name": "Unique Customers",
     "expression": "COUNT(DISTINCT orders.customer_unique_id)", "base_table": "orders",
     "alias": "unique_customer_count",
     "synonyms": ["unique customers", "customers", "shoppers", "buyers"],
     "description": "Distinct customers (deduplicated across accounts)."},
    {"name": "Average Order Value",
     "expression": "ROUND(AVG(orders.order_line_total_value), 2)",
     "base_table": "orders", "alias": "average_order_value",
     "synonyms": ["average order value", "aov", "avg order value", "basket size"],
     "description": "Mean total value per order."},
    {"name": "Average Review Score",
     "expression": "ROUND(AVG(orders.average_review_score), 2)",
     "base_table": "orders", "alias": "average_review_score",
     "synonyms": ["review score", "average review score", "rating", "satisfaction",
                  "csat"],
     "description": "Mean customer review score (1-5)."},
    {"name": "Payment Value",
     "expression": "ROUND(SUM(payments.payment_value), 2)",
     "base_table": "payments", "alias": "payment_value",
     "synonyms": ["payment value", "payments", "amount paid", "collected"],
     "description": "Sum of recorded payment amounts."},
]


def seed_demo_metrics(store, connection_id: str) -> int:
    """Idempotently populate a connection with the demo's certified metrics.
    Returns the number of metrics inserted (0 if already seeded)."""
    if store.count_metrics(connection_id) > 0:
        return 0
    n = 0
    for m in DEMO_METRIC_SEED:
        store.create_metric(
            connection_id, name=m["name"], expression=m["expression"],
            base_table=m["base_table"], alias=m["alias"],
            synonyms=m["synonyms"], description=m["description"], certified=True)
        n += 1
    return n


def _phrases(metric: dict) -> list[str]:
    """All matchable phrases for a metric — its name + synonyms, lowercased."""
    out = [metric["name"].lower()]
    out.extend(s.lower() for s in (metric.get("synonyms") or []))
    return out


def resolve_metric(question: str, metrics: list[dict]) -> dict | None:
    """Match a question to a governed metric by name/synonym (word-boundary).

    Longest phrase wins (so "average order value" beats "orders"), and a certified
    metric is preferred on a tie. Returns a planner-shaped metric dict augmented
    with ``governed`` metadata, or ``None`` when nothing matches.
    """
    ql = question.lower()
    best: tuple[int, int, dict, str] | None = None  # (phrase_len, certified, metric, phrase)
    for m in metrics:
        for phrase in _phrases(m):
            if not phrase:
                continue
            if re.search(r"\b" + re.escape(phrase) + r"\b", ql):
                rank = (len(phrase), int(m.get("certified", False)))
                if best is None or rank > (best[0], best[1]):
                    best = (len(phrase), int(m.get("certified", False)), m, phrase)
    if best is None:
        return None
    _, _, m, phrase = best
    return {
        "expr": m["expression"], "base": m["base_table"], "alias": m["alias"],
        "term": m["name"],
        "governed": {"id": m["id"], "name": m["name"],
                     "certified": bool(m.get("certified")),
                     "matched_phrase": phrase, "expression": m["expression"]},
    }
