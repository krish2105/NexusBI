"""Phase 3 ops — XFF-aware client IP, /status readout, Sentry no-op default."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.monitoring import client_ip, init_sentry
from app.main import app


def _req(xff: str | None, peer: str = "10.0.0.9"):
    headers = {"x-forwarded-for": xff} if xff is not None else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_client_ip_uses_socket_peer_when_no_trusted_proxies(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    # XFF is ignored (spoofable) when we trust no proxies
    assert client_ip(_req("1.2.3.4", peer="10.0.0.9")) == "10.0.0.9"


def test_client_ip_reads_xff_behind_one_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    # one trusted proxy -> real client is the rightmost XFF entry
    assert client_ip(_req("203.0.113.7")) == "203.0.113.7"
    assert client_ip(_req("client, 203.0.113.7")) == "203.0.113.7"


def test_client_ip_two_proxies_picks_correct_hop(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 2)
    # trust 2 proxies -> 2nd from the right
    assert client_ip(_req("realclient, edge, cdn")) == "edge"


def test_init_sentry_is_noop_without_dsn(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", None)
    assert init_sentry() is False


def test_status_endpoint_reports_components():
    with TestClient(app) as c:
        j = c.get("/status").json()
    assert j["status"] in ("ok", "degraded")
    comp = j["components"]
    assert comp["app_db"]["status"] == "ok"
    assert comp["safety"]["status"] == "ok"
    # optional services are "off" (not failures) when unconfigured on the free tier
    assert comp["redis"]["status"] in ("off", "ok")
    assert comp["billing"]["status"] in ("off", "ok")
    assert comp["error_tracking"]["status"] in ("off", "ok")
