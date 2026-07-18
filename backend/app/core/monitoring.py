"""Error tracking (Sentry) + request-origin helpers — Phase 3 ops.

Sentry is entirely optional: no ``SENTRY_DSN`` means ``init_sentry`` is a no-op
and the SDK is never even imported, so the free-tier install/runtime is
unaffected. Set the DSN (Sentry free tier) and unhandled errors, with a scrubbed
request context, start flowing.
"""
from __future__ import annotations

import logging

from fastapi import Request

from app.config import settings

log = logging.getLogger("nexus.ops")


def init_sentry() -> bool:
    """Initialize Sentry if configured. Returns True when active."""
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            # We never want raw SQL, DSNs, or query payloads leaving in an event.
            send_default_pii=False,
            before_send=_scrub,
        )
        log.info("Sentry error tracking active")
        return True
    except Exception as e:  # noqa: BLE001 - monitoring must never break boot
        log.warning(f"SENTRY_DSN set but Sentry init failed ({e}); continuing without it")
        return False


def _scrub(event, _hint):
    """Belt-and-braces: strip anything that could carry secrets/PII before send."""
    req = event.get("request") or {}
    req.pop("cookies", None)
    req.pop("data", None)               # request bodies (may hold questions/DSNs)
    headers = req.get("headers") or {}
    for h in ("authorization", "x-api-key", "cookie"):
        headers.pop(h, None)
        headers.pop(h.title(), None)
    return event


def client_ip(request: Request) -> str:
    """The real client IP for rate limiting. Behind proxies (Render/Vercel) the
    socket peer is the proxy, so with ``trusted_proxy_count`` > 0 we read the
    client from X-Forwarded-For (the Nth entry from the right, N = trusted
    proxies) — otherwise a whole deployment shares one rate-limit bucket. With 0
    trusted proxies we use the socket peer and ignore XFF (which a client could
    otherwise spoof to evade limits)."""
    n = settings.trusted_proxy_count
    if n > 0:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                return parts[-min(n, len(parts))]
    return request.client.host if request.client else "anonymous"
