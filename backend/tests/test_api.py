"""API integration tests via FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    j = client.get("/health").json()
    assert j["status"] == "ok"
    assert "5-layer" in j["safety"]


def test_demo_connection_listed(client):
    ids = [c["id"] for c in client.get("/connections").json()["connections"]]
    assert "demo" in ids


def test_schema_endpoint_returns_catalog(client):
    j = client.get("/connections/demo/schema").json()
    assert len(j["tables"]) >= 10
    assert any(g["term"] == "merchandise revenue" for g in j["glossary"])


def test_run_query_returns_grounded_result(client):
    r = client.post("/query/run",
                    json={"question": "How many delivered orders are there?"}).json()
    assert not r["blocked"]
    assert r["rows"][0]["order_count"] == 96478


def test_malicious_query_blocked_via_api(client):
    r = client.post("/query/run", json={"question": "delete all orders"}).json()
    assert r["blocked"] and not r["rows"]


def test_sse_stream_emits_pipeline(client):
    qid = client.post("/query",
                      json={"question": "Total merchandise revenue"}).json()["query_id"]
    events = []
    with client.stream("GET", f"/query/{qid}/stream") as s:
        for line in s.iter_lines():
            if line and line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
    assert "sql_validator" in events and events[-1] == "done"
    assert events.index("sql_validator") < events.index("executor")


def test_audit_log_records_queries(client):
    client.post("/query/run", json={"question": "Total merchandise revenue"})
    audit = client.get("/audit").json()["audit"]
    assert any(a["action"] == "query.executed" for a in audit)


def test_dashboard_pin_and_load(client):
    q = client.post("/query/run",
                    json={"question": "Show payment value by payment type"}).json()
    qid = q["query_id"]
    dash = client.post("/dashboards", json={"name": "Exec Overview"}).json()
    did = dash["id"]
    client.post(f"/dashboards/{did}/pin", json={"query_id": qid})
    loaded = client.get(f"/dashboards/{did}").json()
    assert loaded["items"] and loaded["items"][0]["result"]["rows"]
