"""Forecasting node — point forecasts + confidence bands for a time series.

Uses statsmodels Holt-Winters (Exponential Smoothing) when available for a real
trend+seasonal model; otherwise a robust deterministic fallback (OLS trend +
seasonal-naive residual with a normal confidence band). The LLM is never in this
path — the numbers come from the model, so they are reproducible.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

_YM = re.compile(r"^(\d{4})-(\d{2})$")
_YMD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


@dataclass
class Forecast:
    method: str
    horizon: int
    periods: list[str]
    point: list[float]
    lower: list[float]
    upper: list[float]
    history_periods: list[str] = field(default_factory=list)
    history_values: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "method": self.method, "horizon": self.horizon,
            "periods": self.periods, "point": self.point,
            "lower": self.lower, "upper": self.upper,
            "history_periods": self.history_periods,
            "history_values": self.history_values, "notes": self.notes,
        }


def _next_period_labels(last_label: str, horizon: int) -> list[str]:
    # Daily (YYYY-MM-DD): advance by calendar days.
    md = _YMD.match(str(last_label))
    if md:
        d = date(int(md.group(1)), int(md.group(2)), int(md.group(3)))
        return [(d + timedelta(days=i + 1)).isoformat() for i in range(horizon)]
    m = _YM.match(str(last_label))
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        out = []
        for _ in range(horizon):
            mo += 1
            if mo > 12:
                mo = 1
                y += 1
            out.append(f"{y:04d}-{mo:02d}")
        return out
    # Fallback: numeric period index.
    try:
        base = int(last_label)
        return [str(base + i + 1) for i in range(horizon)]
    except (TypeError, ValueError):
        return [f"t+{i+1}" for i in range(horizon)]


def _seasonal_periods(labels: list[str]) -> int:
    """Seasonal cycle length inferred from the label format: monthly→12, daily→7
    (weekly), otherwise none. Giving the classical baseline the right seasonality
    keeps a head-to-head against the LSTM fair."""
    if labels and all(_YMD.match(str(x)) for x in labels):
        return 7
    if labels and all(_YM.match(str(x)) for x in labels):
        return 12
    return 1


def _trim_partial_periods(labels: list[str], values: list[float]) -> tuple[list, list, int]:
    """Drop contiguous partial boundary periods (real data tails off at the edges).

    A boundary period whose value is < 10% of the series median is treated as an
    incomplete period and removed from both ends only (never the interior)."""
    if len(values) < 4:
        return labels, values, 0
    ordered = sorted(values)
    median = ordered[len(ordered) // 2] or 1.0
    thresh = 0.10 * median
    lo, hi = 0, len(values) - 1
    while lo < hi and values[lo] < thresh:
        lo += 1
    while hi > lo and values[hi] < thresh:
        hi -= 1
    trimmed = (len(values) - (hi - lo + 1))
    return labels[lo:hi + 1], values[lo:hi + 1], trimmed


def forecast_series(labels: list[str], values: list[float], horizon: int = 6,
                    min_points: int = 6, backend: str | None = None) -> Forecast | None:
    """Forecast a time series with confidence bands.

    ``backend`` selects the engine — ``"holtwinters"`` (default, zero-key,
    deterministic), ``"lstm"`` (optional PyTorch variant), or ``"auto"`` (LSTM
    when torch is available and the series is long enough, else Holt-Winters).
    When ``None`` it reads ``settings.forecast_backend``. The LSTM path always
    degrades gracefully to the classical model, so the caller always gets a
    forecast when one is possible.
    """
    labels = [str(x) for x in labels]
    values = [float(v) for v in values]
    labels, values, trimmed = _trim_partial_periods(labels, values)
    if len(values) < min_points:
        return None

    if backend is None:
        try:
            from app.config import settings
            backend = settings.forecast_backend
        except Exception:  # noqa: BLE001
            backend = "holtwinters"

    fut_labels = _next_period_labels(labels[-1], horizon)
    seasonal = _seasonal_periods(labels)

    fc: Forecast | None = None
    if backend in ("lstm", "auto"):
        try:
            from app.ml.lstm_forecast import lstm_forecast

            fc = lstm_forecast(labels, values, horizon, fut_labels, seasonal)
        except Exception:  # noqa: BLE001 - torch missing / training failure
            fc = None

    if fc is None:
        fc = _classical_forecast(labels, values, horizon, fut_labels, seasonal)

    if trimmed:
        fc.notes.insert(0, f"Trimmed {trimmed} partial boundary period(s) before modeling.")
    return fc


def _classical_forecast(labels, values, horizon, fut_labels, seasonal) -> Forecast:
    """Holt-Winters with an OLS-trend fallback — the zero-key deterministic path."""
    try:
        fc = _hw_forecast(labels, values, horizon, fut_labels, seasonal)
        # Reject a degenerate collapse (the WHOLE forecast clamped to ~0). Judged
        # on the mean so a legitimately low seasonal day (e.g. a weekend in the
        # daily series) doesn't trip the guard the way a per-point test would.
        median = sorted(values)[len(values) // 2]
        mean_pt = sum(fc.point) / len(fc.point) if fc.point else 0.0
        if median > 0 and mean_pt <= 0.02 * median:
            fc = _ols_forecast(labels, values, horizon, fut_labels)
    except Exception:  # noqa: BLE001 - fall back to deterministic model
        fc = _ols_forecast(labels, values, horizon, fut_labels)
    return fc


def _hw_forecast(labels, values, horizon, fut_labels, seasonal) -> Forecast:
    import warnings

    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # type: ignore

    use_seasonal = seasonal >= 2 and len(values) >= 2 * seasonal
    model = ExponentialSmoothing(
        values, trend="add", damped_trend=True,
        seasonal="add" if use_seasonal else None,
        seasonal_periods=seasonal if use_seasonal else None,
        initialization_method="estimated")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = model.fit()
    point = [max(0.0, float(x)) for x in fit.forecast(horizon)]
    resid = [values[i] - float(fit.fittedvalues[i]) for i in range(len(values))]
    sigma = (sum(r * r for r in resid) / max(1, len(resid) - 1)) ** 0.5
    z = 1.96
    lower = [max(0.0, p - z * sigma * math.sqrt(i + 1)) for i, p in enumerate(point)]
    upper = [p + z * sigma * math.sqrt(i + 1) for i, p in enumerate(point)]
    return Forecast(
        method="Holt-Winters (add trend"
               + (", add seasonal)" if use_seasonal else ")"),
        horizon=horizon, periods=fut_labels, point=_r(point),
        lower=_r(lower), upper=_r(upper),
        history_periods=[str(x) for x in labels], history_values=_r(values),
        notes=[f"95% band from residual sigma={sigma:,.1f}"])


def _ols_forecast(labels, values, horizon, fut_labels) -> Forecast:
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in xs) or 1.0
    slope = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n)) / denom
    intercept = mean_y - slope * mean_x
    fitted = [intercept + slope * x for x in xs]
    resid = [values[i] - fitted[i] for i in range(n)]
    sigma = (sum(r * r for r in resid) / max(1, n - 2)) ** 0.5
    z = 1.96
    point, lower, upper = [], [], []
    for i in range(horizon):
        x = n + i
        p = max(0.0, intercept + slope * x)
        band = z * sigma * math.sqrt(i + 1)
        point.append(p)
        lower.append(max(0.0, p - band))
        upper.append(p + band)
    return Forecast(
        method="OLS linear trend", horizon=horizon, periods=fut_labels,
        point=_r(point), lower=_r(lower), upper=_r(upper),
        history_periods=[str(x) for x in labels], history_values=_r(values),
        notes=[f"slope={slope:,.1f}/period; 95% band sigma={sigma:,.1f}"])


def _r(xs: list[float]) -> list[float]:
    return [round(float(x), 2) for x in xs]
