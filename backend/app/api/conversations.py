"""Conversation (multi-turn thread) endpoints.

A conversation groups turns so follow-ups ("now drill into the North region",
"why did it drop?") resolve against prior context. Create a thread, then pass its
id to /query or /query/run.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import authorize_connection, get_current_user
from app.api.schemas import ConversationRequest
from app.db.app_store import get_store

router = APIRouter(tags=["conversations"])


@router.post("/conversations")
def create_conversation(req: ConversationRequest,
                        user: dict | None = Depends(get_current_user)):
    authorize_connection(req.connection_id, user)
    return get_store().create_conversation(req.connection_id, req.title)


@router.get("/conversations")
def list_conversations(connection_id: str | None = None, limit: int = 50):
    return {"conversations": get_store().list_conversations(connection_id, limit)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    conv = get_store().get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "unknown conversation")
    # Expose each turn's final result payload for thread replay.
    turns = [{"query_id": t["id"], "question": t["question"],
              "turn_index": t.get("turn_index"),
              "result": t.get("payload"), "created_at": t["created_at"]}
             for t in conv["turns"]]
    return {"id": conv["id"], "connection_id": conv["connection_id"],
            "title": conv.get("title"), "turns": turns}
