"""Optional PyTorch LSTM forecaster — the deep-learning variant behind a flag.

This is the stretch model: a windowed LSTM that forecasts a whole horizon in one
shot (direct multi-step / MIMO — no recursive error accumulation), returning the
**same** ``Forecast`` dataclass as the classical path so nothing downstream
changes. It is opt-in (``FORECAST_BACKEND=lstm``) and depends on ``torch`` from
``requirements-ml.txt``; when torch is absent, the series is too short, or
training diverges, it returns ``None`` and ``forecast_series`` falls back to
Holt-Winters. Nothing about the default zero-key path touches this file.

Design choices that matter:
  * **log1p + z-score, fit on the passed series only** — no leakage (the eval
    strips the holdout before calling), and inverse-transforming through
    ``expm1`` keeps forecasts non-negative and the band asymmetric for revenue.
  * **Cyclical calendar features** (sin/cos of the weekly or monthly phase) so the
    net is sample-efficient and doesn't have to rediscover seasonality.
  * **Per-horizon residual-sigma 95% band** — the MIMO head predicts every step,
    so the band uses the RMS residual at *each* horizon (monotone via cummax),
    staying in the Holt-Winters ``z·sigma`` idiom so the two engines compare.
  * **Determinism** — python/numpy/torch seeded, pinned to CPU (MPS/CUDA aren't
    bit-reproducible), single-threaded, fixed epochs, full-batch (no shuffle).
    Global torch state is mutated under a lock and restored in ``finally`` so a
    concurrent API request is never affected. A given series → the same forecast,
    so the eval report and CI gate stay reproducible.
"""
from __future__ import annotations

import dataclasses
import math
import threading
from collections import OrderedDict
from datetime import date

from app.ml.forecasting import Forecast, _r

_YMD_LEN = 10  # len("YYYY-MM-DD")

# torch's thread count + deterministic-mode + global RNG are process-global; a fit
# mutates them, so fits are serialized and the previous state restored afterwards.
_FIT_LOCK = threading.Lock()

# Small bounded cache: determinism means identical inputs → identical output, so a
# repeated query needn't retrain. Copies are stored/returned so a caller mutating
# ``notes`` (forecast_series inserts a trim note) can't corrupt the cache.
_CACHE: "OrderedDict[tuple, Forecast]" = OrderedDict()
_CACHE_MAX = 32


def _phase(label: str, period: int) -> float:
    """Seasonal phase in [0, period): weekday for daily, month for monthly, else 0."""
    s = str(label)
    if period == 7 and len(s) == _YMD_LEN:
        try:
            return float(date.fromisoformat(s).weekday())
        except ValueError:
            return 0.0
    if period == 12 and len(s) >= 7:
        try:
            return float(int(s[5:7]) - 1)
        except ValueError:
            return 0.0
    return 0.0


def _copy_fc(fc: Forecast) -> Forecast:
    """Independent copy so cache entries and returned objects never alias."""
    return dataclasses.replace(
        fc, periods=list(fc.periods), point=list(fc.point), lower=list(fc.lower),
        upper=list(fc.upper), history_periods=list(fc.history_periods),
        history_values=list(fc.history_values), notes=list(fc.notes))


def _config_key() -> tuple:
    from app.config import settings

    return (settings.lstm_lookback, settings.lstm_hidden_size, settings.lstm_epochs,
            settings.lstm_lr, settings.lstm_weight_decay, settings.lstm_dropout,
            settings.lstm_seed, settings.lstm_z, settings.lstm_min_points,
            settings.lstm_min_windows)


def lstm_forecast(labels: list[str], values: list[float], horizon: int,
                  fut_labels: list[str], seasonal: int) -> Forecast | None:
    """Train an LSTM on ``values`` and forecast ``horizon`` steps, or ``None``.

    Returns ``None`` (→ classical fallback) when torch is unavailable, the series
    is too short to form enough training windows, the series is ~constant, or
    training/forecast produces non-finite output. Never raises.
    """
    key = (tuple(labels), tuple(values), horizon, tuple(fut_labels), seasonal,
           _config_key())
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return _copy_fc(hit)

    fc = _fit_and_forecast(labels, values, horizon, fut_labels, seasonal)
    if fc is not None:
        _CACHE[key] = _copy_fc(fc)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return fc


