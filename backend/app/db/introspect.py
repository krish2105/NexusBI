"""Schema introspection -> allow-list and column metadata.

The allow-list is derived from the *live* target schema on connect, so it always
matches reality (and hallucinated identifiers are rejected for free). It's cached
because it gates every query: in-process (lru) on a single instance, or in Redis
(shared, TTL'd) when ``REDIS_URL`` is set so a multi-worker deploy doesn't
re-introspect per instance.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from app.core.redis_client import get_redis
from app.db.target_pool import TargetPool
from app.sqlsafety import AllowList

_TTL_S = 3600  # schema changes rarely; an hour bounds staleness for uploads


def build_allow_list(pool: TargetPool | None = None) -> AllowList:
    pool = pool or TargetPool()
    allow: AllowList = {}
    for table in pool.list_tables():
        cols = {name.lower() for name, _type in pool.table_columns(table)}
        allow[table.lower()] = cols
    return allow


@lru_cache(maxsize=8)
def _lru_allow_list(url: str) -> AllowList:
    return build_allow_list(TargetPool(url=url))


def _rkey(url: str) -> str:
    # Never put a DSN (may carry credentials) in a cache key — hash it.
    return "nexus:allow:" + hashlib.sha256(url.encode()).hexdigest()[:16]


def cached_allow_list(url: str) -> AllowList:
    r = get_redis()
    if r is None:
        return _lru_allow_list(url)
    try:
        raw = r.get(_rkey(url))
        if raw:
            return {t: set(cols) for t, cols in json.loads(raw).items()}
    except Exception:  # noqa: BLE001 - cache read must never break a query
        pass
    allow = build_allow_list(TargetPool(url=url))
    try:
        r.set(_rkey(url), json.dumps({t: sorted(c) for t, c in allow.items()}),
              ex=_TTL_S)
    except Exception:  # noqa: BLE001
        pass
    return allow


def invalidate_allow_list(url: str) -> None:
    """Drop the cached schema for a connection (e.g. after a CSV re-upload)."""
    _lru_allow_list.cache_clear()
    r = get_redis()
    if r is not None:
        try:
            r.delete(_rkey(url))
        except Exception:  # noqa: BLE001
            pass
