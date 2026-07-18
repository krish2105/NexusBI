"""Sliding-window rate limiter (per client key), Redis-backed when available.

Two backends behind one ``allow()`` interface:
  * **Redis** (when ``REDIS_URL`` is set) — a sorted-set sliding window shared
    across instances, so a multi-worker deploy enforces one real limit instead of
    N per-instance limits.
  * **In-process** (default, $0) — a per-key deque. Correct on a single instance.

If Redis is configured but hiccups mid-request, we fail *open* to the in-process
window rather than take the endpoint down.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque

from app.config import settings
from app.core.redis_client import get_redis


class RateLimiter:
    def __init__(self, limit: int | None = None, window_s: int | None = None):
        self.limit = limit or settings.rate_limit_requests
        self.window = window_s or settings.rate_limit_window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        r = get_redis()
        if r is not None:
            try:
                return self._allow_redis(r, key)
            except Exception:  # noqa: BLE001 - Redis blip -> fail open to memory
                pass
        return self._allow_memory(key, now)

    # -- in-process sliding window -----------------------------------------
    def _allow_memory(self, key: str, now: float | None) -> tuple[bool, int]:
        now = now if now is not None else time.monotonic()
        with self._lock:
            dq = self._hits[key]
            cutoff = now - self.window
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.limit:
                retry = int(self.window - (now - dq[0])) + 1
                return False, retry
            dq.append(now)
            return True, 0

    # -- Redis sliding window (sorted set of request timestamps) -----------
    def _allow_redis(self, r, key: str) -> tuple[bool, int]:
        now = time.time()
        rkey = f"nexus:rl:{key}"
        pipe = r.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - self.window)
        pipe.zcard(rkey)
        _, count = pipe.execute()
        if count >= self.limit:
            oldest = r.zrange(rkey, 0, 0, withscores=True)
            retry = int(self.window - (now - oldest[0][1])) + 1 if oldest else self.window
            return False, max(retry, 1)
        pipe = r.pipeline()
        pipe.zadd(rkey, {f"{now}:{secrets.token_hex(4)}": now})
        pipe.expire(rkey, int(self.window) + 1)
        pipe.execute()
        return True, 0


limiter = RateLimiter()