def _fit_and_forecast(labels, values, horizon, fut_labels, seasonal
                      ) -> Forecast | None:
    try:
        import numpy as np
        import torch
        import torch.nn as nn
    except Exception:  # noqa: BLE001 - torch not installed
        return None

    from app.config import settings

    n = len(values)
    if n < settings.lstm_min_points:
        return None
    if max(values) - min(values) < 1e-9:  # near-constant: classical handles it
        return None

    # Adaptive lookback: the configured window, capped so a short series (e.g. the
    # ~24-point monthly one) can still form enough training windows. Seasonality is
    # carried by the cyclical calendar features, so the lookback need not span a
    # full cycle — which lets the LSTM also run on the short monthly series.
    lookback = max(2, min(settings.lstm_lookback, n // 3))
    n_windows = n - lookback - horizon + 1
    if n_windows < settings.lstm_min_windows:
        return None

    period = seasonal if seasonal >= 2 else 1

    # Build features outside the lock (pure numpy, no torch global state).
    y = np.asarray(values, dtype=np.float64)
    y_log = np.log1p(np.clip(y, 0.0, None))
    mu = float(y_log.mean())
    sigma = float(y_log.std()) or 1.0
    y_scaled = (y_log - mu) / sigma
    phases = np.array([_phase(lbl, period) for lbl in labels], dtype=np.float64)
    if period >= 2:
        sin_feat = np.sin(2 * math.pi * phases / period)
        cos_feat = np.cos(2 * math.pi * phases / period)
    else:
        sin_feat = np.zeros(n)
        cos_feat = np.zeros(n)
    feats = np.stack([y_scaled, sin_feat, cos_feat], axis=1)  # (n, 3)
    input_size = feats.shape[1]

    Xs, Ys = [], []
    for t in range(n_windows):
        Xs.append(feats[t:t + lookback])
        Ys.append(y_scaled[t + lookback:t + lookback + horizon])

    def _inv(scaled):
        return np.clip(np.expm1(scaled * sigma + mu), 0.0, None)

    # torch global state (threads, deterministic mode, RNG) is mutated here; hold
    # the lock and restore prior state so concurrent requests are unaffected.
    with _FIT_LOCK:
        prev_threads = torch.get_num_threads()
        try:
            import random as _random

            seed = settings.lstm_seed
            _random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            torch.set_num_threads(1)
            try:
                torch.use_deterministic_algorithms(True)
            except Exception:  # noqa: BLE001 - CPU LSTM is deterministic regardless
                pass
            device = torch.device("cpu")  # never MPS/CUDA — not bit-reproducible

            X_t = torch.tensor(np.asarray(Xs), dtype=torch.float32, device=device)
            Y_t = torch.tensor(np.asarray(Ys), dtype=torch.float32, device=device)

            class _Net(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.lstm = nn.LSTM(input_size, settings.lstm_hidden_size,
                                        num_layers=1, batch_first=True)
                    self.drop = nn.Dropout(settings.lstm_dropout)
                    self.head = nn.Linear(settings.lstm_hidden_size, horizon)

                def forward(self, x):
                    _, (h, _c) = self.lstm(x)
                    return self.head(self.drop(h[-1]))

            model = _Net().to(device)
            opt = torch.optim.Adam(model.parameters(), lr=settings.lstm_lr,
                                   weight_decay=settings.lstm_weight_decay)
            loss_fn = nn.SmoothL1Loss()  # robust to daily revenue spikes

            model.train()
            for _ in range(settings.lstm_epochs):  # fixed epochs, full-batch → deterministic
                opt.zero_grad()
                loss = loss_fn(model(X_t), Y_t)
                if not torch.isfinite(loss):
                    return None
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), settings.lstm_grad_clip)
                opt.step()

            model.eval()
            with torch.no_grad():
                last_win = torch.tensor(feats[n - lookback:n][None, :, :],
                                        dtype=torch.float32, device=device)
                pred_scaled = model(last_win).cpu().numpy().ravel()[:horizon]
                fitted = model(X_t).cpu().numpy()  # (n_windows, horizon), scaled
        finally:
            torch.set_num_threads(prev_threads)
            try:
                torch.use_deterministic_algorithms(False)
            except Exception:  # noqa: BLE001
                pass

    point = _inv(pred_scaled)
    if not np.all(np.isfinite(point)):
        return None

    # Per-horizon residual sigma (original units): the MIMO head predicts every
    # step, so estimate the band at each horizon directly, then cummax so it never
    # shrinks with lead time. Same z·sigma / clamp-at-0 idiom as Holt-Winters.
    resid_h = _inv(Y_t.cpu().numpy()) - _inv(fitted)     # (n_windows, horizon)
    sigma_h = np.sqrt((resid_h ** 2).mean(axis=0))       # (horizon,)
    sigma_h = np.maximum.accumulate(sigma_h)
    z = settings.lstm_z
    lower = [max(0.0, float(p) - z * float(s)) for p, s in zip(point, sigma_h)]
    upper = [float(p) + z * float(s) for p, s in zip(point, sigma_h)]

    mean_sigma = float(sigma_h.mean())
    return Forecast(
        method=f"LSTM (PyTorch, 1x{settings.lstm_hidden_size}, lookback={lookback})",
        horizon=horizon, periods=fut_labels, point=_r([float(p) for p in point]),
        lower=_r(lower), upper=_r(upper),
        history_periods=[str(x) for x in labels], history_values=_r(list(values)),
        notes=[f"Direct {horizon}-step MIMO LSTM on {n_windows} windows "
               f"(lookback={lookback}); 95% band from per-horizon residual "
               f"sigma (mean={mean_sigma:,.1f}, monotone)."])
