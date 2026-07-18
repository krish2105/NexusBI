"""NL query endpoints — submit, SSE stream of live agent steps, fetch result."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.graph import run_analysis
from app.api.deps import (authorize_connection, get_current_user, rate_limit,
                          resolve_connection_url)
from app.api.schemas import QueryRequest
from app.core.plans import byo_llm_key_for, check_query_quota
from app.db.app_store import get_store
from app.llm.client import use_groq_key

router = APIRouter(tags=["query"])

DEMO = "demo"


def _meter(user: dict | None, connection_id: str) -> None:
    """Enforce + record Free-tier query usage. The open demo is never metered,
    and anonymous use (no account) isn't either."""
    if user and connection_id != DEMO:
        check_query_quota(user["id"])
        get_store().record_usage(user["id"], connection_id)


@router.post("/query", dependencies=[Depends(rate_limit)])
def submit_query(req: QueryRequest, user: dict | None = Depends(get_current_user)):
    """Register a question and return a query_id to stream."""
    authorize_connection(req.connection_id, user)
    _meter(user, req.connection_id)
    store = get_store()
    qid = store.save_query(req.connection_id, req.question, None, None, [], {},
                           {"status": "pending"},
                           conversation_id=req.conversation_id)
    return {"query_id": qid, "stream_url": f"/query/{qid}/stream"}


def _sse(event: dict) -> str:
    name = event.get("node", "message")
    return f"event: {name}\ndata: {json.dumps(event, default=str)}\n\n"


def _is_pending(payload) -> bool:
    """A query still needs execution only until its result payload is written."""
    return not payload or (isinstance(payload, dict)
                           and payload.get("status") == "pending")


@router.get("/query/{query_id}/stream", dependencies=[Depends(rate_limit)])
def stream_query(query_id: str, user: dict | None = Depends(get_current_user)):
    """Server-Sent Events: each agent node transition as it happens.

    Runs the pipeline only for a query that hasn't produced a result yet; a query
    that already completed is **replayed** from its stored result rather than
    re-executed — closing the cost-amplification / DoS vector of re-running the
    whole agent pipeline on every GET. Rate-limited, and (under REQUIRE_AUTH)
    scoped to the query's connection so it isn't an IDOR read of another tenant."""
    store = get_store()
    q = store.get_query(query_id)
    if not q:
        raise HTTPException(404, "unknown query_id")
    authorize_connection(q["connection_id"], user)
    question = q["question"]

    if not _is_pending(q.get("payload")):
        def replay():
            yield _sse({"node": "start", "status": "ok", "query_id": query_id,
                        "replayed": True})
            yield _sse({"node": "final", "status": "ok", "result": q["payload"],
                        "replayed": True})
            yield "event: done\ndata: {}\n\n"
        return StreamingResponse(replay(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    url = resolve_connection_url(q["connection_id"])
    byo = byo_llm_key_for(user["id"] if user else None)

    def gen():
        with use_groq_key(byo):  # a Pro BYO key runs generation on their account
            for ev in run_analysis(question, connection_id=q["connection_id"],
                                   connection_url=url, query_id=query_id,
                                   persist=True,
                                   conversation_id=q.get("conversation_id")):
                yield _sse(ev)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.post("/query/run", dependencies=[Depends(rate_limit)])
def run_query_sync(req: QueryRequest, user: dict | None = Depends(get_current_user)):
    """Synchronous convenience: run the full pipeline and return the final result."""
    authorize_connection(req.connection_id, user)
    _meter(user, req.connection_id)
    store = get_store()
    qid = store.save_query(req.connection_id, req.question, None, None, [], {}, {},
                           conversation_id=req.conversation_id)
    url = resolve_connection_url(req.connection_id)
    byo = byo_llm_key_for(user["id"] if user else None)
    final = None
    with use_groq_key(byo):
        for ev in run_analysis(req.question, connection_id=req.connection_id,
                               connection_url=url, query_id=qid, persist=True,
                               conversation_id=req.conversation_id):
            if ev.get("node") == "final":
                final = ev["result"]
    return final or {"error": "no result"}


@router.get("/query/{query_id}")
def get_query(query_id: str, user: dict | None = Depends(get_current_user)):
    q = get_store().get_query(query_id)
    if not q:
        raise HTTPException(404, "unknown query_id")
    authorize_connection(q["connection_id"], user)  # not an IDOR read of another tenant
    return {"query_id": q["id"], "question": q["question"], "sql": q["sql"],
            "confidence": q["confidence"], "assumptions": q.get("assumptions"),
            "result_meta": q.get("result_meta"), "result": q.get("payload"),
            "created_at": q["created_at"]}
