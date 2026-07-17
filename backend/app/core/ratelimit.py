"""Simple in-memory sliding-window rate limiter (per client key).

Free-tier friendly (no Redis). For a multi-instance deploy, swap the backing
store for Redis behind the same ``allow()`` interface.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.config import settings


class RateLimiter:
    def __init__(self, limit: int | None = None, window_s: int | None = None):
        self.limit = limit or settings.rate_limit_requests
        self.window = window_s or settings.rate_limit_window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
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


limiter = RateLimiter()
