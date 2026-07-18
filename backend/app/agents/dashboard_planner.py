"""NL → dashboard planning.

Turn a plain-English description ("an executive overview", "a delivery dashboard
for the North region") into a themed set of questions that compose a dashboard.
Deterministic recipes cover the common BI themes; a detected scope (region /
state / status / payment) is applied to every tile. An LLM, when configured, can
generate the question list from the description + schema; the deterministic
planner is the zero-key default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agents.followup import _detect_scope_filters
from app.agents.sql_generator import _classify_cols, is_olist_schema
from app.db.target_pool import TargetPool
from app.rag.retriever import retrieve_schema

# theme -> (title, [questions]) — grounded in the Olist demo schema.
_THEMES: dict[str, tuple[str, list[str]]] = {
    "executive": ("Executive Overview", [
        "Total merchandise revenue",
        "How many orders are there?",
        "How many unique customers are there?",
        "Show monthly merchandise revenue over time",
        "Top 5 product categories by merchandise revenue",
        "Top 10 customer states by number of orders",
    ]),
    "sales": ("Sales & Revenue", [
        "Total merchandise revenue",
        "Total gross order value including freight",
        "Show monthly merchandise revenue over time",
        "Top 10 product categories by merchandise revenue",
        "Payment value by payment type",
        "Gross order value by Brazilian macroregion",
    ]),
    "delivery": ("Delivery Performance", [
        "What is the late-delivery rate by customer state?",
        "Show order counts by status",
        "How many delivered orders are there?",
        "What is the average review score by customer state?",
        "Top 10 customer states by number of orders",
    ]),
    "customer": ("Customer Insights", [
        "How many unique customers are there?",
        "How many shoppers made repeat purchases?",
        "Top 10 customer states by number of orders",
        "What is the average review score by customer state?",
        "Show monthly orders and unique customers",
    ]),
}

_THEME_KEYWORDS = {
    "delivery": ("deliver", "logistic", "fulfil", "shipping", "freight", "operation",
                 "carrier"),
    "customer": ("customer", "shopper", "retention", "loyal", "churn", "segment"),
    "sales": ("sales", "revenue", "financial", "money", "gmv", "income", "earning"),
    "executive": ("executive", "overview", "summary", "kpi", "board", "health",
                  "snapshot"),
}


@dataclass
class DashboardPlan:
    title: str
    theme: str
    questions: list[str]
    scope_filters: list[dict] = field(default_factory=list)
    scope_label: str | None = None


def _pick_theme(desc: str) -> str:
    d = desc.lower()
    for theme, kws in _THEME_KEYWORDS.items():
        if theme == "executive":
            continue
        if any(k in d for k in kws):
            return theme
    return "executive"


def _title_from(desc: str, default: str, scope_label: str | None) -> str:
    d = desc.strip()
    if d and len(d) <= 60 and not d.lower().startswith(("build", "make", "create",
                                                        "generate", "a ", "an ")):
        base = d[0].upper() + d[1:]
    else:
        base = default
    if scope_label and scope_label.lower() not in base.lower():
        base += f" — {scope_label}"
    return base


def _generic_questions(url: str) -> tuple[str, list[str]]:
    """For an arbitrary uploaded schema: a few questions from the widest table."""
    schema = retrieve_schema("overview summary total by", connection_url=url, k=3)
    if not schema.tables:
        return "Overview", ["How many rows are there?"]
    table = max(schema.tables, key=lambda t: len(t.columns))
    dates, numerics, texts = _classify_cols(table)
    qs = [f"How many {table.name} records are there?"]
    if numerics:
        n = numerics[0]
        qs.append(f"What is the total {n}?")
        if texts:
            qs.append(f"Total {n} by {texts[0]}")
        if dates:
            qs.append(f"Show {n} over time")
    elif texts:
        qs.append(f"Count of {table.name} by {texts[0]}")
    return f"{table.name.title()} Overview", qs


def plan_dashboard(description: str, url: str) -> DashboardPlan:
    scope_filters = _detect_scope_filters(description, url)
    scope_label = ", ".join(f["label"] for f in scope_filters) if scope_filters else None

    # Themed recipes for the Olist star schema; generic derivation otherwise.
    if is_olist_schema(retrieve_schema(description or "overview", connection_url=url, k=8)):
        theme = _pick_theme(description)
        title_default, questions = _THEMES[theme]
    else:
        theme = "generic"
        title_default, questions = _generic_questions(url)
        scope_filters, scope_label = [], None  # scope catalog is Olist-specific

    return DashboardPlan(
        title=_title_from(description, title_default, scope_label),
        theme=theme, questions=list(questions),
        scope_filters=scope_filters, scope_label=scope_label,
    )
