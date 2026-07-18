"""Account — plan, usage snapshot, and BYO-LLM-key management (Phase 3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import settings
from app.core.crypto import encrypt
from app.core.plans import is_pro, usage_snapshot
from app.db.app_store import get_store

router = APIRouter(tags=["account"])


class ByoKeyRequest(BaseModel):
    provider: str = "groq"
    key: str = Field(min_length=10, max_length=400)


def _require(user: dict | None) -> dict:
    if not user:
        raise HTTPException(401, "authentication required")
    return user


@router.get("/account")
def account(user: dict | None = Depends(get_current_user)):
    user = _require(user)
    return {"user": {"id": user["id"], "email": user["email"]},
            "usage": usage_snapshot(user["id"])}


@router.post("/account/llm-key")
def set_llm_key(req: ByoKeyRequest, user: dict | None = Depends(get_current_user)):
    """Store a BYO LLM key (encrypted at rest). A Pro feature — allowed for any
    authed user when billing is disabled (self-host/dev)."""
    user = _require(user)
    if req.provider != "groq":
        raise HTTPException(422, "only 'groq' is supported for BYO keys today")
    store = get_store()
    if settings.billing_enabled and not is_pro(store.get_user(user["id"])):
        raise HTTPException(402, {"error": "pro_required",
                                  "detail": "BYO LLM key is a Pro feature."})
    store.set_byo_llm_key(user["id"], encrypt(req.key))
    store.append_audit("account.llm_key_set", actor=user["id"], verdict="ALLOW")
    return {"ok": True, "provider": req.provider}


@router.delete("/account/llm-key")
def clear_llm_key(user: dict | None = Depends(get_current_user)):
    user = _require(user)
    get_store().set_byo_llm_key(user["id"], None)
    return {"ok": True}
