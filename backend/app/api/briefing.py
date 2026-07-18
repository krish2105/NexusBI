"""Proactive daily briefing endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agents.briefing import generate_briefing
from app.api.deps import (authorize_connection, get_current_user,
                          resolve_connection_url)

router = APIRouter(tags=["briefing"])


@router.get("/briefing")
def briefing(connection_id: str = "demo",
             user: dict | None = Depends(get_current_user)):
    """Generate an executive briefing by proactively analyzing the connection.

    On-demand generation (idempotent, read-only). For a scheduled daily digest,
    a cron / GitHub Action can hit this and deliver the payload — same free-tier
    pattern as /monitors/run-all."""
    authorize_connection(connection_id, user)
    url = resolve_connection_url(connection_id)
    return generate_briefing(url=url, connection_id=connection_id)
