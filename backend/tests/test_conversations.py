"""Multi-turn conversational analysis: session memory, follow-up resolution
(scope / pivot / metric), and "why did it change?" root-cause decomposition."""
import pytest
from fastapi.testclient import TestClient

from app.agents.followup import resolve
from app.agents.planner import plan_question
from app.config import settings
from app.main import app

DEMO_URL = settings.demo_target_url


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --- follow-up resolver (unit) ---
def _history_from(question):
    return [{"question": question, "context": {"plan": plan_question(question)}}]


def test_scope_filter_keeps_dimension():
    hist = _history_from("top 5 product categories by merchandise revenue")
    r = resolve("now just for the North region", hist, DEMO_URL)
    # value-scope, NOT a re-pivot on "region"
    assert r.mode == "refine"
    assert any("North" in c for c in r.changed)
    assert r.seed_plan["dimension"]["label"] == "category_name_en"


def test_pivot_changes_dimension():
    hist = _history_from("top 5 categories by merchandise revenue")
    r = resolve("break it down by state", hist, DEMO_URL)
    assert r.seed_plan["dimension"]["label"] == "state_code"


def test_why_routes_to_rootcause():
    hist = _history_from("show monthly merchandise revenue over time")
    r = resolve("why did it drop?", hist, DEMO_URL)
    assert r.mode == "why"
    assert r.why_context["plan"]["metric"]["alias"] == "merchandise_revenue"


def test_fresh_question_not_treated_as_followup():
    hist = _history_from("total revenue")
    r = resolve("How many delivered orders are there?", hist, DEMO_URL)
    assert not r.is_followup


# --- end-to-end via API ---
def test_conversation_multi_turn_chaining(client):
    conv = client.post("/conversations",
                       json={"connection_id": "demo", "title": "t"}).json()
    cid = conv["id"]

    r1 = client.post("/query/run", json={
        "question": "top 5 product categories by merchandise revenue",
        "connection_id": "demo", "conversation_id": cid}).json()
    assert not r1["blocked"]
    assert r1["suggested_followups"]

    r2 = client.post("/query/run", json={
        "question": "now just for the North region",
        "connection_id": "demo", "conversation_id": cid}).json()
    assert r2["resolved_question"] and "North" in r2["resolved_question"]

    # Turn 3 must INHERIT the North filter and re-pivot by state.
    r3 = client.post("/query/run", json={
        "question": "break it down by state",
        "connection_id": "demo", "conversation_id": cid}).json()
    assert "state_code" in [c for c in r3["columns"]]
    # Northern states only (filter carried forward): PA/AM/etc, never SP.
    states = {row["state_code"] for row in r3["rows"]}
    assert "SP" not in states

    thread = client.get(f"/conversations/{cid}").json()
    assert len(thread["turns"]) == 3


def test_conversation_why_branch(client):
    conv = client.post("/conversations", json={"connection_id": "demo"}).json()
    cid = conv["id"]
    client.post("/query/run", json={
        "question": "show monthly merchandise revenue over time",
        "connection_id": "demo", "conversation_id": cid})
    why = client.post("/query/run", json={
        "question": "why did it change?",
        "connection_id": "demo", "conversation_id": cid}).json()
    assert why["rootcause"] and why["rootcause"]["available"]
    assert why["rootcause"]["contributors"]
    assert "driven mainly by" in why["narrative"]
