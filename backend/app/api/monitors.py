"""Scheduled anomaly monitors + alert inbox.

Create a monitor (a saved question), run it on demand, or run all enabled
monitors via POST /monitors/run-all — the endpoint a cron or GitHub Action
calls on a schedule. Anomalous results raise alerts.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.monitor import run_all_monitors, run_monitor
from app.api.deps import authorize_connection, get_current_user, require_user
from app.db.app_store import get_store

router = APIRouter(tags=["monitors"])


class MonitorRequest(BaseModel):
    name: str
    question: str
    connection_id: str = "demo"
    schedule: str | None = "0 8 * * *"   # informational cron (daily 08:00)


@router.post("/monitors")
def create_monitor(req: MonitorRequest, user: dict | None = Depends(get_current_user)):
    authorize_connection(req.connection_id, user)
    return get_store().create_monitor(req.name, req.question, req.connection_id,
                                      req.schedule)


@router.get("/monitors")
def list_monitors():
    return {"monitors": get_store().list_monitors()}


@router.post("/monitors/{monitor_id}/run")
def run_one(monitor_id: str):
    m = get_store().get_monitor(monitor_id)
    if not m:
        raise HTTPException(404, "unknown monitor")
    out = run_monitor(m)
    return {"status": out["status"], "alerts": out["alerts"],
            "result": out["result"]}


@router.post("/monitors/run-all")
def run_all():
    """Batch entrypoint for a cron / GitHub Action scheduler."""
    return run_all_monitors()


@router.post("/monitors/{monitor_id}/toggle")
def toggle(monitor_id: str, enabled: bool = True):
    get_store().set_monitor_enabled(monitor_id, enabled)
    return {"monitor_id": monitor_id, "enabled": enabled}


@router.delete("/monitors/{monitor_id}")
def delete(monitor_id: str, user: dict | None = Depends(require_user)):
    get_store().delete_monitor(monitor_id)
    return {"deleted": monitor_id}


@router.get("/alerts")
def alerts(limit: int = 100):
    return {"alerts": get_store().list_alerts(limit=limit)}


@router.post("/alerts/{alert_id}/ack")
def ack(alert_id: str):
    get_store().acknowledge_alert(alert_id)
    return {"acknowledged": alert_id}
