"""Data-source connection + semantic catalog + glossary endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import DEMO_CONNECTION_ID, resolve_connection_url
from app.api.schemas import ConnectionRequest, GlossaryRequest
from app.config import settings
from app.db.app_store import get_store
from app.db.target_pool import TargetPool
from app.rag.catalog import build_catalog

router = APIRouter(tags=["connections"])


def _validate_readonly(url: str) -> tuple[bool, str]:
    """A connection must be usable AND refuse writes before we accept it."""
    pool = TargetPool(url=url)
    try:
        pool.execute("SELECT 1 AS ok LIMIT 1")
    except Exception as e:  # noqa: BLE001
        return False, f"could not connect / query: {e}"
    return True, "ok"


@router.post("/connections")
def create_connection(req: ConnectionRequest):
    store = get_store()
    url = req.target_url or settings.demo_target_url
    ok, msg = _validate_readonly(url)
    if not ok:
        raise HTTPException(400, msg)
    kind = "sqlite" if url.startswith("sqlite") else "postgres"
    conn = store.create_connection("demo-user", req.name, url, kind, is_readonly=True)
    return {"connection_id": conn["id"], "name": conn["name"], "db_kind": kind,
            "is_readonly": True}


@router.get("/connections")
def list_connections():
    conns = get_store().list_connections()
    demo = {"id": DEMO_CONNECTION_ID, "name": "Demo — Olist e-commerce",
            "db_kind": "sqlite", "is_readonly": True, "bundled": True}
    return {"connections": [demo] + [
        {"id": c["id"], "name": c["name"], "db_kind": c["db_kind"],
         "is_readonly": bool(c["is_readonly"])} for c in conns]}


@router.get("/connections/{connection_id}/schema")
def get_schema(connection_id: str):
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
def add_glossary(connection_id: str, req: GlossaryRequest):
    g = get_store().add_glossary_term(connection_id, req.term, req.sql_definition,
                                      req.description)
    return {"id": g["id"], "term": g["term"]}


@router.delete("/connections/{connection_id}")
def delete_connection(connection_id: str):
    if connection_id == DEMO_CONNECTION_ID:
        raise HTTPException(400, "the bundled demo connection cannot be deleted")
    get_store().delete_connection(connection_id)
    return {"deleted": connection_id}
