"""Narrator node — a concise, business-framed insight grounded ONLY in the real
numbers the database returned. The LLM (if configured) may phrase it, but never
invents figures; the deterministic narrator composes directly from the result.
"""
from __future__ import annotations


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _confidence(rows: list[dict], assumptions: list[str],
                anomalies: list[dict] | None) -> str:
    n = len(rows)
    score = 0
    score += 1 if n >= 3 else 0
    score += 1 if len(assumptions) <= 1 else 0
    score += 1 if not anomalies else 0
    return {3: "HIGH", 2: "MEDIUM"}.get(score, "LOW" if score < 2 else "MEDIUM")


def narrate(question: str, columns: list[str], rows: list[dict],
            chart_spec: dict, forecast: dict | None,
            anomalies: list[dict] | None, assumptions: list[str]) -> dict:
    if not rows:
        return {"narrative": "The query returned no rows for this question.",
                "confidence": "LOW"}

    enc = chart_spec.get("encodings", {})
    ctype = chart_spec.get("type")
    sentences: list[str] = []

    if ctype == "kpi":
        col = enc.get("value") or columns[0]
        sentences.append(f"{col.replace('_', ' ').capitalize()} is "
                         f"{_fmt(rows[0][col])}.")

    elif ctype in ("bar", "grouped_bar"):
        x = enc.get("x"); y = enc.get("y")
        y = y[0] if isinstance(y, list) else y
        top = rows[0]
        total = sum(r[y] for r in rows if isinstance(r.get(y), (int, float)))
        share = (top[y] / total * 100) if total else 0
        sentences.append(f"{_fmt(top[x])} leads with {_fmt(top[y])} "
                         f"({share:.0f}% of the top {len(rows)}).")
        if len(rows) >= 2:
            sentences.append(f"{_fmt(rows[1][x])} follows at {_fmt(rows[1][y])}.")

    elif ctype == "line":
        x = enc.get("x"); y = enc.get("y")
        # Prefer the forecaster's trimmed (complete-period) series so partial
        # boundary months don't produce a misleading "declined 100%" reading.
        if forecast and forecast.get("history_values"):
            xs = forecast["history_periods"]; ys = forecast["history_values"]
            fx0, fy0, fx1, fy1 = xs[0], ys[0], xs[-1], ys[-1]
        else:
            fx0, fy0 = rows[0].get(x), rows[0].get(y)
            fx1, fy1 = rows[-1].get(x), rows[-1].get(y)
        if isinstance(fy0, (int, float)) and fy0:
            delta = (fy1 - fy0) / abs(fy0) * 100
            direction = "grew" if delta >= 0 else "declined"
            sentences.append(f"{y.replace('_', ' ').capitalize()} {direction} "
                             f"{abs(delta):.0f}% from {fx0} ({_fmt(fy0)}) "
                             f"to {fx1} ({_fmt(fy1)}).")
        if forecast and forecast.get("point"):
            p0 = forecast["point"][0]
            sentences.append(f"The {forecast['method']} forecast projects "
                             f"{_fmt(p0)} next period "
                             f"(95% band {_fmt(forecast['lower'][0])}"
                             f"–{_fmt(forecast['upper'][0])}).")
    else:
        sentences.append(f"Returned {len(rows)} rows across "
                         f"{len(columns)} columns.")

    if anomalies:
        worst = max(anomalies, key=lambda a: a.get("score", 0))
        sentences.append(f"{len(anomalies)} anomaly point(s) flagged; the most "
                         f"extreme is value {_fmt(worst['value'])} "
                         f"({worst.get('direction', 'outlier')}).")

    confidence = _confidence(rows, assumptions, anomalies)
    narrative = " ".join(sentences)

    # Optional LLM polish would go here (get_llm().complete(...)) — figures are
    # already fixed, so the model may only rephrase, never recompute.
    return {"narrative": narrative, "confidence": confidence}
