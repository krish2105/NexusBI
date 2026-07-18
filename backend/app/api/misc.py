"""History, audit log, eval reports, and health."""
from __future__ import annotations

import json

from fastapi import APIRouter

from app.config import settings
from app.core.tracing import is_enabled as tracing_enabled
from app.db.app_store import get_store
from app.llm.client import get_llm

router = APIRouter(tags=["meta"])

EVALS_DIR = settings.data_dir.parent.parent / "evals"  # backend/evals (M7 output)


@router.get("/history")
def history(limit: int = 50):
    return {"queries": get_store().list_queries(limit=limit)}


@router.get("/audit")
def audit(limit: int = 100):
    return {"audit": get_store().list_audit(limit=limit)}


@router.get("/evals")
def evals():
    """Serve the eval reports for the in-app 'How accurate is Nexus?' page."""
    out: dict = {}
    for name in ("text2sql_report.json", "sql_safety_report.json",
                 "forecast_report.json", "rag_report.json",
                 "spider_report.json"):
        path = EVALS_DIR / name
        if path.exists():
            out[name.replace("_report.json", "")] = json.loads(path.read_text())
    return out or {"status": "run `make eval` to generate reports"}


@router.get("/health")
def health():
    llm = get_llm()
    return {"status": "ok", "app": settings.app_name,
            "llm_provider": llm.provider, "demo_target": settings.demo_target_url,
            "safety": "5-layer text-to-SQL guard active",
            "tracing": "langfuse (on)" if tracing_enabled() else "off"}


@router.get("/status")
def status():
    """Component health for an uptime check / status page. Each component reports
    ``ok``/``degraded``/``off``; overall is ``degraded`` if any hard dependency
    (the app DB) is down. Optional services report ``off`` when unconfigured —
    that's expected on the free tier, not a failure."""
    from app.core.monitoring import client_ip  # noqa: F401 (import-safety check)
    from app.core.redis_client import get_redis

    components: dict[str, dict] = {}

    # App metadata DB — the one hard dependency.
    try:
        get_store().list_users()
        components["app_db"] = {"status": "ok",
                                "backend": get_store().kind}
    except Exception as e:  # noqa: BLE001
        components["app_db"] = {"status": "degraded", "detail": str(e)[:120]}

    # Redis (optional): off when unconfigured, ok when reachable.
    components["redis"] = {
        "status": "ok" if get_redis() is not None
        else ("off" if not settings.redis_url else "degraded"),
        "shared_state": get_redis() is not None,
    }

    components["llm"] = {"status": "ok", "provider": get_llm().provider}
    components["safety"] = {"status": "ok", "guard": "5-layer, sqlguard-backed"}
    components["error_tracking"] = {
        "status": "ok" if settings.sentry_dsn else "off"}
    components["billing"] = {
        "status": "ok" if settings.billing_enabled else "off",
        "mode": "stripe" if settings.billing_enabled else "free-only"}

    overall = "degraded" if components["app_db"]["status"] != "ok" else "ok"
    return {"status": overall, "app": settings.app_name, "components": components}
