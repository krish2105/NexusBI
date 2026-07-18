"""Forecasting default-path tests — MUST run WITHOUT torch.

These guard the zero-key default: daily/monthly label handling, seasonality
inference, and the guarantee that requesting the LSTM backend degrades gracefully
to the classical engine when the LSTM abstains or torch is not installed. No torch
import here, so these run on default CI (which does not install requirements-ml.txt).
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.ml.forecasting import (
    _next_period_labels,
    _seasonal_periods,
    forecast_series,
)


def _daily(n: int, start: str = "2021-01-04"):
    d0 = date.fromisoformat(start)
    labels, values = [], []
    for i in range(n):
        d = d0 + timedelta(days=i)
        weekly = 300 * math.sin(2 * math.pi * d.weekday() / 7)
        labels.append(d.isoformat())
        values.append(max(0.0, 1000 + 5 * i + weekly + 40 * math.sin(i * 1.3)))
    return labels, values


def test_daily_label_increment():
    assert _next_period_labels("2021-01-30", 3) == ["2021-01-31", "2021-02-01",
                                                    "2021-02-02"]
    # crosses a year boundary correctly
    assert _next_period_labels("2021-12-31", 1) == ["2022-01-01"]


def test_monthly_label_increment_unchanged():
    assert _next_period_labels("2018-11", 2) == ["2018-12", "2019-01"]


def test_seasonal_period_inference():
    assert _seasonal_periods(["2021-01-01", "2021-01-02"]) == 7   # daily → weekly
    assert _seasonal_periods(["2021-01", "2021-02"]) == 12        # monthly
    assert _seasonal_periods(["a", "b"]) == 1                     # unknown → none


def test_classical_daily_uses_weekly_seasonality():
    """A daily series should reach a Holt-Winters (or OLS) forecast with future
    daily labels — the classical path handles the new grain without torch."""
    labels, values = _daily(120)
    fc = forecast_series(labels, values, horizon=7, backend="holtwinters")
    assert fc is not None
    assert len(fc.point) == 7
    assert fc.periods[0] > labels[-1]           # next calendar day


def test_lstm_backend_falls_back_when_engine_abstains(monkeypatch):
    """backend='lstm' but the engine returns None → classical forecast, never a
    crash. forecast_series imports lstm_forecast at call time, so this holds even
    on a torch-free machine."""
    monkeypatch.setattr("app.ml.lstm_forecast.lstm_forecast", lambda *a, **k: None)
    labels, values = _daily(120)
    fc = forecast_series(labels, values, horizon=7, min_points=6, backend="lstm")
    assert fc is not None
    assert "LSTM" not in fc.method              # fell back to the classical engine


def test_default_backend_never_imports_torch(monkeypatch):
    """The default path must not even attempt to load the LSTM module."""
    called = {"lstm": False}

    def _boom(*a, **k):
        called["lstm"] = True
        raise AssertionError("default path must not touch the LSTM engine")

    monkeypatch.setattr("app.ml.lstm_forecast.lstm_forecast", _boom)
    labels, values = _daily(120)
    fc = forecast_series(labels, values, horizon=7)   # backend defaults to holtwinters
    assert fc is not None and not called["lstm"]
