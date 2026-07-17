"""Anomaly detection node.

  * Time series (date + numeric)  -> STL residual thresholding (statsmodels) or a
    rolling z-score fallback.
  * Cross-section (single metric) -> IsolationForest (scikit-learn) or an IQR
    fallback, so anomalies work even on a minimal install.

Returns flagged indices with a severity score so the frontend can mark points.
"""
from __future__ import annotations


def _zscore_anomalies(values: list[float], z_thresh: float = 2.5) -> list[dict]:
    n = len(values)
    if n < 4:
        return []
    mean = sum(values) / n
    std = (sum((v - mean) ** 2 for v in values) / n) ** 0.5 or 1e-9
    out = []
    for i, v in enumerate(values):
        z = (v - mean) / std
        if abs(z) >= z_thresh:
            out.append({"index": i, "value": round(v, 2), "score": round(abs(z), 2),
                        "direction": "high" if z > 0 else "low"})
    return out


def _stl_anomalies(values: list[float], period: int) -> list[dict] | None:
    try:
        from statsmodels.tsa.seasonal import STL  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    if len(values) < 2 * period:
        return None
    res = STL(values, period=period, robust=True).fit()
    resid = list(res.resid)
    n = len(resid)
    mean = sum(resid) / n
    std = (sum((r - mean) ** 2 for r in resid) / n) ** 0.5 or 1e-9
    out = []
    for i, r in enumerate(resid):
        z = (r - mean) / std
        if abs(z) >= 2.5:
            out.append({"index": i, "value": round(values[i], 2),
                        "score": round(abs(z), 2),
                        "direction": "high" if z > 0 else "low"})
    return out


def _iforest_anomalies(values: list[float]) -> list[dict] | None:
    try:
        from sklearn.ensemble import IsolationForest  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    if len(values) < 8:
        return None
    X = [[v] for v in values]
    model = IsolationForest(contamination="auto", random_state=42)
    preds = model.fit_predict(X)
    scores = model.score_samples(X)
    out = []
    for i, p in enumerate(preds):
        if p == -1:
            out.append({"index": i, "value": round(values[i], 2),
                        "score": round(float(-scores[i]), 3), "direction": "outlier"})
    return out


def detect_anomalies(columns: list[str], rows: list[dict], chart_spec: dict) -> list[dict]:
    enc = chart_spec.get("encodings", {})
    ctype = chart_spec.get("type")
    ycol = enc.get("y") or enc.get("value")
    if not ycol or not rows or ycol not in rows[0]:
        return []
    values = [r[ycol] for r in rows if isinstance(r.get(ycol), (int, float))
              and not isinstance(r.get(ycol), bool)]
    if len(values) < 4:
        return []

    if ctype == "line":
        stl = _stl_anomalies(values, period=12)
        return stl if stl is not None else _zscore_anomalies(values)

    iso = _iforest_anomalies(values)
    return iso if iso is not None else _zscore_anomalies(values)
