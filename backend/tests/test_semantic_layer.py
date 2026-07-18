"""Semantic layer — governed, certified metric definitions.

Covers the store CRUD, the resolver (name/synonym matching), the safety-verified
API (a bad definition can never be saved), and the end-to-end wiring: a question
that names a governed metric is computed from the *certified* SQL expression and
the result carries the governed-metric badge.
"""
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.agents.semantic import resolve_metric, seed_demo_metrics
from app.db.app_store import AppStore
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def store():
    return AppStore(url=f"sqlite:///{tempfile.mktemp(suffix='.db')}")


# --- store CRUD -------------------------------------------------------------
def test_metric_crud_roundtrip(store):
    m = store.create_metric("c1", name="Revenue", expression="SUM(x)",
                            base_table="t", alias="rev",
                            synonyms=["sales"], description="d", certified=True)
    assert m["certified"] is True and m["synonyms"] == ["sales"]
    assert store.count_metrics("c1") == 1
    got = store.get_metric(m["id"])
    assert got["name"] == "Revenue"
    upd = store.update_metric(m["id"], certified=False, synonyms=["sales", "turnover"])
    assert upd["certified"] is False and "turnover" in upd["synonyms"]
    store.delete_metric(m["id"])
    assert store.count_metrics("c1") == 0


def test_seed_is_idempotent(store):
    n1 = seed_demo_metrics(store, "demo")
    n2 = seed_demo_metrics(store, "demo")
    assert n1 == 9 and n2 == 0
    assert store.count_metrics("demo") == 9
    assert all(m["certified"] for m in store.list_metrics("demo"))


# --- resolver ---------------------------------------------------------------
def test_resolver_matches_name_and_synonym(store):
    seed_demo_metrics(store, "demo")
    ms = store.list_metrics("demo")
    assert resolve_metric("show revenue by category", ms)["governed"]["name"] \
        == "Merchandise Revenue"
    assert resolve_metric("average order value trend", ms)["governed"]["name"] \
        == "Average Order Value"


def test_resolver_prefers_longest_phrase(store):
    """'average order value' must beat the shorter 'orders' synonym."""
    seed_demo_metrics(store, "demo")
    ms = store.list_metrics("demo")
    r = resolve_metric("what is the average order value", ms)
    assert r["governed"]["matched_phrase"] == "average order value"


def test_resolver_returns_none_when_no_metric_named(store):
    seed_demo_metrics(store, "demo")
    assert resolve_metric("list the products table", store.list_metrics("demo")) is None


def test_resolver_shape_drops_into_plan_metric(store):
    seed_demo_metrics(store, "demo")
    r = resolve_metric("total revenue", store.list_metrics("demo"))
    assert set(("expr", "base", "alias", "term")).issubset(r)  # planner-metric shape


# --- API: list + safety-verified create ------------------------------------
def test_list_autoseeds_demo(client):
    j = client.get("/metrics?connection_id=demo").json()
    assert len(j["metrics"]) >= 9
    assert any(m["name"] == "Merchandise Revenue" for m in j["metrics"])


def test_create_valid_metric(client):
    body = {"name": "Late Rate",
            "expression": "ROUND(AVG(orders.delivered_late_flag), 4)",
            "base_table": "orders", "alias": "late_rate",
            "synonyms": ["late rate"], "certified": True}
    r = client.post("/metrics?connection_id=demo", json=body)
    assert r.status_code == 200
    client.delete(f"/metrics/{r.json()['id']}?connection_id=demo")


def test_create_rejects_hallucinated_column(client):
    body = {"name": "Bad", "expression": "SUM(orders.nope_col)",
            "base_table": "orders", "alias": "bad"}
    r = client.post("/metrics?connection_id=demo", json=body)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "unsafe_or_invalid_metric"


def test_create_rejects_sql_injection(client):
    body = {"name": "Evil", "expression": "1); DROP TABLE orders;--",
            "base_table": "orders", "alias": "evil"}
    r = client.post("/metrics?connection_id=demo", json=body)
    assert r.status_code == 400


# --- end-to-end: governed metric drives generation --------------------------
def test_governed_metric_drives_query(client):
    j = client.post("/query/run", json={"question": "revenue by category"}).json()
    assert j["blocked"] is False
    gm = j["governed_metric"]
    assert gm and gm["name"] == "Merchandise Revenue" and gm["certified"] is True
    # the certified expression is what actually ran
    assert "line_merchandise_value" in j["sql"]
