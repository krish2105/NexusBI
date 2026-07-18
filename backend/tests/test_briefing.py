"""Proactive daily briefing — proactive analysis of key metrics."""
import pytest
from fastapi.testclient import TestClient

from app.agents.briefing import generate_briefing
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_briefing_available_and_shaped():
    b = generate_briefing()
    assert b["available"]
    assert b["headline"]
    assert len(b["metrics"]) >= 5
    assert b["forecast_outlook"]


def test_briefing_uses_complete_periods_not_partial_month():
    # The August-2018 review score must be ~4.2 (complete), not the ~2.2 partial
    # tail — i.e. all metrics read off the same complete-period window.
    b = generate_briefing()
    rev = next(m for m in b["metrics"] if m["column"] == "merchandise_value")
    score = next(m for m in b["metrics"] if m["column"] == "average_review_score")
    assert rev["value"] > 800_000            # a full month, not a near-zero tail
    assert 3.5 < score["value"] < 5.0        # real avg review score, not the tail


def test_briefing_ranks_movers_and_roots_cause():
    b = generate_briefing()
    # what_changed is ranked by significance; the top mover has a narrative.
    assert b["what_changed"]
    assert all("narrative" in w for w in b["what_changed"])


def test_briefing_endpoint(client):
    j = client.get("/briefing?connection_id=demo").json()
    assert j["available"]
    assert "metrics" in j and "watchouts" in j


def test_briefing_unavailable_without_timeseries(client):
    import io
    up = client.post(
        "/connections/upload",
        files={"files": ("flat.csv", io.BytesIO(b"a,b\n1,2\n3,4\n"), "text/csv")},
        data={"name": "flat"}).json()
    j = client.get(f"/briefing?connection_id={up['connection_id']}").json()
    assert not j["available"]
