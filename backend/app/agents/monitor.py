"""Monitor runner — run a saved question, detect anomalies, raise alerts.

A monitor is a (question, connection) that runs on a schedule. For a time-series
answer we flag when the most recent period deviates from its trailing baseline
(z-score); the graph's own anomaly node also contributes. Alerts land in an inbox.

The "schedule" is external: a cron / GitHub Action hits POST /monitors/run-all.
This is the correct free-tier design (no always-on worker) and is documented.
"""
from __future__ import annotations

import statistics

from app.agents.graph import run_analysis_collect
from app.api.deps import resolve_connection_url
from app.db.app_store import get_store


def _numeric_series(result: dict) -> tuple[str, list[float]] | None:
    enc = result.get("chart_spec", {}).get("encodings", {})
    if result.get("chart_spec", {}).get("type") != "line":
        return None
    y = enc.get("y")
    if not y:
        return None
    vals = [r[y] for r in result.get("rows", [])
            if isinstance(r.get(y), (int, float)) and not isinstance(r.get(y), bool)]
    return (y, vals) if len(vals) >= 4 else None


def run_monitor(monitor: dict) -> dict:
    store = get_store()
    url = resolve_connection_url(monitor["connection_id"])
    result = run_analysis_collect(monitor["question"],
                                  connection_id=monitor["connection_id"],
                                  connection_url=url, persist=False)
    created_alerts: list[dict] = []

    if result.get("blocked") or result.get("error"):
        store.mark_monitor_run(monitor["id"], "error")
        return {"monitor_id": monitor["id"], "status": "error",
                "alerts": [], "result": result}

    series = _numeric_series(result)
    if series:
        y, vals = series
        # Robust check: latest period vs a trailing baseline (median + MAD
        # modified z-score). Robust to ramp-up months and outliers.
        window = vals[-13:-1] if len(vals) > 13 else vals[:-1]
        last = vals[-1]
        med = statistics.median(window)
        mad = statistics.median([abs(v - med) for v in window]) or 1e-9
        if mad < 1e-6:
            mad = (statistics.pstdev(window) or 1.0) * 0.6745
        mz = 0.6745 * (last - med) / mad
        if abs(mz) >= 3.5:
            severity = "high" if abs(mz) >= 6 else "medium"
            direction = "above" if mz > 0 else "below"
            pct = (last - med) / abs(med) * 100 if med else 0
            msg = (f"Latest {y.replace('_', ' ')} = {last:,.0f} is {abs(mz):.1f} "
                   f"(robust z) {direction} the trailing baseline "
                   f"({med:,.0f}), {pct:+.0f}%.")
            aid = store.add_alert(monitor["id"], monitor["name"], severity, msg,
                                  metric=round(float(last), 2),
                                  detail={"z": round(mz, 2), "baseline": round(med, 2),
                                          "question": monitor["question"]})
            created_alerts.append({"id": aid, "severity": severity, "message": msg})

    store.mark_monitor_run(monitor["id"], "ok")
    return {"monitor_id": monitor["id"], "status": "ok",
            "alerts": created_alerts, "result": result}


def run_all_monitors() -> dict:
    store = get_store()
    monitors = store.list_monitors(enabled_only=True)
    runs, total_alerts = [], 0
    for m in monitors:
        r = run_monitor(m)
        total_alerts += len(r["alerts"])
        runs.append({"monitor_id": m["id"], "name": m["name"],
                     "status": r["status"], "alerts": len(r["alerts"])})
    return {"monitors_run": len(monitors), "alerts_raised": total_alerts, "runs": runs}
