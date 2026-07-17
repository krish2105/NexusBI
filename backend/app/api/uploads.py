"""Bring-your-own-data — upload CSV(s) -> instant read-only SQLite warehouse.

Each upload becomes its own connection with its own on-disk SQLite DB. Identifiers
are sanitized, sizes are capped, and the resulting DB is queried through the same
read-only pool + five-layer safety guard as the demo — so an uploaded dataset is
exactly as safe as the bundled one.
"""
from __future__ import annotations

import io
import re
import sqlite3
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import require_user
from app.config import settings, VAR_DIR
from app.core.connguard import check_connection
from app.core.crypto import encrypt
from app.db.app_store import get_store
from app.rag.catalog import invalidate_catalog

router = APIRouter(tags=["connections"])

UPLOAD_DIR = VAR_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_IDENT = re.compile(r"[^a-z0-9_]+")


def _sanitize_ident(name: str, fallback: str) -> str:
    s = _IDENT.sub("_", name.strip().lower()).strip("_")
    if not s or not re.match(r"[a-z_]", s):
        s = f"{fallback}_{s}" if s else fallback
    return s[:63]


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if n in seen:
            seen[n] += 1
            out.append(f"{n}_{seen[n]}")
        else:
            seen[n] = 0
            out.append(n)
    return out


@router.post("/connections/upload")
async def upload_csv(
    files: list[UploadFile] = File(...),
    name: str = Form("My uploaded dataset"),
    user: dict | None = Depends(require_user),
):
    if not files:
        raise HTTPException(400, "no files uploaded")
    if len(files) > settings.max_tables_per_upload:
        raise HTTPException(400, f"at most {settings.max_tables_per_upload} files "
                                 "per upload")

    conn_id = uuid.uuid4().hex
    db_path = UPLOAD_DIR / f"{conn_id}.db"
    con = sqlite3.connect(db_path)
    summary: list[dict] = []
    used_tables: list[str] = []

    try:
        for i, f in enumerate(files):
            if not (f.filename or "").lower().endswith((".csv", ".tsv", ".txt")):
                raise HTTPException(400, f"'{f.filename}': only CSV/TSV files are "
                                         "accepted")
            raw = await f.read()
            if len(raw) > settings.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, f"'{f.filename}' exceeds "
                                         f"{settings.max_upload_mb} MB")
            sep = "\t" if f.filename.lower().endswith(".tsv") else ","
            try:
                df = pd.read_csv(io.BytesIO(raw), sep=sep,
                                 nrows=settings.max_rows_per_table + 1,
                                 low_memory=False)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(400, f"could not parse '{f.filename}': "
                                         f"{str(e)[:100]}")

            truncated = len(df) > settings.max_rows_per_table
            if truncated:
                df = df.iloc[: settings.max_rows_per_table]
            if df.shape[1] > settings.max_columns_per_table:
                df = df.iloc[:, : settings.max_columns_per_table]
            if df.empty or df.shape[1] == 0:
                raise HTTPException(400, f"'{f.filename}' has no usable rows/columns")

            base = Path(f.filename).stem
            table = _sanitize_ident(base, f"table_{i}")
            while table in used_tables:
                table = f"{table}_{i}"
            used_tables.append(table)
            df.columns = _dedupe([_sanitize_ident(str(c), f"col_{j}")
                                  for j, c in enumerate(df.columns)])
            df.to_sql(table, con, index=False, if_exists="replace")
            summary.append({"table": table, "rows": int(len(df)),
                            "columns": list(df.columns), "truncated": truncated})
        con.commit()
    except HTTPException:
        con.close()
        db_path.unlink(missing_ok=True)
        raise
    finally:
        con.close()

    url = f"sqlite:///{db_path}"
    # Same connection-time checks as any other target.
    check = check_connection(url)
    if not check.ok:
        db_path.unlink(missing_ok=True)
        raise HTTPException(400, f"uploaded DB failed safety check: {check.reason}")

    owner = user["id"] if user else "demo-user"
    store = get_store()
    # Register with conn_id == db filename stem for a clean 1:1 mapping.
    _register_with_id(store, conn_id, owner, name, encrypt(url))
    invalidate_catalog(url)

    return {"connection_id": conn_id, "name": name, "db_kind": "sqlite",
            "is_readonly": True, "tables": summary,
            "verification": check.reason}


def _register_with_id(store, conn_id: str, owner: str, name: str, enc_url: str):
    """Insert a connection row with a caller-chosen id (matches the db filename)."""
    import time

    with store._con() as c:  # noqa: SLF001 - internal, same module family
        c.execute(
            "INSERT OR REPLACE INTO connections(id,user_id,name,target_url,db_kind,"
            "is_readonly,created_at) VALUES(?,?,?,?,?,?,?)",
            (conn_id, owner, name, enc_url, "sqlite", 1, time.time()))
    return store.get_connection(conn_id)
