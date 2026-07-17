"""LLM path (Groq) — verified with a mocked SDK so the plumbing is proven
correct without needing a live network key. The zero-key deterministic path
remains the default and is covered exhaustively elsewhere; these tests lock in
the *upgrade* path: provider resolution, response parsing, and SQL extraction
from a markdown-fenced LLM completion, including a validator-rejection repair.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.llm.client import LLMClient
from app.rag.catalog import Table, Column
from app.rag.retriever import RetrievedSchema


def _fake_groq_response(content: str):
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    return SimpleNamespace(choices=[choice])


@pytest.fixture(autouse=True)
def _reset_llm_singleton():
    """`get_llm()` caches a module-level singleton; reset it around every test
    in this file so provider resolution is fresh regardless of test order or
    what other test modules resolved earlier in the same session."""
    import app.llm.client as llm_module

    llm_module._client = None
    yield
    llm_module._client = None


@pytest.fixture
def groq_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_fake_key")
    monkeypatch.setattr(settings, "llm_provider", "auto")
    yield


def test_provider_resolves_to_groq_when_key_set(groq_key):
    client = LLMClient()
    assert client.provider == "groq"
    assert client.is_llm


def test_provider_is_deterministic_with_no_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "ollama_base_url", None)
    monkeypatch.setattr(settings, "llm_provider", "auto")
    client = LLMClient()
    assert client.provider == "deterministic"
    assert not client.is_llm


def test_groq_complete_parses_response(groq_key):
    with patch("groq.Groq") as MockGroq:
        instance = MockGroq.return_value
        instance.chat.completions.create.return_value = _fake_groq_response(
            "SELECT COUNT(*) AS n FROM orders LIMIT 10000")
        client = LLMClient()
        resp = client.complete("system prompt", "user prompt")
        assert resp.provider == "groq"
        assert "SELECT" in resp.text
        # model + messages were passed through correctly
        _, kwargs = instance.chat.completions.create.call_args
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][1]["content"] == "user prompt"


def test_generate_sql_uses_llm_and_strips_markdown_fence(groq_key):
    from app.agents.sql_generator import generate_sql

    fenced = "```sql\nSELECT COUNT(*) AS order_count FROM orders LIMIT 10000;\n```"
    schema = RetrievedSchema(
        tables=[Table("orders", "one row per order",
                      [Column("order_id", "TEXT", False)])],
        glossary=[])
    with patch("groq.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = (
            _fake_groq_response(fenced))
        out = generate_sql("How many orders are there?", schema,
                           {"assumptions": [], "intent_summary": "count orders"})
        assert out["generator"] == "groq"
        assert out["sql"].strip().upper().startswith("SELECT")
        assert "```" not in out["sql"]


def test_generate_sql_falls_back_deterministically_on_llm_error(groq_key):
    from app.agents.sql_generator import generate_sql

    schema = RetrievedSchema(
        tables=[Table("orders", "one row per order",
                      [Column("order_id", "TEXT", False)])],
        glossary=[])
    with patch("groq.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.side_effect = (
            ConnectionError("network down"))
        out = generate_sql("How many orders are there?", schema,
                           {"assumptions": [], "intent_summary": "count orders",
                            "metric": {"expr": "COUNT(*)", "base": "orders",
                                      "alias": "order_count"},
                            "dimension": None, "shape": "scalar", "top_n": None,
                            "filters": []})
        assert out["generator"] == "deterministic"
        assert "SELECT" in out["sql"].upper()


def test_repair_sql_uses_llm_with_validation_feedback(groq_key):
    from app.agents.sql_generator import repair_sql

    schema = RetrievedSchema(
        tables=[Table("orders", "one row per order",
                      [Column("order_id", "TEXT", False)])],
        glossary=[])
    with patch("groq.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = (
            _fake_groq_response("SELECT order_id FROM orders LIMIT 10000"))
        out = repair_sql("orders", schema, {"assumptions": []},
                         errors=["column 'x' does not exist"])
        assert out["generator"] == "groq"
        assert "order_id" in out["sql"]
        _, kwargs = MockGroq.return_value.chat.completions.create.call_args
        assert "REJECTED" in kwargs["messages"][1]["content"]
