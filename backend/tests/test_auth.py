"""Phase 3 auth — email+password signup/login, JWT, O(1) API-key lookup."""
import tempfile

import pytest
from fastapi.testclient import TestClient

import app.db.app_store as app_store
from app.core.security import api_key_id, hash_secret, verify_secret
from app.db.app_store import AppStore
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    # Isolate each test on a fresh app DB so user rows don't collide.
    url = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
    monkeypatch.setattr(app_store, "_store", AppStore(url=url))
    with TestClient(app) as c:
        yield c


def test_signup_returns_session_and_one_time_key(client):
    r = client.post("/auth/signup", json={"email": "A@B.com", "password": "hunter2hunter"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "a@b.com"        # normalized
    assert body["user"]["plan"] == "free"
    assert body["access_token"] and body["api_key"].startswith("nxs_")


def test_signup_rejects_dupe_and_bad_input(client):
    client.post("/auth/signup", json={"email": "x@y.com", "password": "longenough1"})
    assert client.post("/auth/signup",
                       json={"email": "X@Y.com", "password": "longenough1"}).status_code == 409
    assert client.post("/auth/signup",
                       json={"email": "x@y.com", "password": "short"}).status_code == 422
    assert client.post("/auth/signup",
                       json={"email": "notanemail", "password": "longenough1"}).status_code == 422


def test_login_and_me_via_jwt(client):
    client.post("/auth/signup", json={"email": "u@v.com", "password": "correcthorse"})
    assert client.post("/auth/login",
                       json={"email": "u@v.com", "password": "wrong"}).status_code == 401
    tok = client.post("/auth/login",
                      json={"email": "u@v.com", "password": "correcthorse"}).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200 and me.json()["email"] == "u@v.com"


def test_api_key_auth_is_indexed(client):
    key = client.post("/auth/signup",
                      json={"email": "k@k.com", "password": "passwordlong"}).json()["api_key"]
    # the key resolves via the indexed id, not a full-table scan
    store = app_store.get_store()
    u = store.get_user_by_api_key_id(api_key_id(key))
    assert u and verify_secret(key, u["api_key_hash"])
    me = client.get("/auth/me", headers={"X-API-Key": key})
    assert me.status_code == 200 and me.json()["email"] == "k@k.com"
    assert client.get("/auth/me", headers={"X-API-Key": "nxs_bogus"}).status_code == 401


def test_password_hash_is_not_plaintext(client):
    client.post("/auth/signup", json={"email": "p@p.com", "password": "myrealpassword"})
    row = app_store.get_store().get_user_by_email("p@p.com")
    assert "myrealpassword" not in (row["password_hash"] or "")
    assert row["password_hash"].startswith("pbkdf2_sha256$")
    assert verify_secret("myrealpassword", row["password_hash"])
