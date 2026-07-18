"""Typed analysis state threaded through the agent graph."""
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict


class AnalysisState(TypedDict, total=False):
    query_id: str
    connection_id: str
    connection_url: str
    question: str

    plan: dict
    governed_metric: Optional[dict]   # certified metric used, if the question named one
    retrieved_schema: list[dict]
    schema_prompt: str

    sql: str
    sql_explanation: str
    sql_valid: bool
    safe_sql: Optional[str]
    validation_errors: list[str]
    repair_attempts: int

    result_rows: list[dict]
    result_columns: list[str]
    result_meta: dict

    chart_spec: dict
    forecast: Optional[dict]
    anomalies: Optional[list[dict]]

    narrative: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    assumptions: list[str]

    generator: str          # "deterministic" | "groq" | "ollama"
    error: Optional[str]
    blocked: bool
    events: list[dict[str, Any]]
