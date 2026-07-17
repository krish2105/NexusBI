"""Observability tracing must be a true no-op when unconfigured, and must never
break or slow down the pipeline even with bad Langfuse credentials."""
from app.agents.graph import run_analysis_collect as run
from app.core.tracing import QueryTrace, is_enabled


def test_tracing_disabled_by_default():
    assert not is_enabled()


def test_query_trace_noop_has_safe_defaults():
    t = QueryTrace("qid", "question", "demo")
    assert not t.enabled
    span = t.node_span("planner", label="x")
    span.update(output={"a": 1}, level="ERROR")   # must not raise
    span.end()                                     # must not raise
    t.finish(output={"blocked": False})            # must not raise
    assert t.url() is None


def test_pipeline_result_has_trace_url_key_even_when_disabled():
    r = run("Total merchandise revenue", persist=False)
    assert "trace_url" in r
    assert r["trace_url"] is None
