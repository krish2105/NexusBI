"""NL query endpoints — submit, SSE stream of live agent steps, fetch result."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.graph import run_analysis
from app.api.deps import (authorize_connection, get_current_user, rate_limit,
                          resolve_connection_url)
from app.api.schemas import QueryRequest
from app.db.app_store import get_store

router = APIRouter(tags=["query"])


@router.post("/query", dependencies=[Depends(rate_limit)])
def submit_query(req: QueryRequest, user: dict | None = Depends(get_current_user)):
    """Register a question and return a query_id to stream."""
    authorize_connection(req.connection_id, user)
    store = get_store()
    qid = store.save_query(req.connection_id, req.question, None, None, [], {},
                           {"status": "pending"},
                           conversation_id=req.conversation_id)
    return {"query_id": qid, "stream_url": f"/query/{qid}/stream"}


def _sse(event: dict) -> str:
    name = event.get("node", "message")
    return f"event: {name}\ndata: {json.dumps(event, default=str)}\n\n"


@router.get("/query/{query_id}/stream")
def stream_query(query_id: str):
    """Server-Sent Events: each agent node transition as it happens."""
    store = get_store()
    q = store.get_query(query_id)
    if not q:
        raise HTTPException(404, "unknown query_id")
    question = q["question"]
    url = resolve_connection_url(q["connection_id"])

    def gen():
        for ev in run_analysis(question, connection_id=q["connection_id"],
                               connection_url=url, query_id=query_id, persist=True,
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
    store = get_store()
    qid = store.save_query(req.connection_id, req.question, None, None, [], {}, {},
                           conversation_id=req.conversation_id)
    url = resolve_connection_url(req.connection_id)
    final = None
    for ev in run_analysis(req.question, connection_id=req.connection_id,
                           connection_url=url, query_id=qid, persist=True,
                           conversation_id=req.conversation_id):
        if ev.get("node") == "final":
            final = ev["result"]
    return final or {"error": "no result"}


@router.get("/query/{query_id}")
def get_query(query_id: str):
    q = get_store().get_query(query_id)
    if not q:
        raise HTTPException(404, "unknown query_id")
    return {"query_id": q["id"], "question": q["question"], "sql": q["sql"],
            "confidence": q["confidence"], "assumptions": q.get("assumptions"),
            "result_meta": q.get("result_meta"), "result": q.get("payload"),
            "created_at": q["created_at"]}
