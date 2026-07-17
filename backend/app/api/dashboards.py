"""Dashboards — create, pin query results, load (re-runs pinned queries live)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.graph import run_analysis_collect
from app.api.deps import resolve_connection_url
from app.api.schemas import DashboardRequest, PinRequest
from app.db.app_store import get_store

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.post("")
def create_dashboard(req: DashboardRequest):
    return get_store().create_dashboard(req.name)


@router.get("")
def list_dashboards():
    return {"dashboards": get_store().list_dashboards()}


@router.post("/{dashboard_id}/pin")
def pin(dashboard_id: str, req: PinRequest):
    store = get_store()
    if not store.get_query(req.query_id):
        raise HTTPException(404, "unknown query_id")
    return store.pin_to_dashboard(dashboard_id, req.query_id, req.position)


@router.get("/{dashboard_id}")
def load_dashboard(dashboard_id: str, live: bool = True):
    store = get_store()
    dash = store.get_dashboard(dashboard_id)
    if not dash:
        raise HTTPException(404, "unknown dashboard")
    # Re-run each pinned query against live data (dashboards reflect current data).
    for item in dash["items"]:
        q = store.get_query(item["query_id"])
        if not q:
            continue
        if live:
            url = resolve_connection_url(q["connection_id"])
            item["result"] = run_analysis_collect(
                q["question"], connection_id=q["connection_id"],
                connection_url=url, persist=False)
        else:
            item["result"] = q.get("payload")
    return dash
