"""Demo revenue time series at two grains — the input to forecasting + backtests.

Both series measure the *same* metric (merchandise value) so a monthly vs daily
comparison is apples-to-apples:

  * ``monthly`` — the pre-aggregated ``monthly_kpis`` view (~24 complete points).
  * ``daily``   — merchandise value per calendar day, **calendar-reindexed** off the
    ``dates`` dimension so days with no orders are 0-filled (a gap-free series with
    weekly seasonality, ~700 points after boundary trimming).

The daily series is what makes an LSTM a genuine showcase rather than a toy: a
neural sequence model needs far more than two dozen points to earn its keep.
These helpers are demo-schema specific (Olist star) and used by the eval
head-to-head backtest and the tests.
"""
from __future__ import annotations

from app.db.target_pool import TargetPool

_MONTHLY_SQL = (
    "SELECT year_month AS label, merchandise_value AS value "
    "FROM monthly_kpis ORDER BY year_month LIMIT 10000"
)

# Calendar-reindexed daily revenue: every day in the order date-range appears,
# 0-filled when no orders fell on it, so the series has no time gaps.
_DAILY_SQL = """
WITH bounds AS (
  SELECT MIN(d.date) AS lo, MAX(d.date) AS hi
  FROM orders o JOIN dates d ON o.order_date_id = d.date_id
)
SELECT d.date AS label, COALESCE(SUM(o.merchandise_value), 0) AS value
FROM dates d
LEFT JOIN orders o ON o.order_date_id = d.date_id
WHERE d.date BETWEEN (SELECT lo FROM bounds) AND (SELECT hi FROM bounds)
GROUP BY d.date
ORDER BY d.date
LIMIT 100000
"""


def load_series(grain: str = "monthly", pool: TargetPool | None = None
                ) -> tuple[list[str], list[float]]:
    """Return ``(labels, values)`` for ``grain`` in {"monthly", "daily"}."""
    pool = pool or TargetPool()
    sql = _DAILY_SQL if grain == "daily" else _MONTHLY_SQL
    rows = pool.execute(sql).rows
    labels = [str(r["label"]) for r in rows]
    values = [float(r["value"] or 0.0) for r in rows]
    return labels, values
