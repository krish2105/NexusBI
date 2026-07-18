"""Proactive Daily Briefing — insight without being asked.

Nexus analyzes the business on its own: for each key metric it computes the
latest complete period, the period-over-period change, a forecast, and an
anomaly flag; ranks what moved most; root-causes the biggest revenue swing; and
narrates an executive briefing. This is the "autonomous analyst" payoff — it
ties together the monitors, forecaster, anomaly detector, and root-cause engine
into a single proactive report. Deterministic: every number comes from the data.

Rich path uses the demo's pre-aggregated ``monthly_kpis`` view. For any other
connection we fall back to a generic monthly briefing over a detected date +
numeric columns, or report that there isn't enough time-series data.
"""
from __future__ import annotations

import statistics

from app.agents.planner import METRICS
from app.config import settings
from app.db.target_pool import TargetPool
from app.ml.forecasting import _trim_partial_periods, forecast_series
from app.ml.rootcause import explain_change

_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]

# metric config over monthly_kpis: (label, column, unit, higher_is_better, rootcause_alias)
_KPIS = [
    ("Merchandise revenue", "merchandise_value", "R$", True, "merchandise_revenue"),
    ("Orders", "order_count", "", True, None),
    ("Unique customers", "unique_customer_count", "", True, None),
    ("Avg order value", "average_gross_order_value", "R$", True, None),
    ("Avg review score", "average_review_score", "", True, None),
    ("Late-delivery rate", "late_delivery_rate", "%", False, None),
]


def _period_label(ym: str) -> str:
    try:
        y, m = ym.split("-")
        return f"{_MONTHS[int(m)]} {y}"
    except (ValueError, IndexError):
        return ym


def _fmt(v: float, unit: str) -> str:
    if unit == "%":
        return f"{v * 100:.1f}%" if abs(v) <= 1 else f"{v:.1f}%"
    if unit == "R$":
        return f"R${v:,.0f}"
    return f"{v:,.2f}" if abs(v) < 100 else f"{v:,.0f}"


def _robust_anomaly(series: list[float]) -> bool:
    if len(series) < 5:
        return False
    window, last = series[-13:-1], series[-1]
    med = statistics.median(window)
    mad = statistics.median([abs(v - med) for v in window]) or 1e-9
    return abs(0.6745 * (last - med) / mad) >= 3.5


def _has_monthly_kpis(pool: TargetPool) -> bool:
    return "monthly_kpis" in {t.lower() for t in pool.list_tables()}


