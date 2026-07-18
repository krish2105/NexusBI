# Forecasting — classical default + optional PyTorch LSTM

Nexus forecasts a time series with point predictions **and** 95% confidence
bands. The engine is deterministic — the LLM is never in this path, so the
numbers are reproducible — and it ships in two tiers:

| Engine | Default? | Dependency | Where it shines |
|---|---|---|---|
| **Holt-Winters** (statsmodels) + OLS-trend fallback | ✅ yes | none (zero-key) | any series; the free-tier path |
| **LSTM** (PyTorch, direct multi-step) | opt-in | `requirements-ml.txt` | long series with enough history |

Both return the identical `Forecast` object (`point[]`, `lower[]`, `upper[]`,
`periods[]`, …), so the API, the workspace chart, and the daily briefing don't
care which engine produced a forecast.

## Turning on the LSTM

```bash
cd backend
pip install -r requirements-ml.txt        # CPU-only torch, a few hundred MB
FORECAST_BACKEND=lstm uvicorn app.main:app --reload
```

`FORECAST_BACKEND` values: `holtwinters` (default — never imports torch),
`lstm` (use the LSTM, fall back to Holt-Winters if it abstains), `auto` (same as
`lstm` but intended for "use it when torch is present"). Every LSTM hyperparameter
is a `LSTM_*` env var (see `app/config.py`).

The LSTM **abstains** (→ Holt-Winters) when torch is absent, the series is shorter
than `LSTM_MIN_POINTS`, too few training windows can be formed, the series is
near-constant, or training diverges. It never returns a non-deterministic or
non-finite forecast — worst case you get the classical forecast.

## How the LSTM works

- **Direct multi-step (MIMO) head** — one forward pass emits all H steps, so
  there's no recursive error accumulation on noisy data.
- **`log1p` + z-score**, fit on the passed series only (no leakage). Inverting
  through `expm1` keeps forecasts non-negative and the band asymmetric for revenue.
- **Cyclical calendar features** (sin/cos of the weekly or monthly phase) so the
  net is sample-efficient instead of rediscovering seasonality.
- **Per-horizon residual-sigma band** — the MIMO head predicts every step, so the
  95% band uses the RMS residual at each horizon (monotone via cummax), in the
  same `z·sigma` idiom as Holt-Winters, so the two engines' bands are comparable.
- **Deterministic** — python/numpy/torch seeded, pinned to CPU (MPS/CUDA aren't
  bit-reproducible), single-threaded, fixed epochs, full-batch (no shuffle).
  Global torch state is mutated under a lock and restored, so concurrent API
  requests are unaffected. Repeated identical inputs are cached.

## Measured — head-to-head, not asserted

`python -m evals.run_evals` runs a **rolling-origin (walk-forward) backtest** on
two grains of the same metric (merchandise revenue) — the honest way to compare
models on limited data: each engine is refit at several non-overlapping origins
and its errors are **pooled**, so a single lucky split can't decide the winner.
Three engines compete, and a model must beat the **seasonal-naive reference** to
matter. `forecast_report.json` records RMSE/MAE, a zero-day-masked MAPE (the daily
series has zero-revenue days), and **empirical 95% band coverage** so "95%" is
audited, not claimed.

Representative result on the bundled Olist demo (torch installed):

| Series | Folds | seasonal-naive RMSE | Holt-Winters RMSE | LSTM RMSE | 95% band coverage (HW / LSTM) |
|---|---|---|---|---|---|
| **Daily** (~700 pts) | 6 × 14 | 11,101 | 10,187 | **9,749** | 100% / **94%** |
| **Monthly** (~24 pts) | up to 3 × 3 | 413,967 | 167,295 | 127,855¹ | 67% / 67% |

¹ The monthly LSTM clears the data floor on only the longest fold, so its number
is **indicative, not robust** (reported as `folds: 1`). The report says so.

**The honest takeaway:** on the ~700-point daily series the LSTM is both more
accurate (lower RMSE than Holt-Winters and seasonal-naive) *and* better
calibrated — ~94% band coverage (≈ the nominal 95%) at roughly half the band
width of Holt-Winters (which is over-wide at 100% coverage). On the ~24-point
monthly series there simply isn't enough history for a sequence model to earn a
robust win — classical methods and their structural prior are the right tool.
Deep learning pays off exactly when there's data to learn from; the benchmark
proves it rather than assuming it.

## Why it's off by default

`torch` is ~a few hundred MB and overkill for short business series, so the
free-tier Docker image and default CI stay torch-free. The LSTM is a genuine
showcase of the deep-learning path (and reproducible enough to gate on), but the
zero-key Holt-Winters engine remains the default everywhere.
