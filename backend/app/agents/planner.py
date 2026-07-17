"""Planner node — decompose the NL question into a structured intent.

Deterministic by default (keyword/grammar parse into metric / dimension / grain /
filters / top-N), with an LLM path when a provider is configured. Records
``assumptions`` (e.g. how "last quarter" was resolved) so every answer is
explainable, and flags write-intent for a hard stop (MVP blocks writes).
"""
from __future__ import annotations

import re

from app.llm.client import get_llm

# metric term -> (canonical expression, base table, output alias, agg-kind)
METRICS: dict[str, dict] = {
    "merchandise revenue": {"expr": "ROUND(SUM(order_items.line_merchandise_value), 2)",
                            "base": "order_items", "alias": "merchandise_revenue"},
    "revenue": {"expr": "ROUND(SUM(order_items.line_merchandise_value), 2)",
                "base": "order_items", "alias": "merchandise_revenue"},
    "gross order value": {"expr": "ROUND(SUM(order_items.line_total_value), 2)",
                          "base": "order_items", "alias": "gross_order_value"},
    "gross value": {"expr": "ROUND(SUM(order_items.line_total_value), 2)",
                    "base": "order_items", "alias": "gross_order_value"},
    "freight": {"expr": "ROUND(SUM(order_items.freight_value), 2)",
                "base": "order_items", "alias": "freight_value"},
    "units sold": {"expr": "COUNT(*)", "base": "order_items", "alias": "units_sold"},
    "units": {"expr": "COUNT(*)", "base": "order_items", "alias": "units_sold"},
    "order count": {"expr": "COUNT(DISTINCT orders.order_id)", "base": "orders",
                    "alias": "order_count"},
    "orders": {"expr": "COUNT(DISTINCT orders.order_id)", "base": "orders",
               "alias": "order_count"},
    "unique customers": {"expr": "COUNT(DISTINCT orders.customer_unique_id)",
                         "base": "orders", "alias": "unique_customer_count"},
    "customers": {"expr": "COUNT(DISTINCT orders.customer_unique_id)",
                  "base": "orders", "alias": "unique_customer_count"},
    "average order value": {"expr": "ROUND(AVG(orders.order_line_total_value), 2)",
                            "base": "orders", "alias": "average_order_value"},
    "review score": {"expr": "ROUND(AVG(orders.average_review_score), 2)",
                     "base": "orders", "alias": "average_review_score"},
    "payment value": {"expr": "ROUND(SUM(payments.payment_value), 2)",
                      "base": "payments", "alias": "payment_value"},
}

# dimension keyword -> (label column, owning table, group expression)
DIMENSIONS: dict[str, dict] = {
    "category": {"table": "categories", "col": "categories.category_name_en",
                 "label": "category_name_en"},
    "categories": {"table": "categories", "col": "categories.category_name_en",
                   "label": "category_name_en"},
    "state": {"table": "regions", "col": "regions.state_code", "label": "state_code"},
    "region": {"table": "regions", "col": "regions.macroregion_name_en",
               "label": "macroregion_name_en"},
    "payment type": {"table": "payments", "col": "payments.payment_type",
                     "label": "payment_type"},
    "payment method": {"table": "payments", "col": "payments.payment_type",
                       "label": "payment_type"},
    "status": {"table": "orders", "col": "orders.order_status", "label": "order_status"},
    "seller state": {"table": "sellers", "col": "sellers.seller_state",
                     "label": "seller_state"},
    "seller": {"table": "sellers", "col": "sellers.seller_id", "label": "seller_id"},
    "product": {"table": "products", "col": "order_items.product_id",
                "label": "product_id"},
    "macroregion": {"table": "regions", "col": "regions.macroregion_name_en",
                    "label": "macroregion_name_en"},
    "city": {"table": "customers", "col": "customers.customer_city",
             "label": "customer_city"},
}

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
    "twenty": 20, "twenty-five": 25, "fifty": 50, "hundred": 100,
}
_TOPN = re.compile(r"\btop\s+(\d{1,3})\b", re.I)
_TOPN_WORD = re.compile(
    r"\b(?:top|first|which|best|leading|highest)\s+"
    r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|"
    r"twenty(?:-five)?|fifty|hundred)\b", re.I)
