"""Shared dependencies: the app store, and connection -> target URL resolution."""
from __future__ import annotations

from app.config import settings
from app.db.app_store import AppStore, get_store

DEMO_CONNECTION_ID = "demo"


def store_dep() -> AppStore:
    return get_store()


def resolve_connection_url(connection_id: str) -> str:
    """Map a connection id to its (read-only) target DSN. 'demo' -> bundled DB."""
    if connection_id in (DEMO_CONNECTION_ID, "", None):
        return settings.demo_target_url
    conn = get_store().get_connection(connection_id)
    if not conn:
        return settings.demo_target_url
    return conn["target_url"]
