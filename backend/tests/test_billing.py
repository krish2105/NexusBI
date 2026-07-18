"""Phase 3 billing — Free-tier metering, account/BYO-key, Stripe env-gating."""
import tempfile

import pytest
from fastapi.testclient import TestClient

import app.db.app_store as app_store
from app.config import settings
from app.core.crypto import decrypt
from app.db.app_store import AppStore
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(app_store, "_store",
                        AppStore(url=f"sqlite:///{tempfile.mktemp(suffix='.db')}"))
    with TestClient(app) as c:
        yield c


def _signup(client, email="p@p.com"):
    b = client.post("/auth/signup", json={"email": email, "password": "longpassword"}).json()
    return b["access_token"], b["user"]["id"], {"Authorization": f"Bearer {b['access_token']}"}


# --- metering ---------------------------------------------------------------
def test_free_tier_daily_query_cap(client, monkeypatch):
    monkeypatch.setattr(settings, "free_tier_daily_queries", 3)
    _, uid, hdr = _signup(client)
    store = app_store.get_store()
    # a non-demo connection owned by the user (metering only applies off-demo)
    conn = store.create_connection(uid, "mine", "sqlite:///x.db", "sqlite")["id"]
    # 3 allowed, 4th blocked with 402
    for _ in range(3):
        assert store.count_usage_since  # sanity
        r = client.post("/query", json={"question": "revenue", "connection_id": conn},
                        headers=hdr)
        assert r.status_code == 200, r.text
    blocked = client.post("/query", json={"question": "revenue", "connection_id": conn},
                          headers=hdr)
    assert blocked.status_code == 402
    assert blocked.json()["detail"]["error"] == "quota_exceeded"


def test_demo_is_never_metered(client, monkeypatch):
    monkeypatch.setattr(settings, "free_tier_daily_queries", 1)
    _, _, hdr = _signup(client)
    for _ in range(3):  # well past the cap, but the demo is free
        r = client.post("/query", json={"question": "x", "connection_id": "demo"},
                        headers=hdr)
        assert r.status_code == 200


def test_pro_user_is_uncapped(client, monkeypatch):
    monkeypatch.setattr(settings, "free_tier_daily_queries", 1)
    _, uid, hdr = _signup(client)
    store = app_store.get_store()
    store.set_plan(uid, "pro")
    conn = store.create_connection(uid, "mine", "sqlite:///x.db", "sqlite")["id"]
    for _ in range(3):
        r = client.post("/query", json={"question": "x", "connection_id": conn},
                        headers=hdr)
        assert r.status_code == 200


def test_free_tier_connection_cap(client, monkeypatch):
    monkeypatch.setattr(settings, "free_tier_max_connections", 1)
    monkeypatch.setattr(settings, "allow_local_targets", True)
    _, uid, hdr = _signup(client)
    app_store.get_store().create_connection(uid, "c1", "sqlite:///a.db", "sqlite")
    # 2nd connection over the free cap -> 402
    r = client.post("/connections",
                    json={"name": "c2", "target_url": "sqlite:///b.db",
                          "read_only_confirmed": True}, headers=hdr)
    assert r.status_code == 402


# --- account + BYO key ------------------------------------------------------
def test_account_snapshot_and_byo_key(client):
    _, uid, hdr = _signup(client)
    acct = client.get("/account", headers=hdr).json()
    assert acct["usage"]["plan"] == "free"
    assert acct["usage"]["daily_query_limit"] == settings.free_tier_daily_queries
    assert acct["usage"]["byo_llm_key"] is False

    # set a BYO key -> stored encrypted, reflected in the snapshot
    r = client.post("/account/llm-key", json={"provider": "groq", "key": "gsk_secret_key_123"},
                    headers=hdr)
    assert r.status_code == 200
    row = app_store.get_store().get_user(uid)
    assert row["byo_llm_key_enc"].startswith("enc:v1:")
    assert decrypt(row["byo_llm_key_enc"]) == "gsk_secret_key_123"
    assert client.get("/account", headers=hdr).json()["usage"]["byo_llm_key"] is True

    assert client.delete("/account/llm-key", headers=hdr).status_code == 200
    assert app_store.get_store().get_user(uid)["byo_llm_key_enc"] is None


def test_account_requires_auth(client):
    assert client.get("/account").status_code == 401


# --- billing env-gating -----------------------------------------------------
def test_billing_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", None)
    assert client.get("/billing/config").json()["enabled"] is False
    _, _, hdr = _signup(client)
    j = client.post("/billing/checkout", headers=hdr).json()
    assert j["enabled"] is False   # no Stripe -> no checkout, everyone stays Free


def test_webhook_ignored_when_billing_off(client):
    r = client.post("/billing/webhook", content=b"{}")
    assert r.status_code == 200 and "ignored" in r.json()
