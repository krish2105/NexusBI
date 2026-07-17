"""Deterministic chart selection from the result shape.

The LLM never chooses the chart or the numbers — heuristics on the result schema
do, so visualization is reproducible:

  (date + numeric)          -> line   (forecast-eligible)
  (categorical + numeric)   -> bar
  (single numeric scalar)   -> kpi
  (two numerics)            -> scatter
  (categorical + 2 numerics)-> grouped_bar
"""
from __future__ import annotations

import re
from typing import Any

_DATE_HINT = re.compile(
    r"(date|day|week|month|year|_at$|timestamp|year_month|period)", re.I)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _classify(columns: list[str], rows: list[dict]) -> dict[str, str]:
    """Return {column: 'date'|'numeric'|'categorical'}."""
    kinds: dict[str, str] = {}
    sample = rows[:50]
    for c in columns:
        vals = [r[c] for r in sample if r.get(c) is not None]
        if _DATE_HINT.search(c) and vals:
            kinds[c] = "date"
        elif vals and all(_is_number(v) for v in vals):
            kinds[c] = "numeric"
        else:
            kinds[c] = "categorical"
    return kinds


def select_chart(columns: list[str], rows: list[dict]) -> dict:
    if not columns or not rows:
        return {"type": "table", "reason": "no rows", "encodings": {}}

    kinds = _classify(columns, rows)
    dates = [c for c, k in kinds.items() if k == "date"]
    numerics = [c for c, k in kinds.items() if k == "numeric"]
    categoricals = [c for c, k in kinds.items() if k == "categorical"]

    # Single scalar -> KPI card
    if len(columns) == 1 and len(rows) == 1 and numerics:
        return {"type": "kpi", "reason": "single scalar value",
                "encodings": {"value": numerics[0]}, "forecastable": False}

    # Time series -> line (+ forecast eligible)
    if dates and numerics:
        return {"type": "line", "reason": "date + numeric time series",
                "encodings": {"x": dates[0], "y": numerics[0],
                              "series": numerics},
                "forecastable": len(rows) >= 6}

    # Categorical + one numeric -> bar
    if categoricals and len(numerics) == 1:
        return {"type": "bar", "reason": "categorical comparison",
                "encodings": {"x": categoricals[0], "y": numerics[0]},
                "forecastable": False}

    # Categorical + multiple numerics -> grouped bar
    if categoricals and len(numerics) >= 2:
        return {"type": "grouped_bar", "reason": "categorical with multiple measures",
                "encodings": {"x": categoricals[0], "y": numerics},
                "forecastable": False}

    # Two numerics -> scatter
    if len(numerics) >= 2 and not categoricals and not dates:
        return {"type": "scatter", "reason": "two numeric correlation",
                "encodings": {"x": numerics[0], "y": numerics[1]},
                "forecastable": False}

    return {"type": "table", "reason": "no clean chart mapping",
            "encodings": {}, "forecastable": False}
