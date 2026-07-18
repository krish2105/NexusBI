"""LSTM forecaster engine tests — torch-guarded.

The whole module is skipped when torch is absent (default CI does not install
requirements-ml.txt). The torch-free default-path guarantees live in
``test_forecasting.py`` so they run without torch.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.ml.forecasting import Forecast, _next_period_labels, forecast_series

torch = pytest.importorskip("torch")  # skip the whole module without torch

from app.ml.lstm_forecast import _CACHE, lstm_forecast  # noqa: E402


def _daily(n: int, start: str = "2021-01-04"):
    """Synthetic daily revenue: trend + weekly cycle + mild deterministic noise."""
    d0 = date.fromisoformat(start)
    labels, values = [], []
    for i in range(n):
        d = d0 + timedelta(days=i)
        base = 1000 + 5 * i                      # trend
        weekly = 300 * math.sin(2 * math.pi * d.weekday() / 7)
        noise = 40 * math.sin(i * 1.3)           # deterministic
        labels.append(d.isoformat())
        values.append(max(0.0, base + weekly + noise))
    return labels, values


@pytest.fixture(autouse=True)
def _clear_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


def test_lstm_shape_and_non_negativity():
    labels, values = _daily(220)
    fut = _next_period_labels(labels[-1], 14)
    fc = lstm_forecast(labels, values, 14, fut, 7)
    assert isinstance(fc, Forecast)
    assert fc.method.startswith("LSTM")
    assert len(fc.point) == len(fc.lower) == len(fc.upper) == len(fc.periods) == 14
    assert all(p >= 0 for p in fc.point)
    assert all(lo <= p <= up for lo, p, up in zip(fc.lower, fc.point, fc.upper))
    assert fc.periods[0] == labels[-1][:8] + f"{int(labels[-1][8:]) + 1:02d}" \
        or fc.periods[0] > labels[-1]          # next calendar day


def test_lstm_band_sigma_is_monotone():
    """The (unclamped) upper band minus point = z·sigma_h must be non-decreasing —
    the per-horizon sigma is cummax'd so uncertainty never shrinks with lead time."""
    labels, values = _daily(220)
    fut = _next_period_labels(labels[-1], 14)
    fc = lstm_forecast(labels, values, 14, fut, 7)
    half = [u - p for u, p in zip(fc.upper, fc.point)]   # = z·sigma_h, unclamped
    # Tolerance absorbs 2-dp rounding of point/upper (each rounded independently);
    # a removed cummax would shrink the band by orders of magnitude more.
    assert all(half[i] <= half[i + 1] + 0.02 for i in range(len(half) - 1))


def test_lstm_is_deterministic():
    labels, values = _daily(200)
    fut = _next_period_labels(labels[-1], 10)
    _CACHE.clear()
    a = lstm_forecast(labels, values, 10, fut, 7)
    _CACHE.clear()                                        # force a real re-train
    b = lstm_forecast(labels, values, 10, fut, 7)
    assert (a.point, a.lower, a.upper) == (b.point, b.lower, b.upper)


def test_lstm_restores_global_thread_state():
    before = torch.get_num_threads()
    labels, values = _daily(200)
    fut = _next_period_labels(labels[-1], 7)
    lstm_forecast(labels, values, 7, fut, 7)
    assert torch.get_num_threads() == before             # not left single-threaded


def test_lstm_cache_returns_independent_copy():
    labels, values = _daily(200)
    fut = _next_period_labels(labels[-1], 7)
    a = lstm_forecast(labels, values, 7, fut, 7)          # trains + caches
    a.notes.append("mutated by caller")
    b = lstm_forecast(labels, values, 7, fut, 7)          # cache hit
    assert "mutated by caller" not in b.notes             # cache not corrupted


def test_lstm_abstains_when_too_short():
    labels, values = _daily(10)                           # < lstm_min_points
    fut = _next_period_labels(labels[-1], 3)
    assert lstm_forecast(labels, values, 3, fut, 7) is None


def test_lstm_abstains_on_constant_series():
    labels, _ = _daily(200)
    values = [500.0] * len(labels)                        # zero variance
    fut = _next_period_labels(labels[-1], 7)
    assert lstm_forecast(labels, values, 7, fut, 7) is None


def test_lstm_wired_through_forecast_series():
    labels, values = _daily(220)
    fc = forecast_series(labels, values, horizon=14, min_points=6, backend="lstm")
    assert fc is not None and "LSTM" in fc.method
