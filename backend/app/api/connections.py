"""Data-source connection + semantic catalog + glossary endpoints.

Creating a connection is hardened: the DSN is SSRF-screened, *verified* read-only
by probing the engine, and encrypted before it is stored. Non-demo connections
are scoped to the authenticated user.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (DEMO_CONNECTION_ID, authorize_connection,
                          get_current_user, require_user, resolve_connection_url)
from app.api.schemas import ConnectionRequest, GlossaryRequest
from app.config import settings
from app.core.connguard import check_connection
from app.core.crypto import encrypt
from app.db.app_store import get_store
from app.db.target_pool import TargetPool
from app.rag.catalog import build_catalog

router = APIRouter(tags=["connections"])


@router.post("/connections")
def create_connection(req: ConnectionRequest, user: dict | None = Depends(require_user)):
    store = get_store()
    url = req.target_url or settings.demo_target_url

    # Free-tier connection cap (Pro is uncapped; anonymous/demo use isn't metered).
    if user:
        from app.core.plans import check_connection_quota
        check_connection_quota(user["id"])

    # SSRF screen + engine-verified read-only check before we accept anything.
    check = check_connection(url)
    if not check.ok:
        raise HTTPException(400, f"connection rejected: {check.reason}")

    kind = "sqlite" if url.startswith("sqlite") else "postgres"
    owner = user["id"] if user else "demo-user"
    # DSN is encrypted at rest (may carry credentials).
    conn = store.create_connection(owner, req.name, encrypt(url), kind, is_readonly=True)
    return {"connection_id": conn["id"], "name": conn["name"], "db_kind": kind,
            "is_readonly": True, "verification": check.reason}


@router.get("/connections")
def list_connections(user: dict | None = Depends(get_current_user)):
    conns = get_store().list_connections(user_id=user["id"] if user else None)
    demo = {"id": DEMO_CONNECTION_ID, "name": "Demo — Olist e-commerce",
            "db_kind": "sqlite", "is_readonly": True, "bundled": True}
    return {"connections": [demo] + [
        {"id": c["id"], "name": c["name"], "db_kind": c["db_kind"],
         "is_readonly": bool(c["is_readonly"])} for c in conns]}


@router.get("/connections/{connection_id}/schema")
def get_schema(connection_id: str, user: dict | None = Depends(get_current_user)):
    authorize_connection(connection_id, user)
    url = resolve_connection_url(connection_id)
    catalog = build_catalog(TargetPool(url=url))
    return {
        "connection_id": connection_id,
        "tables": [
            {"name": t.name, "grain": t.grain,
             "columns": [{"name": c.name, "type": c.data_type,
                          "definition": c.definition, "samples": c.samples}
                         for c in t.columns]}
            for t in catalog.tables.values()],
        "glossary": [{"term": g.term, "definition": g.definition,
                      "canonical_sql": g.canonical_sql,
                      "required_tables": g.required_tables, "caveats": g.caveats}
                     for g in catalog.glossary],
    }


@router.post("/connections/{connection_id}/glossary")
def add_glossary(connection_id: str, req: GlossaryRequest,
                 user: dict | None = Depends(get_current_user)):
    authorize_connection(connection_id, user)
    g = get_store().add_glossary_term(connection_id, req.term, req.sql_definition,
                                      req.description)
    return {"id": g["id"], "term": g["term"]}


@router.delete("/connections/{connection_id}")
def delete_connection(connection_id: str, user: dict | None = Depends(require_user)):
    if connection_id == DEMO_CONNECTION_ID:
        raise HTTPException(400, "the bundled demo connection cannot be deleted")
    authorize_connection(connection_id, user)
    get_store().delete_connection(connection_id)
    return {"deleted": connection_id}
