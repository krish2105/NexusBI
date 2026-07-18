"""Shared dependencies: auth, tenant isolation, rate limiting, connection resolution."""
from __future__ import annotations

from fastapi import Header, HTTPException, Request

from app.config import settings
from app.core.crypto import decrypt
from app.core.ratelimit import limiter
from app.core.security import api_key_id, decode_jwt, verify_secret
from app.db.app_store import AppStore, get_store

DEMO_CONNECTION_ID = "demo"


def store_dep() -> AppStore:
    return get_store()


# --- auth ------------------------------------------------------------------
def get_current_user(authorization: str | None = Header(None),
                     x_api_key: str | None = Header(None)) -> dict | None:
    if authorization and authorization.lower().startswith("bearer "):
        payload = decode_jwt(authorization.split(" ", 1)[1])
        if payload:
            return {"id": payload["sub"], "email": payload.get("email")}
    if x_api_key:
        store = get_store()
        # O(1): map the key to its indexed id, then a single hash verify.
        u = store.get_user_by_api_key_id(api_key_id(x_api_key))
        if u and verify_secret(x_api_key, u["api_key_hash"]):
            return {"id": u["id"], "email": u["email"]}
        # Fallback for legacy keys issued before api_key_id existed (no index).
        if u is None:
            for cand in store.list_users():
                if not cand.get("api_key_id") and \
                        verify_secret(x_api_key, cand["api_key_hash"]):
                    return {"id": cand["id"], "email": cand["email"]}
    return None


def require_user(authorization: str | None = Header(None),
                 x_api_key: str | None = Header(None)) -> dict | None:
    user = get_current_user(authorization, x_api_key)
    if settings.require_auth and not user:
        raise HTTPException(401, "authentication required")
    return user


# --- rate limit ------------------------------------------------------------
def rate_limit(request: Request) -> None:
    from app.core.monitoring import client_ip

    ok, retry = limiter.allow(client_ip(request))
    if not ok:
        raise HTTPException(429, "rate limit exceeded",
                            headers={"Retry-After": str(retry)})


# --- connection resolution + tenant isolation ------------------------------
def resolve_connection_url(connection_id: str) -> str:
    """Map a connection id to its (decrypted, read-only) target DSN."""
    if connection_id in (DEMO_CONNECTION_ID, "", None):
        return settings.demo_target_url
    conn = get_store().get_connection(connection_id)
    if not conn:
        return settings.demo_target_url
    return decrypt(conn["target_url"])


def authorize_connection(connection_id: str, user: dict | None) -> None:
    """Per-connection tenant isolation: a user may only use their own
    connections (the bundled demo is public)."""
    if connection_id in (DEMO_CONNECTION_ID, "", None):
        return
    conn = get_store().get_connection(connection_id)
    if not conn:
        raise HTTPException(404, "unknown connection")
    if settings.require_auth:
        if not user or conn.get("user_id") != user["id"]:
            raise HTTPException(403, "this connection belongs to another account")


def can_access_connection(connection_id: str | None, user: dict | None) -> bool:
    """Non-raising form of :func:`authorize_connection`, for filtering list
    responses down to the resources a caller is allowed to see."""
    if not settings.require_auth:
        return True
    if connection_id in (DEMO_CONNECTION_ID, "", None):
        return True
    conn = get_store().get_connection(connection_id)
    return bool(conn and user and conn.get("user_id") == user["id"])


def authorize_owner(owner_id: str | None, user: dict | None) -> None:
    """Ownership check for resources keyed on a ``user_id`` (e.g. dashboards).
    Resources created in the open demo (no owner) stay public."""
    if not settings.require_auth or owner_id in (None, ""):
        return
    if not user or owner_id != user["id"]:
        raise HTTPException(403, "this resource belongs to another account")
