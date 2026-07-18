"""Plan definitions + usage metering (Free vs Pro) — Phase 3 billing.

Free is the default and needs no Stripe. When billing is unconfigured everyone is
Free and the caps still apply (so the free tier is real, not just a label); the
open demo connection is never metered. Pro (a paid Stripe subscription) lifts the
caps and unlocks BYO-LLM-key.
"""
from __future__ import annotations

import time

from fastapi import HTTPException

from app.config import settings
from app.db.app_store import get_store

FREE = "free"
PRO = "pro"


def _day_start() -> float:
    now = time.time()
    return now - (now % 86400)  # epoch is UTC, so this is UTC midnight


def is_pro(user_row: dict | None) -> bool:
    return bool(user_row and user_row.get("plan") == PRO)


def usage_snapshot(user_id: str) -> dict:
    store = get_store()
    u = store.get_user(user_id) or {}
    pro = is_pro(u)
    return {
        "plan": u.get("plan", FREE),
        "queries_today": store.count_usage_since(user_id, _day_start()),
        "daily_query_limit": None if pro else settings.free_tier_daily_queries,
        "connections": store.count_user_connections(user_id),
        "connection_limit": None if pro else settings.free_tier_max_connections,
        "byo_llm_key": bool(u.get("byo_llm_key_enc")),
        "billing_enabled": settings.billing_enabled,
    }


def check_query_quota(user_id: str) -> None:
    """Raise 402 if a Free user is over the daily query cap. Pro is unlimited."""
    store = get_store()
    if is_pro(store.get_user(user_id)):
        return
    used = store.count_usage_since(user_id, _day_start())
    if used >= settings.free_tier_daily_queries:
        raise HTTPException(402, {
            "error": "quota_exceeded",
            "detail": f"Free tier allows {settings.free_tier_daily_queries} "
                      "queries/day. Upgrade to Pro for unlimited.",
            "limit": settings.free_tier_daily_queries})


def check_connection_quota(user_id: str) -> None:
    store = get_store()
    if is_pro(store.get_user(user_id)):
        return
    if store.count_user_connections(user_id) >= settings.free_tier_max_connections:
        raise HTTPException(402, {
            "error": "connection_limit",
            "detail": f"Free tier allows {settings.free_tier_max_connections} "
                      "connections. Upgrade to Pro for more.",
            "limit": settings.free_tier_max_connections})


def byo_llm_key_for(user_id: str | None) -> str | None:
    """A Pro user's decrypted BYO Groq key, if set — else None (shared/zero-key
    path). Honored for any authed user when billing is off (self-host/dev)."""
    if not user_id:
        return None
    from app.core.crypto import decrypt

    u = get_store().get_user(user_id)
    if not u or not u.get("byo_llm_key_enc"):
        return None
    if settings.billing_enabled and not is_pro(u):
        return None
    try:
        return decrypt(u["byo_llm_key_enc"])
    except Exception:  # noqa: BLE001
        return None
