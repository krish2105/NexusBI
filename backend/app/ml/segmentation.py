"""RFM customer segmentation (real ML, deterministic).

Recency / Frequency / Monetary quintile scoring on the customer feature table,
then a standard RFM segment matrix (Champions, Loyal, At Risk, Hibernating, …).
The LLM is not involved — this is quantitative reasoning, so the segments are
reproducible.

Works on the demo's ``customer_features`` (and any table exposing recency,
frequency, and monetary-like columns).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.db.target_pool import TargetPool

# Column resolution: (role -> candidate column names, lower is better?)
_RECENCY = ["recency_days_at_dataset_end", "recency_days", "recency"]
_FREQUENCY = ["order_count", "frequency", "orders", "purchase_count"]
_MONETARY = ["merchandise_value", "monetary", "gross_order_value", "payment_value",
             "total_spend", "revenue"]


@dataclass
class SegmentResult:
    available: bool
    reason: str = ""
    total_customers: int = 0
    segments: list[dict] = None            # [{segment, count, pct, avg_r, avg_f, avg_m}]
    scatter: list[dict] = None             # sampled points for a viz
    columns_used: dict | None = None

    def to_dict(self) -> dict:
        return {
            "available": self.available, "reason": self.reason,
            "total_customers": self.total_customers,
            "segments": self.segments or [], "scatter": self.scatter or [],
            "columns_used": self.columns_used or {},
        }


def _pick(cols: set[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None


def _score_quintile(series: pd.Series, ascending: bool) -> pd.Series:
    """1..5 quintile score. ascending=True means higher raw value -> higher score."""
    ranked = series.rank(method="first")
    try:
        q = pd.qcut(ranked, 5, labels=[1, 2, 3, 4, 5])
    except ValueError:
        # too few distinct values -> coarse binning
        q = pd.cut(ranked, 5, labels=[1, 2, 3, 4, 5])
    q = q.astype(int)
    return q if ascending else (6 - q)


def _label(r: int, f: int, m: int) -> str:
    fm = (f + m) / 2
    if r >= 4 and fm >= 4:
        return "Champions"
    if r >= 3 and fm >= 3:
        return "Loyal"
    if r >= 4 and fm <= 2:
        return "New / Promising"
    if r == 3 and fm <= 2:
        return "Potential Loyalist"
    if r <= 2 and fm >= 4:
        return "Can't Lose"
    if r <= 2 and fm >= 3:
        return "At Risk"
    if r <= 2 and fm == 2:
        return "Hibernating"
    return "Lost"


SEGMENT_ORDER = ["Champions", "Loyal", "Potential Loyalist", "New / Promising",
                 "At Risk", "Can't Lose", "Hibernating", "Lost"]


def segment_customers(url: str | None = None, table: str = "customer_features",
                      sample: int = 600) -> SegmentResult:
    # Segmentation reads the full customer base (not the interactive 10k row cap).
    pool = TargetPool(url=url, row_cap=500_000)
    if table not in {t.lower() for t in pool.list_tables()}:
        return SegmentResult(False, f"no '{table}' table on this connection")

    cols = {c.lower() for c, _ in pool.table_columns(table)}
    rc = _pick(cols, _RECENCY)
    fc = _pick(cols, _FREQUENCY)
    mc = _pick(cols, _MONETARY)
    if not (rc and fc and mc):
        return SegmentResult(False, "table lacks recency/frequency/monetary columns")

    res = pool.execute(
        f'SELECT "{rc}" AS r, "{fc}" AS f, "{mc}" AS m FROM "{table}" '
        f'WHERE "{rc}" IS NOT NULL AND "{fc}" IS NOT NULL AND "{mc}" IS NOT NULL '
        f'LIMIT 200000')
    df = pd.DataFrame(res.rows)
    if df.empty:
        return SegmentResult(False, "no rows to segment")

    df["R"] = _score_quintile(df["r"], ascending=False)  # lower recency = better
    df["F"] = _score_quintile(df["f"], ascending=True)
    df["M"] = _score_quintile(df["m"], ascending=True)
    df["segment"] = [_label(r, f, m) for r, f, m in zip(df["R"], df["F"], df["M"])]

    total = len(df)
    grouped = df.groupby("segment")
    segments = []
    for seg, g in grouped:
        segments.append({
            "segment": seg, "count": int(len(g)),
            "pct": round(len(g) / total * 100, 1),
            "avg_recency_days": round(float(g["r"].mean()), 1),
            "avg_frequency": round(float(g["f"].mean()), 2),
            "avg_monetary": round(float(g["m"].mean()), 2),
        })
    segments.sort(key=lambda s: (SEGMENT_ORDER.index(s["segment"])
                                 if s["segment"] in SEGMENT_ORDER else 99))

    # Sampled scatter (frequency vs monetary, coloured by segment) for the viz.
    samp = df.sample(min(sample, total), random_state=42)
    scatter = [{"f": float(row.f), "m": round(float(row.m), 2), "segment": row.segment}
               for row in samp.itertuples()]

    return SegmentResult(
        True, "", total_customers=total, segments=segments, scatter=scatter,
        columns_used={"recency": rc, "frequency": fc, "monetary": mc},
    )
