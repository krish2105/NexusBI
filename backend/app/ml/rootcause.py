"""Root-cause / contribution analysis — answers "why did it change?".

Given a prior time-series metric, decompose it by a categorical dimension across
the two most recent complete periods and attribute the period-over-period change
to specific members ("the decline was driven mainly by X (-45% of the move)").

This is deterministic contribution analysis — the LLM never invents a driver; the
numbers come straight from the (safety-validated) decomposition query. It's the
capability that turns "revenue dropped" into "revenue dropped *because*".
"""
from __future__ import annotations

import statistics

from app.agents.sql_generator import synthesize_decomposition
from app.config import settings
from app.db.introspect import cached_allow_list
from app.db.joingraph import cached_join_graph
from app.db.target_pool import TargetPool
from app.sqlsafety.guard import validate_sql

# Sensible default decomposition dimension by metric base table.
_DEFAULT_DECOMP = {
    "order_items": {"table": "categories", "col": "categories.category_name_en",
                    "label": "category"},
    "orders": {"table": "regions", "col": "regions.macroregion_name_en",
               "label": "region"},
    "payments": {"table": "payments", "col": "payments.payment_type",
                 "label": "payment type"},
}


def _fmt(v: float) -> str:
    return f"{v:,.0f}"


def explain_change(plan: dict, url: str | None = None, top_k: int = 6) -> dict:
    url = url or settings.demo_target_url
    metric = plan["metric"]
    decomp = plan.get("dimension") or _DEFAULT_DECOMP.get(
        metric["base"], _DEFAULT_DECOMP["order_items"])
    # normalize a plan dimension into the shape we need
    decomp = {"table": decomp["table"], "col": decomp["col"],
              "label": decomp.get("label", decomp["col"])}

    sql = synthesize_decomposition(metric, decomp, plan.get("filters"),
                                   graph=cached_join_graph(url))
    allow = cached_allow_list(url)
    report = validate_sql(sql, allow, target_dialect="sqlite")
    if not report.allowed:
        return {"available": False, "reason": "decomposition query failed validation"}

    rows = TargetPool(url=url).execute(report.safe_sql).rows
    if not rows:
        return {"available": False, "reason": "no data to decompose"}

    # period -> {member: val}, and period totals
    by_period: dict[str, dict[str, float]] = {}
    for r in rows:
        by_period.setdefault(r["period"], {})[r["member"]] = float(r["val"] or 0)
    totals = {p: sum(m.values()) for p, m in by_period.items()}

    # Drop trailing partial periods (near-zero totals — real data tails off).
    periods = sorted(totals)
    if len(periods) >= 4:
        med = statistics.median(sorted(totals.values()))
        thresh = 0.10 * med
        while len(periods) > 2 and totals[periods[-1]] < thresh:
            periods.pop()
    if len(periods) < 2:
        return {"available": False, "reason": "need at least two comparable periods"}

    p1, p2 = periods[-2], periods[-1]
    members = set(by_period[p1]) | set(by_period[p2])
    total_change = totals[p2] - totals[p1]

    contributors = []
    for m in members:
        v1 = by_period[p1].get(m, 0.0)
        v2 = by_period[p2].get(m, 0.0)
        delta = v2 - v1
        contributors.append({
            "member": m, "from": round(v1, 2), "to": round(v2, 2),
            "delta": round(delta, 2),
            "contribution_pct": round(delta / total_change * 100, 1)
            if total_change else None,
        })
    contributors.sort(key=lambda c: -abs(c["delta"]))
    contributors = contributors[:top_k]

    pct = (total_change / totals[p1] * 100) if totals[p1] else 0
    direction = "rose" if total_change >= 0 else "fell"
    lead = contributors[0] if contributors else None
    narrative = (
        f"Between {p1} and {p2}, {metric['alias'].replace('_', ' ')} {direction} "
        f"{abs(pct):.0f}% ({_fmt(totals[p1])} → {_fmt(totals[p2])}, "
        f"{'+' if total_change >= 0 else ''}{_fmt(total_change)}).")
    if lead and lead["contribution_pct"] is not None:
        movers = ", ".join(
            f"{c['member']} ({'+' if c['delta'] >= 0 else ''}{_fmt(c['delta'])}, "
            f"{c['contribution_pct']:.0f}% of the move)"
            for c in contributors[:3])
        narrative += f" The change was driven mainly by {movers}."

    return {
        "available": True,
        "decomposition_dimension": decomp["label"],
        "period_from": p1, "period_to": p2,
        "total_from": round(totals[p1], 2), "total_to": round(totals[p2], 2),
        "total_change": round(total_change, 2),
        "pct_change": round(pct, 1),
        "contributors": contributors,
        "sql": report.safe_sql,
        "narrative": narrative,
    }
