"""Decision-intelligence suite: RFM segments, feedback loop, monitors, Trust Center."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --- RFM segmentation ---
def test_segments_endpoint(client):
    j = client.get("/insights/segments?connection_id=demo").json()
    assert j["available"]
    assert j["total_customers"] > 50000            # full customer base, not the row cap
    segs = {s["segment"] for s in j["segments"]}
    assert "Champions" in segs
    assert sum(s["count"] for s in j["segments"]) == j["total_customers"]
    assert j["scatter"]


def test_segments_unavailable_on_uploaded_without_features(client):
    import io
    up = client.post(
        "/connections/upload",
        files={"files": ("tiny.csv", io.BytesIO(b"a,b\n1,2\n3,4\n"), "text/csv")},
        data={"name": "tiny"}).json()
    j = client.get(f"/insights/segments?connection_id={up['connection_id']}").json()
    assert not j["available"]


# --- feedback loop ---
def test_feedback_up_becomes_vetted_example(client):
    q = client.post("/query/run",
                    json={"question": "Total merchandise revenue"}).json()
    r = client.post(f"/query/{q['query_id']}/feedback", json={"rating": "up"})
    assert r.status_code == 200
    assert r.json()["stats"]["up"] >= 1
    stats = client.get("/feedback/stats").json()
    assert any(e["question"] == "Total merchandise revenue"
               for e in stats["vetted_examples"])


def test_feedback_rejects_bad_rating(client):
    q = client.post("/query/run", json={"question": "Total merchandise revenue"}).json()
    assert client.post(f"/query/{q['query_id']}/feedback",
                       json={"rating": "maybe"}).status_code == 400


# --- monitors + alerts ---
def test_monitor_run_raises_alert_on_anomalous_series(client):
    m = client.post("/monitors", json={
        "name": "Monthly revenue watch",
        "question": "Show monthly merchandise revenue over time",
        "connection_id": "demo"}).json()
    out = client.post(f"/monitors/{m['id']}/run").json()
    assert out["status"] == "ok"
    # The Olist monthly series has a sharp final-period drop -> an alert.
    assert isinstance(out["alerts"], list)
    alerts = client.get("/alerts").json()["alerts"]
    assert isinstance(alerts, list)


def test_run_all_monitors_batch(client):
    out = client.post("/monitors/run-all").json()
    assert out["monitors_run"] >= 1
    assert "alerts_raised" in out


# --- Trust Center ---
def test_trust_summary(client):
    j = client.get("/trust/summary").json()
    assert "safety" in j and "governance" in j and "feedback" in j
    assert j["governance"]["queries_executed"] >= 1
    assert len(j["principles"]) >= 3