_TOPN_WORD_DIGIT = re.compile(r"\b(?:which|top|first|best)\s+(\d{1,3})\b", re.I)
_TIME_WORDS = re.compile(
    r"\b(monthly|per month|over time|trend|each month|by month|month over month|"
    r"time series|timeline)\b", re.I)
_WRITE_WORDS = re.compile(
    r"\b(delete|drop|update|insert|truncate|alter|create|modify|remove)\b", re.I)


def _match_metric(q: str) -> dict:
    ql = q.lower()
    # longest term first for specificity ("merchandise revenue" before "revenue")
    for term in sorted(METRICS, key=len, reverse=True):
        if term in ql:
            return {**METRICS[term], "term": term}
    # heuristics
    if re.search(r"\bhow many\b.*\border", ql) or "number of orders" in ql:
        return {**METRICS["order count"], "term": "order count"}
    if "how many" in ql and ("customer" in ql or "shopper" in ql):
        return {**METRICS["unique customers"], "term": "unique customers"}
    return {**METRICS["revenue"], "term": "revenue (default)"}


def _match_dimension(q: str) -> dict | None:
    ql = q.lower()
    for term in sorted(DIMENSIONS, key=len, reverse=True):
        if term in ql:
            return {**DIMENSIONS[term], "term": term}
    return None


def _match_filters(q: str) -> list[dict]:
    ql = q.lower()
    filters = []
    if "delivered" in ql:
        filters.append({"sql": "orders.delivered_status_flag = 1", "label": "delivered"})
    if "canceled" in ql or "cancelled" in ql:
        filters.append({"sql": "orders.canceled_status_flag = 1", "label": "canceled"})
    if "late" in ql and "deliver" in ql:
        filters.append({"sql": "orders.delivered_late_flag = 1", "label": "late deliveries"})
    return filters


def plan_question(question: str) -> dict:
    llm = get_llm()
    if llm.is_llm:
        # The LLM plan is advisory; the deterministic structure below still runs so
        # the synthesizer always has a grounded skeleton. (LLM SQL path in generator.)
        pass

    metric = _match_metric(question)
    dimension = _match_dimension(question)
    is_time = bool(_TIME_WORDS.search(question))
    top_n = None
    for m in (_TOPN.search(question), _TOPN_WORD_DIGIT.search(question)):
        if m:
            top_n = int(m.group(1))
            break
    if top_n is None:
        wm = _TOPN_WORD.search(question)
        if wm:
            top_n = _NUMBER_WORDS.get(wm.group(1).lower())
    filters = _match_filters(question)
    write_intent = bool(_WRITE_WORDS.search(question))

    if is_time:
        shape = "timeseries"
    elif dimension or top_n:
        shape = "groupby"
    else:
        shape = "scalar"

    assumptions: list[str] = []
    if metric["term"] == "revenue (default)":
        assumptions.append("Interpreted 'revenue' as merchandise revenue "
                           "(SUM of item prices, excluding freight).")
    if top_n and not dimension:
        assumptions.append(f"'top {top_n}' requested without an explicit dimension; "
                           "grouped by product category by default.")

    return {
        "metric": metric,
        "dimension": dimension,
        "shape": shape,
        "top_n": top_n,
        "filters": filters,
        "is_time_series": is_time,
        "write_intent": write_intent,
        "assumptions": assumptions,
        "intent_summary": _summarize(metric, dimension, shape, top_n, filters),
    }


def _summarize(metric, dimension, shape, top_n, filters) -> str:
    parts = [f"compute {metric['alias']}"]
    if shape == "timeseries":
        parts.append("as a monthly time series")
    elif dimension:
        parts.append(f"grouped by {dimension['label']}")
    if top_n:
        parts.append(f"top {top_n}")
    if filters:
        parts.append("filtered to " + ", ".join(f["label"] for f in filters))
    return " ".join(parts)