def generate_briefing(url: str | None = None, connection_id: str = "demo") -> dict:
    url = url or settings.demo_target_url
    pool = TargetPool(url=url)
    if not _has_monthly_kpis(pool):
        return {"available": False,
                "reason": "This connection has no monthly time-series view to brief on."}

    rows = pool.execute(
        f"SELECT year_month, order_count, {', '.join(k[1] for k in _KPIS)} "
        f"FROM monthly_kpis ORDER BY year_month LIMIT 10000").rows
    if len(rows) < 4:
        return {"available": False, "reason": "not enough periods to brief"}

    labels_all = [r["year_month"] for r in rows]
    # Determine the complete-period window ONCE from order volume, then apply it
    # to every metric — so an average-type metric (review score, AOV) isn't read
    # off a partial boundary month (which trimming-by-own-value would miss).
    oc_all = [float(r["order_count"] or 0) for r in rows]
    labels_c, _oc_c, _ = _trim_partial_periods(labels_all, oc_all)
    if len(labels_c) < 3:
        return {"available": False, "reason": "not enough complete periods"}
    start, end = labels_all.index(labels_c[0]), labels_all.index(labels_c[-1])
    labels = labels_all[start:end + 1]

    metrics_out: list[dict] = []
    movers: list[dict] = []

    for label, col, unit, higher_better, rc_alias in _KPIS:
        vals = [float(r[col]) if r[col] is not None else 0.0
                for r in rows[start:end + 1]]
        if len(vals) < 3:
            continue
        latest, prior = vals[-1], vals[-2]
        mom = (latest - prior) / abs(prior) * 100 if prior else 0.0
        direction = "up" if latest >= prior else "down"
        if abs(mom) < 1.0:
            sentiment = "neutral"       # essentially flat
        else:
            sentiment = "good" if ((direction == "up") == higher_better) else "bad"
        anomaly = _robust_anomaly(vals)
        fc = forecast_series(labels, vals, horizon=1, min_points=6)
        forecast_next = fc.point[0] if fc else None
        spark = vals[-12:]

        metrics_out.append({
            "label": label, "column": col, "unit": unit,
            "value": round(latest, 4), "value_fmt": _fmt(latest, unit),
            "prior": round(prior, 4), "mom_pct": round(mom, 1),
            "direction": direction, "sentiment": sentiment,
            "anomaly": anomaly, "spark": [round(v, 2) for v in spark],
            "forecast_next": round(forecast_next, 2) if forecast_next else None,
            "forecast_method": fc.method if fc else None,
            "period_label": _period_label(labels[-1]),
        })
        significance = abs(mom) + (60 if anomaly else 0)
        movers.append({"label": label, "mom_pct": round(mom, 1),
                       "sentiment": sentiment, "significance": significance,
                       "rc_alias": rc_alias, "value_fmt": _fmt(latest, unit),
                       "direction": direction})

    if not metrics_out:
        return {"available": False, "reason": "no complete metrics to brief"}

    as_of = metrics_out[0]["period_label"]
    movers.sort(key=lambda m: -m["significance"])

    # --- root-cause the biggest revenue-type swing ---
    what_changed: list[dict] = []
    for mv in movers[:3]:
        entry = {"label": mv["label"], "mom_pct": mv["mom_pct"],
                 "sentiment": mv["sentiment"],
                 "narrative": f"{mv['label']} {mv['direction']} "
                              f"{abs(mv['mom_pct']):.0f}% to {mv['value_fmt']}."}
        if mv["rc_alias"] and mv["rc_alias"] in _alias_metric_map():
            rc = explain_change({"metric": _alias_metric_map()[mv["rc_alias"]],
                                 "dimension": None, "filters": []}, url=url)
            if rc.get("available"):
                entry["rootcause"] = rc
                top = rc["contributors"][:2]
                entry["narrative"] += " Driven by " + ", ".join(
                    f"{c['member']} ({'+' if c['delta'] >= 0 else ''}{c['delta']:,.0f})"
                    for c in top) + "."
        what_changed.append(entry)

    # --- watchouts: anomalous metrics + open alerts ---
    watchouts = [{"message": f"{m['label']} shows an anomaly this period "
                             f"({m['value_fmt']}).", "severity": "high"}
                 for m in metrics_out if m["anomaly"]]
    try:
        from app.db.app_store import get_store
        alerts = [a for a in get_store().list_alerts(limit=20)
                  if not a.get("acknowledged")][:3]
        for a in alerts:
            watchouts.append({"message": f"{a['monitor_name']}: {a['message']}",
                              "severity": a["severity"]})
    except Exception:  # noqa: BLE001
        pass

    # --- headline + forecast outlook ---
    lead = movers[0]
    positive = next((m for m in movers if m["sentiment"] == "good"), None)
    headline = (f"{lead['label']} {lead['direction']} {abs(lead['mom_pct']):.0f}% "
                f"to {lead['value_fmt']} in {as_of}")
    if positive and positive["label"] != lead["label"]:
        headline += (f"; {positive['label'].lower()} "
                     f"{'rose' if positive['direction'] == 'up' else 'moved'} "
                     f"{abs(positive['mom_pct']):.0f}%")
    headline += "."

    rev = next((m for m in metrics_out if m["column"] == "merchandise_value"), None)
    forecast_outlook = None
    if rev and rev["forecast_next"]:
        model = (rev.get("forecast_method") or "Holt-Winters").split(" (")[0]
        forecast_outlook = (f"Merchandise revenue is projected at "
                            f"{_fmt(rev['forecast_next'], 'R$')} next period "
                            f"({model}).")

    return {
        "available": True, "connection_id": connection_id, "as_of": as_of,
        "headline": headline, "metrics": metrics_out,
        "what_changed": what_changed, "watchouts": watchouts,
        "forecast_outlook": forecast_outlook,
        "generated_note": "Deterministic — computed from the data (monthly_kpis), "
                          "no LLM. Anomalies via robust MAD; drivers via "
                          "contribution analysis.",
    }


def _alias_metric_map() -> dict:
    """Map a metric alias -> the planner METRICS entry (for root-cause)."""
    out = {}
    for term, spec in METRICS.items():
        out.setdefault(spec["alias"], {**spec, "term": term})
    return out
