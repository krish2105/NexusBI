"""Dashboards — create, generate from NL, pin, load (re-runs pinned queries)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agents.dashboard_planner import plan_dashboard
from app.agents.graph import run_analysis_collect
from app.agents.planner import plan_question
from app.api.deps import (authorize_connection, authorize_owner,
                          get_current_user, rate_limit, resolve_connection_url)
from app.api.schemas import (DashboardGenerateRequest, DashboardRequest,
                             PinRequest)
from app.config import settings
from app.db.app_store import get_store

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.post("")
def create_dashboard(req: DashboardRequest,
                     user: dict | None = Depends(get_current_user)):
    return get_store().create_dashboard(req.name,
                                        user_id=user["id"] if user else None)


@router.post("/generate", dependencies=[Depends(rate_limit)])
def generate_dashboard(req: DashboardGenerateRequest,
                       user: dict | None = Depends(get_current_user)):
    """NL → dashboard: interpret the description into a themed set of questions,
    run each through the safe pipeline, and compose a saved dashboard."""
    authorize_connection(req.connection_id, user)
    store = get_store()
    url = resolve_connection_url(req.connection_id)
    plan = plan_dashboard(req.description, url)

    dash = store.create_dashboard(plan.title,
                                  user_id=user["id"] if user else None)
    tiles = []
    for i, q in enumerate(plan.questions):
        seed = None
        if plan.scope_filters:
            seed = plan_question(q)
            seed["filters"] = list(seed.get("filters", [])) + plan.scope_filters
            seed["intent_summary"] = (seed.get("intent_summary", "")
                                      + f" for {plan.scope_label}")
        result = run_analysis_collect(
            q, connection_id=req.connection_id, connection_url=url,
            seed_plan=seed, persist=True)
        if result.get("blocked") or result.get("error"):
            continue
        store.pin_to_dashboard(dash["id"], result["query_id"], {"i": i})
        tiles.append({"question": q, "result": result})

    return {"dashboard_id": dash["id"], "title": plan.title, "theme": plan.theme,
            "scope": plan.scope_label, "tile_count": len(tiles), "tiles": tiles}


@router.get("")
def list_dashboards(user: dict | None = Depends(get_current_user)):
    ds = get_store().list_dashboards()
    if settings.require_auth:
        ds = [d for d in ds if d.get("user_id") in (None, "")
              or (user and d["user_id"] == user["id"])]
    return {"dashboards": ds}


@router.post("/{dashboard_id}/pin")
def pin(dashboard_id: str, req: PinRequest,
        user: dict | None = Depends(get_current_user)):
    store = get_store()
    dash = store.get_dashboard(dashboard_id)
    if not dash:
        raise HTTPException(404, "unknown dashboard")
    authorize_owner(dash.get("user_id"), user)
    q = store.get_query(req.query_id)
    if not q:
        raise HTTPException(404, "unknown query_id")
    authorize_connection(q["connection_id"], user)  # can't pin another tenant's query
    return store.pin_to_dashboard(dashboard_id, req.query_id, req.position)


@router.get("/{dashboard_id}", dependencies=[Depends(rate_limit)])
def load_dashboard(dashboard_id: str, live: bool = True,
                   user: dict | None = Depends(get_current_user)):
    store = get_store()
    dash = store.get_dashboard(dashboard_id)
    if not dash:
        raise HTTPException(404, "unknown dashboard")
    authorize_owner(dash.get("user_id"), user)
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
