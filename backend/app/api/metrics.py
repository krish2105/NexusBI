"""Semantic layer API — governed, certified metric definitions.

A metric maps a business name (+ synonyms) to a canonical SQL expression on a base
table. Nexus computes governed metrics from these definitions instead of guessing,
so answers hit certified numbers. Every definition is **safety-verified on write**:
the expression is compiled into a probe query, run through the same five-layer guard
that gates every user query, and dry-run EXPLAINed — so you cannot define a metric
that is unsafe, references a table/column that doesn't exist, or won't execute.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.semantic import seed_demo_metrics
from app.api.deps import (authorize_connection, get_current_user,
                          resolve_connection_url)
from app.db.app_store import get_store
from app.db.introspect import cached_allow_list
from app.db.target_pool import ReadOnlyExecutionError, TargetPool
from app.sqlsafety.guard import validate_sql

router = APIRouter(tags=["semantic-layer"])


class MetricRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    expression: str = Field(..., min_length=1, max_length=1000)
    base_table: str = Field(..., min_length=1, max_length=120)
    alias: str = Field(..., min_length=1, max_length=120)
    synonyms: list[str] = []
    description: str | None = None
    certified: bool = False


class MetricPatch(BaseModel):
    name: str | None = None
    expression: str | None = None
    base_table: str | None = None
    alias: str | None = None
    synonyms: list[str] | None = None
    description: str | None = None
    certified: bool | None = None


def _verify_definition(connection_id: str, expression: str, base_table: str,
                       alias: str) -> None:
    """Compile the metric into a probe query and run it through the full safety
    gate + a dry-run EXPLAIN. Raises HTTP 400 with the failing rule if unsafe /
    invalid — so a bad definition can never be saved."""
    probe = f"SELECT {expression} AS {alias}\nFROM {base_table}\nLIMIT 1"
    url = resolve_connection_url(connection_id)
    allow = cached_allow_list(url)
    pool = TargetPool(url=url)
    report = validate_sql(probe, allow, source_dialect="postgres",
                          target_dialect=pool.sqlglot_dialect)
    if not report.allowed:
        raise HTTPException(400, {"error": "unsafe_or_invalid_metric",
                                  "layer": report.layer, "reasons": report.errors})
    try:
        pool.explain(report.safe_sql)
    except ReadOnlyExecutionError as e:
        raise HTTPException(400, {"error": "metric_failed_dry_run", "detail": str(e)})


@router.get("/metrics")
def list_metrics(connection_id: str = "demo",
                 user: dict | None = Depends(get_current_user)):
    authorize_connection(connection_id, user)
    store = get_store()
    if connection_id == "demo":
        seed_demo_metrics(store, connection_id)  # populate the demo on first view
    return {"connection_id": connection_id, "metrics": store.list_metrics(connection_id)}


@router.post("/metrics")
def create_metric(req: MetricRequest, connection_id: str = "demo",
                  user: dict | None = Depends(get_current_user)):
    authorize_connection(connection_id, user)
    _verify_definition(connection_id, req.expression, req.base_table, req.alias)
    store = get_store()
    m = store.create_metric(connection_id, name=req.name, expression=req.expression,
                            base_table=req.base_table, alias=req.alias,
                            synonyms=req.synonyms, description=req.description,
                            certified=req.certified)
    store.append_audit("metric.created", actor=connection_id, verdict="ALLOW",
                       detail={"name": req.name, "certified": req.certified})
    return m


@router.patch("/metrics/{metric_id}")
def update_metric(metric_id: str, req: MetricPatch, connection_id: str = "demo",
                  user: dict | None = Depends(get_current_user)):
    authorize_connection(connection_id, user)
    store = get_store()
    existing = store.get_metric(metric_id)
    if not existing or existing["connection_id"] != connection_id:
        raise HTTPException(404, "unknown metric")
    # Re-verify whenever the definition (expression/base/alias) changes.
    expr = req.expression or existing["expression"]
    base = req.base_table or existing["base_table"]
    alias = req.alias or existing["alias"]
    if (req.expression is not None or req.base_table is not None
            or req.alias is not None):
        _verify_definition(connection_id, expr, base, alias)
    m = store.update_metric(metric_id, **req.model_dump(exclude_none=True))
    store.append_audit("metric.updated", actor=connection_id, verdict="ALLOW",
                       detail={"id": metric_id})
    return m


@router.delete("/metrics/{metric_id}")
def delete_metric(metric_id: str, connection_id: str = "demo",
                  user: dict | None = Depends(get_current_user)):
    authorize_connection(connection_id, user)
    store = get_store()
    existing = store.get_metric(metric_id)
    if not existing or existing["connection_id"] != connection_id:
        raise HTTPException(404, "unknown metric")
    store.delete_metric(metric_id)
    store.append_audit("metric.deleted", actor=connection_id, verdict="ALLOW",
                       detail={"id": metric_id})
    return {"deleted": metric_id}
