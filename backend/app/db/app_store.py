"""App-metadata store — connections, query history, dashboards, audit log.

Kept deliberately dependency-light (stdlib sqlite3) so the project runs on the
free tier with zero setup. The DSN is configurable (``app_db_url``); point it at
a Supabase Postgres URL in production and swap the driver in one place.

The app DB is strictly separate from the target/user DB (target_pool.py).
The ``audit_log`` table is append-only by contract: this module exposes only
insert + read for it — never update or delete.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
  api_key_hash TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS connections (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
  target_url TEXT NOT NULL, db_kind TEXT NOT NULL, is_readonly INTEGER NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS glossary (
  id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, term TEXT NOT NULL,
  sql_definition TEXT, description TEXT, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS queries (
  id TEXT PRIMARY KEY, user_id TEXT, connection_id TEXT NOT NULL,
  question TEXT NOT NULL, sql TEXT, confidence TEXT,
  assumptions TEXT, result_meta TEXT, payload TEXT, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboards (
  id TEXT PRIMARY KEY, user_id TEXT, name TEXT NOT NULL,
  layout TEXT, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboard_items (
  id TEXT PRIMARY KEY, dashboard_id TEXT NOT NULL, query_id TEXT NOT NULL,
  position TEXT, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY, actor TEXT, action TEXT NOT NULL, sql_text TEXT,
  row_count INTEGER, latency_ms REAL, verdict TEXT, detail TEXT,
  created_at REAL NOT NULL
);
"""


def _now() -> float:
    return time.time()


def _uid() -> str:
    return uuid.uuid4().hex


class AppStore:
    def __init__(self, url: str | None = None):
        self.url = url or settings.app_db_url
        assert self.url.startswith("sqlite:///"), (
            "AppStore ships with a SQLite driver; set a Postgres adapter for prod")
        self.path = Path(self.url.replace("sqlite:///", "", 1))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_schema(self) -> None:
        with self._con() as con:
            con.executescript(_SCHEMA)

    # --- users ---
    def create_user(self, email: str, api_key_hash: str) -> dict:
        uid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO users(id,email,api_key_hash,created_at) VALUES(?,?,?,?)",
                (uid, email, api_key_hash, _now()))
        return {"id": uid, "email": email}

    def get_user_by_email(self, email: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(r) if r else None

    def list_users(self) -> list[dict]:
        with self._con() as con:
            return [dict(r) for r in con.execute("SELECT * FROM users").fetchall()]

    # --- connections ---
    def create_connection(self, user_id: str, name: str, target_url: str,
                          db_kind: str, is_readonly: bool = True) -> dict:
        cid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO connections(id,user_id,name,target_url,db_kind,"
                "is_readonly,created_at) VALUES(?,?,?,?,?,?,?)",
                (cid, user_id, name, target_url, db_kind, int(is_readonly), _now()))
        return self.get_connection(cid)

    def get_connection(self, cid: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM connections WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None

    def list_connections(self, user_id: str | None = None) -> list[dict]:
        with self._con() as con:
            if user_id:
                rows = con.execute("SELECT * FROM connections WHERE user_id=? "
                                   "ORDER BY created_at DESC", (user_id,)).fetchall()
            else:
                rows = con.execute("SELECT * FROM connections "
                                   "ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_connection(self, cid: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM connections WHERE id=?", (cid,))

    # --- glossary ---
    def add_glossary_term(self, connection_id: str, term: str,
                          sql_definition: str | None, description: str | None) -> dict:
        gid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO glossary(id,connection_id,term,sql_definition,"
                "description,created_at) VALUES(?,?,?,?,?,?)",
                (gid, connection_id, term, sql_definition, description, _now()))
        return {"id": gid, "term": term}

    def list_glossary(self, connection_id: str) -> list[dict]:
        with self._con() as con:
            rows = con.execute("SELECT * FROM glossary WHERE connection_id=? "
                               "ORDER BY term", (connection_id,)).fetchall()
        return [dict(r) for r in rows]

    # --- queries / history ---
    def save_query(self, connection_id: str, question: str, sql: str | None,
                   confidence: str | None, assumptions: list | None,
                   result_meta: dict | None, payload: dict | None,
                   user_id: str | None = None, query_id: str | None = None) -> str:
        qid = query_id or _uid()
        with self._con() as con:
            con.execute(
                "INSERT OR REPLACE INTO queries(id,user_id,connection_id,question,"
                "sql,confidence,assumptions,result_meta,payload,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (qid, user_id, connection_id, question, sql, confidence,
                 json.dumps(assumptions or []), json.dumps(result_meta or {}),
                 json.dumps(payload or {}), _now()))
        return qid

    def get_query(self, qid: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM queries WHERE id=?", (qid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        for k in ("assumptions", "result_meta", "payload"):
            d[k] = json.loads(d[k]) if d.get(k) else None
        return d

    def list_queries(self, limit: int = 50, user_id: str | None = None) -> list[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT id,question,sql,confidence,connection_id,created_at "
                "FROM queries ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # --- dashboards ---
    def create_dashboard(self, name: str, user_id: str | None = None) -> dict:
        did = _uid()
        with self._con() as con:
            con.execute("INSERT INTO dashboards(id,user_id,name,layout,created_at) "
                        "VALUES(?,?,?,?,?)", (did, user_id, name, json.dumps({}), _now()))
        return {"id": did, "name": name}

    def list_dashboards(self) -> list[dict]:
        with self._con() as con:
            rows = con.execute("SELECT * FROM dashboards ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def pin_to_dashboard(self, dashboard_id: str, query_id: str,
                         position: dict | None = None) -> dict:
        iid = _uid()
        with self._con() as con:
            con.execute("INSERT INTO dashboard_items(id,dashboard_id,query_id,"
                        "position,created_at) VALUES(?,?,?,?,?)",
                        (iid, dashboard_id, query_id, json.dumps(position or {}), _now()))
        return {"id": iid, "dashboard_id": dashboard_id, "query_id": query_id}

    def get_dashboard(self, dashboard_id: str) -> dict | None:
        with self._con() as con:
            d = con.execute("SELECT * FROM dashboards WHERE id=?",
                            (dashboard_id,)).fetchone()
            if not d:
                return None
            items = con.execute(
                "SELECT di.*, q.question, q.sql FROM dashboard_items di "
                "JOIN queries q ON q.id=di.query_id WHERE di.dashboard_id=? "
                "ORDER BY di.created_at", (dashboard_id,)).fetchall()
        out = dict(d)
        out["items"] = [dict(i) for i in items]
        return out

    # --- audit log (APPEND-ONLY) ---
    def append_audit(self, action: str, *, actor: str | None = None,
                     sql_text: str | None = None, row_count: int | None = None,
                     latency_ms: float | None = None, verdict: str | None = None,
                     detail: dict | None = None) -> str:
        aid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO audit_log(id,actor,action,sql_text,row_count,"
                "latency_ms,verdict,detail,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (aid, actor, action, sql_text, row_count, latency_ms, verdict,
                 json.dumps(detail or {}), _now()))
        return aid

    def list_audit(self, limit: int = 100) -> list[dict]:
        with self._con() as con:
            rows = con.execute("SELECT * FROM audit_log ORDER BY created_at DESC "
                               "LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d["detail"]) if d.get("detail") else {}
            out.append(d)
        return out


_store: AppStore | None = None


def get_store() -> AppStore:
    global _store
    if _store is None:
        _store = AppStore()
    return _store
