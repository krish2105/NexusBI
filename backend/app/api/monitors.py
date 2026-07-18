"""Scheduled anomaly monitors + alert inbox.

Create a monitor (a saved question), run it on demand, or run all enabled
monitors via POST /monitors/run-all — the entrypoint a cron or GitHub Action
calls on a schedule. Anomalous results raise alerts.

Access control: monitors and alerts inherit tenant isolation from their
connection — under REQUIRE_AUTH a caller only sees / runs monitors on connections
they own (the bundled demo is public). ``run-all`` runs across tenants, so it is
gated by a shared service token (``MONITOR_RUN_TOKEN``) instead of a user session.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.agents.monitor import run_all_monitors, run_monitor
from app.api.deps import (authorize_connection, can_access_connection,
                          get_current_user, rate_limit, require_user)
from app.config import settings
from app.db.app_store import get_store

router = APIRouter(tags=["monitors"])


class MonitorRequest(BaseModel):
    name: str
    question: str
    connection_id: str = "demo"
    schedule: str | None = "0 8 * * *"   # informational cron (daily 08:00)


def _get_owned_monitor(monitor_id: str, user: dict | None) -> dict:
    m = get_store().get_monitor(monitor_id)
    if not m:
        raise HTTPException(404, "unknown monitor")
    authorize_connection(m["connection_id"], user)  # tenant isolation via connection
    return m


@router.post("/monitors")
def create_monitor(req: MonitorRequest, user: dict | None = Depends(get_current_user)):
    authorize_connection(req.connection_id, user)
    return get_store().create_monitor(req.name, req.question, req.connection_id,
                                      req.schedule)


@router.get("/monitors")
def list_monitors(user: dict | None = Depends(get_current_user)):
    rows = get_store().list_monitors()
    rows = [m for m in rows if can_access_connection(m.get("connection_id"), user)]
    return {"monitors": rows}


@router.post("/monitors/{monitor_id}/run", dependencies=[Depends(rate_limit)])
def run_one(monitor_id: str, user: dict | None = Depends(get_current_user)):
    m = _get_owned_monitor(monitor_id, user)
    out = run_monitor(m)
    return {"status": out["status"], "alerts": out["alerts"],
            "result": out["result"]}


@router.post("/monitors/run-all")
def run_all(x_monitor_token: str | None = Header(None),
            user: dict | None = Depends(get_current_user)):
    """Batch entrypoint for a cron / GitHub Action scheduler. Runs every enabled
    monitor across all tenants, so it is gated by the service token when one is
    configured (required whenever REQUIRE_AUTH is on)."""
    if settings.monitor_run_token:
        if x_monitor_token != settings.monitor_run_token:
            raise HTTPException(403, "invalid or missing X-Monitor-Token")
    elif settings.require_auth:
        raise HTTPException(
            403, "set MONITOR_RUN_TOKEN to enable scheduled cross-tenant runs")
    return run_all_monitors()


@router.post("/monitors/{monitor_id}/toggle")
def toggle(monitor_id: str, enabled: bool = True,
           user: dict | None = Depends(get_current_user)):
    _get_owned_monitor(monitor_id, user)
    get_store().set_monitor_enabled(monitor_id, enabled)
    return {"monitor_id": monitor_id, "enabled": enabled}


@router.delete("/monitors/{monitor_id}")
def delete(monitor_id: str, user: dict | None = Depends(require_user)):
    _get_owned_monitor(monitor_id, user)
    get_store().delete_monitor(monitor_id)
    return {"deleted": monitor_id}


@router.get("/alerts")
def alerts(limit: int = 100, user: dict | None = Depends(get_current_user)):
    rows = get_store().list_alerts(limit=limit)
    if settings.require_auth:
        conn_by_monitor = {m["id"]: m.get("connection_id")
                           for m in get_store().list_monitors()}
        rows = [a for a in rows
                if can_access_connection(conn_by_monitor.get(a["monitor_id"]), user)]
    return {"alerts": rows}


@router.post("/alerts/{alert_id}/ack")
def ack(alert_id: str, user: dict | None = Depends(get_current_user)):
    # Scope the ack to an alert on a monitor the caller owns.
    if settings.require_auth:
        alert = next((a for a in get_store().list_alerts(limit=1000)
                      if a["id"] == alert_id), None)
        if not alert:
            raise HTTPException(404, "unknown alert")
        _get_owned_monitor(alert["monitor_id"], user)
    get_store().acknowledge_alert(alert_id)
    return {"acknowledged": alert_id}
