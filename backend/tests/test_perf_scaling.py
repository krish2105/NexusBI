"""Phase 3 perf — Redis-backed rate limiter + allow-list cache (fakeredis), and
the in-process fallback. The live-Postgres connection-pool path is exercised
separately (needs a server); here we cover the parts CI can run deterministically.
"""
import pytest

import app.core.redis_client as rc
from app.config import settings


@pytest.fixture()
def fake_redis(monkeypatch):
    fakeredis = pytest.importorskip("fakeredis")
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    # Force every consumer onto the fake shared store.
    monkeypatch.setattr(rc, "_client", client)
    monkeypatch.setattr(settings, "redis_url", "redis://fake", raising=False)
    yield client


# --- rate limiter -----------------------------------------------------------
def test_in_process_limiter_enforces_window():
    from app.core.ratelimit import RateLimiter
    rl = RateLimiter(limit=3, window_s=60)
    assert [rl.allow("k")[0] for _ in range(5)] == [True, True, True, False, False]


def test_redis_limiter_enforces_and_is_shared(fake_redis):
    from app.core.ratelimit import RateLimiter
    # Two limiter instances (simulating two workers) sharing one Redis store must
    # enforce ONE combined limit, not one-per-instance.
    a = RateLimiter(limit=3, window_s=60)
    b = RateLimiter(limit=3, window_s=60)
    results = [a.allow("user")[0], b.allow("user")[0], a.allow("user")[0],
               b.allow("user")[0]]
    assert results == [True, True, True, False]
    allowed, retry = b.allow("user")
    assert allowed is False and retry >= 1


def test_redis_limiter_falls_open_on_error(monkeypatch, fake_redis):
    """A Redis blip must not take the endpoint down — fail open to in-process."""
    from app.core.ratelimit import RateLimiter
    rl = RateLimiter(limit=2, window_s=60)

    class Boom:
        def pipeline(self, *a, **k):
            raise RuntimeError("redis down")
    monkeypatch.setattr(rc, "_client", Boom())
    # still answers (via in-process path) instead of raising
    assert rl.allow("k")[0] is True


# --- allow-list cache -------------------------------------------------------
def test_allow_list_cache_roundtrips_through_redis(fake_redis):
    from app.db import introspect
    from app.db.seed_demo import seed_sqlite
    seed_sqlite()
    al = introspect.cached_allow_list(settings.demo_target_url)
    assert al and isinstance(next(iter(al.values())), set)  # sets, not lists
    # stored in redis and second read returns an equal structure
    assert fake_redis.keys("nexus:allow:*")
    assert introspect.cached_allow_list(settings.demo_target_url) == al


def test_allow_list_cache_key_is_hashed_not_the_dsn(fake_redis):
    """A DSN can carry credentials — it must never appear in a cache key."""
    from app.db import introspect
    dsn = "postgresql://user:secret@host:5432/db"
    key = introspect._rkey(dsn)
    assert "secret" not in key and "user" not in key and key.startswith("nexus:allow:")
