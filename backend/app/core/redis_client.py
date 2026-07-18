"""Optional Redis connection (Upstash free tier works out of the box).

When ``REDIS_URL`` is unset, this returns ``None`` and every consumer falls back
to an in-process default — so the app runs at $0 on a single instance. Set
``REDIS_URL`` and the rate limiter + allow-list cache become shared across
instances, which is what makes horizontal scale (multiple stateless workers)
correct instead of per-instance-approximate.
"""
from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger("nexus.redis")

_client = "unset"  # sentinel: distinguishes "not yet tried" from "tried, got None"


def get_redis():
    """Cached Redis client, or ``None`` when unconfigured/unreachable."""
    global _client
    if _client != "unset":
        return _client
    if not settings.redis_url:
        _client = None
        return None
    try:
        import redis  # lazy: only imported when REDIS_URL is set

        c = redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=2, socket_timeout=2,
            decode_responses=True)
        c.ping()
        _client = c
        log.info("Redis connected — shared rate limiter + allow-list cache active")
    except Exception as e:  # noqa: BLE001 - never let Redis take the app down
        log.warning(f"REDIS_URL set but Redis is unreachable ({e}); "
                    "falling back to in-process rate limiter/cache")
        _client = None
    return _client


def reset_for_tests() -> None:
    """Drop the cached client so a test can toggle REDIS_URL."""
    global _client
    _client = "unset"
