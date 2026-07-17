"""Observability — optional Langfuse tracing over the agent graph.

Free-tier optional: with no ``LANGFUSE_PUBLIC_KEY``/``LANGFUSE_SECRET_KEY`` set,
every call here is a no-op and the app runs exactly as before. When configured,
each query gets one root trace (``QueryTrace``) with a child span per agent node
(planner, schema_retriever, sql_generator, sql_validator, executor, forecaster,
anomaly, narrator) carrying latency, generator used, and safety verdict — so
every question is fully inspectable in the Langfuse dashboard.

Spans are explicitly parented via ``trace_context={"trace_id": ...}`` rather than
relying on OpenTelemetry contextvar propagation, because ``run_analysis`` is a
generator streamed through FastAPI's SSE response (which may resume it off the
thread that started it) — explicit linking is correct regardless of which thread
resumes the generator.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import settings


@lru_cache(maxsize=1)
def _client():
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:  # noqa: BLE001 - tracing must never break the app
        return None


def is_enabled() -> bool:
    return _client() is not None


class _NullSpan:
    def end(self, **_kw) -> None:
        pass

    def update(self, **_kw) -> None:
        pass


class QueryTrace:
    """Root trace for one full analysis run. Safe to use even when tracing is
    disabled — every method degrades to a no-op."""

    def __init__(self, query_id: str, question: str, connection_id: str):
        self.client = _client()
        self.enabled = self.client is not None
        self.trace_id: str | None = None
        self._cm = None
        self._root_span = None
        if not self.enabled:
            return
        try:
            self._cm = self.client.start_as_current_observation(
                name="nexus.query", as_type="span",
                input={"question": question},
                metadata={"query_id": query_id, "connection_id": connection_id},
            )
            self._root_span = self._cm.__enter__()
            self.trace_id = self.client.get_current_trace_id()
        except Exception:  # noqa: BLE001
            self.enabled = False

    def node_span(self, name: str, **metadata: Any):
        """Start a child span for one graph node; call ``.end(...)`` on it."""
        if not self.enabled:
            return _NullSpan()
        try:
            return self.client.start_observation(
                name=f"node.{name}", as_type="span", metadata=metadata,
                trace_context={"trace_id": self.trace_id} if self.trace_id else None,
            )
        except Exception:  # noqa: BLE001
            return _NullSpan()

    def finish(self, output: Any = None) -> None:
        """Close the trace. Does NOT flush — the SDK batches and exports in the
        background on its own interval; flushing per-request would add network
        latency to every query. Call ``flush()`` once, at app shutdown."""
        if not self.enabled:
            return
        try:
            if output is not None and self._root_span is not None:
                self._root_span.update(output=output)
            self._cm.__exit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass

    def url(self) -> str | None:
        if not self.enabled or not self.trace_id:
            return None
        try:
            return self.client.get_trace_url(trace_id=self.trace_id)
        except Exception:  # noqa: BLE001
            return None


def flush() -> None:
    """Flush any pending traces. Call once at app shutdown, not per-request."""
    client = _client()
    if client is not None:
        try:
            client.flush()
        except Exception:  # noqa: BLE001
            pass
