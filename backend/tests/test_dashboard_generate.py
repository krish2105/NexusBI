"""NL → dashboard: describe a dashboard, get a composed multi-tile board."""
import pytest
from fastapi.testclient import TestClient

from app.agents.dashboard_planner import plan_dashboard
from app.config import settings
from app.main import app

DEMO_URL = settings.demo_target_url


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_theme_detection():
    assert plan_dashboard("a delivery dashboard", DEMO_URL).theme == "delivery"
    assert plan_dashboard("customer retention", DEMO_URL).theme == "customer"
    assert plan_dashboard("revenue overview", DEMO_URL).theme == "sales"
    assert plan_dashboard("exec board", DEMO_URL).theme == "executive"


def test_scope_detection_applies_to_plan():
    p = plan_dashboard("sales dashboard for the North region", DEMO_URL)
    assert p.scope_label == "North"
    assert p.scope_filters


def test_generate_dashboard_composes_tiles(client):
    r = client.post("/dashboards/generate", json={
        "description": "an executive overview", "connection_id": "demo"}).json()
    assert r["tile_count"] >= 4
    assert r["title"]
    # tiles carry real results (chart + rows)
    assert all("result" in t and t["result"]["chart_spec"] for t in r["tiles"])
    # the created dashboard is loadable and has the pinned items
    dash = client.get(f"/dashboards/{r['dashboard_id']}?live=false").json()
    assert len(dash["items"]) == r["tile_count"]


def test_generate_scoped_dashboard_applies_filter(client):
    r = client.post("/dashboards/generate", json={
        "description": "revenue dashboard for the North region",
        "connection_id": "demo"}).json()
    assert r["scope"] == "North"
    # every tile's SQL must carry the North scope filter
    assert all("North" in (t["result"]["sql"] or "") for t in r["tiles"])
