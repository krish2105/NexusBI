"""Access-control tests — the IDOR/SSE fixes.

Under REQUIRE_AUTH, a resource (query, conversation, dashboard, monitor, alert) is
scoped to its connection's / owner's account: tenant B must not read or act on
tenant A's resources, and the bundled demo stays public. Also proves the SSE
stream replays a completed query instead of re-running the pipeline, and that the
cross-tenant run-all batch is gated by a service token.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.ratelimit import limiter
from app.db.app_store import get_store
from app.main import app


@pytest.fixture
def multi_tenant(monkeypatch):
    """REQUIRE_AUTH on + two registered tenants (A, B) with an owned connection,
    query, conversation, dashboard and monitor belonging to A."""
    monkeypatch.setattr(settings, "require_auth", True)
    limiter._hits.clear()  # avoid cumulative 429s from earlier tests
    store = get_store()
    with TestClient(app) as c:
        import uuid
        a = c.post("/auth/register",
                   json={"email": f"a-{uuid.uuid4().hex[:8]}@t.com"}).json()
        b = c.post("/auth/register",
                   json={"email": f"b-{uuid.uuid4().hex[:8]}@t.com"}).json()
        # A's resources (created directly so we don't need the connect-time
        # SSRF/read-only HTTP flow). The connection points at the real demo DB so
        # A's monitor is actually executable in the run-all test.
        conn = store.create_connection(a["user_id"], "a-conn",
                                       settings.demo_target_url, "sqlite", True)
        qid = store.save_query(conn["id"], "A secret question", "SELECT 1", "HIGH",
                               [], {}, {"answer": "A's private data"},
                               user_id=a["user_id"])
        conv = store.create_conversation(conn["id"], "A thread")
        dash = store.create_dashboard("A board", user_id=a["user_id"])
        mon = store.create_monitor("A monitor", "revenue?", conn["id"])
        yield {"c": c, "store": store,
               "A": a["api_key"], "B": b["api_key"],
               "conn": conn["id"], "qid": qid, "conv": conv["id"],
               "dash": dash["id"], "mon": mon["id"]}


def _h(key):
    return {"X-API-Key": key}


# ------------------------------------------------------------- query IDOR
def test_get_query_blocks_other_tenant(multi_tenant):
    m = multi_tenant
    assert m["c"].get(f"/query/{m['qid']}", headers=_h(m["A"])).status_code == 200
    assert m["c"].get(f"/query/{m['qid']}", headers=_h(m["B"])).status_code == 403
    assert m["c"].get(f"/query/{m['qid']}").status_code == 403        # anonymous


def test_stream_blocks_other_tenant(multi_tenant):
    m = multi_tenant
    assert m["c"].get(f"/query/{m['qid']}/stream",
                      headers=_h(m["B"])).status_code == 403


# ------------------------------------------------------- SSE replay (no re-exec)
def test_completed_query_is_replayed_not_reexecuted():
    """A finished query streams its stored result (no pipeline re-run)."""
    limiter._hits.clear()
    with TestClient(app) as c:  # demo connection is public — no auth needed
        qid = c.post("/query",
                     json={"question": "Total merchandise revenue"}).json()["query_id"]
        # First stream executes the pipeline (validator + executor nodes present).
        first = c.get(f"/query/{qid}/stream").text
        assert "sql_validator" in first and "replayed" not in first
        # Second stream replays the stored result — no pipeline nodes, flagged.
        second = c.get(f"/query/{qid}/stream").text
        assert '"replayed": true' in second
        assert "sql_validator" not in second and "executor" not in second


# ------------------------------------------------------- conversation IDOR
def test_get_conversation_blocks_other_tenant(multi_tenant):
    m = multi_tenant
    assert m["c"].get(f"/conversations/{m['conv']}",
                      headers=_h(m["A"])).status_code == 200
    assert m["c"].get(f"/conversations/{m['conv']}",
                      headers=_h(m["B"])).status_code == 403


# ------------------------------------------------------- dashboard IDOR
def test_load_dashboard_blocks_other_tenant(multi_tenant):
    m = multi_tenant
    assert m["c"].get(f"/dashboards/{m['dash']}",
                      headers=_h(m["A"])).status_code == 200
    assert m["c"].get(f"/dashboards/{m['dash']}",
                      headers=_h(m["B"])).status_code == 403


# ------------------------------------------------------- monitor IDOR
def test_monitors_scoped_and_actions_blocked(multi_tenant):
    m = multi_tenant
    # B does not see A's monitor in the list…
    b_list = m["c"].get("/monitors", headers=_h(m["B"])).json()["monitors"]
    assert all(x["id"] != m["mon"] for x in b_list)
    a_list = m["c"].get("/monitors", headers=_h(m["A"])).json()["monitors"]
    assert any(x["id"] == m["mon"] for x in a_list)
    # …and cannot run / toggle / delete it.
    assert m["c"].post(f"/monitors/{m['mon']}/run",
                       headers=_h(m["B"])).status_code == 403
    assert m["c"].post(f"/monitors/{m['mon']}/toggle",
                       headers=_h(m["B"])).status_code == 403
    assert m["c"].delete(f"/monitors/{m['mon']}",
                         headers=_h(m["B"])).status_code == 403


def test_run_all_requires_service_token(multi_tenant, monkeypatch):
    m = multi_tenant
    # No token configured + REQUIRE_AUTH → refused.
    assert m["c"].post("/monitors/run-all").status_code == 403
    # With a token configured, the header must match.
    monkeypatch.setattr(settings, "monitor_run_token", "s3cret-cron")
    assert m["c"].post("/monitors/run-all").status_code == 403
    assert m["c"].post("/monitors/run-all",
                       headers={"X-Monitor-Token": "wrong"}).status_code == 403
    assert m["c"].post("/monitors/run-all",
                       headers={"X-Monitor-Token": "s3cret-cron"}).status_code == 200


# ------------------------------------------------------- demo stays public
def test_demo_stays_public_under_require_auth(multi_tenant):
    """Enabling auth must not break the public bundled-demo experience."""
    m = multi_tenant
    r = m["c"].post("/query/run", json={"question": "Total merchandise revenue"})
    assert r.status_code == 200 and not r.json()["blocked"]
