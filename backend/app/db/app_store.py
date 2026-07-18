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
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, title TEXT,
  created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS queries (
  id TEXT PRIMARY KEY, user_id TEXT, connection_id TEXT NOT NULL,
  question TEXT NOT NULL, sql TEXT, confidence TEXT,
  assumptions TEXT, result_meta TEXT, payload TEXT, created_at REAL NOT NULL,
  conversation_id TEXT, turn_index INTEGER, context TEXT
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
CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY, query_id TEXT NOT NULL, connection_id TEXT,
  question TEXT, sql TEXT, rating TEXT NOT NULL, note TEXT, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS monitors (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, question TEXT NOT NULL,
  connection_id TEXT NOT NULL, schedule TEXT, enabled INTEGER NOT NULL,
  last_run_at REAL, last_status TEXT, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, monitor_name TEXT,
  severity TEXT NOT NULL, message TEXT NOT NULL, metric REAL, detail TEXT,
  acknowledged INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL
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
            # Lightweight migration: add conversation columns to a pre-existing
            # queries table (older app DBs created before multi-turn support).
            existing = {r[1] for r in con.execute("PRAGMA table_info(queries)")}
            for col, decl in (("conversation_id", "TEXT"),
                              ("turn_index", "INTEGER"),
                              ("context", "TEXT")):
                if col not in existing:
                    con.execute(f"ALTER TABLE queries ADD COLUMN {col} {decl}")

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

    # --- conversations (multi-turn threads) ---
    def create_conversation(self, connection_id: str,
                            title: str | None = None) -> dict:
        cid = _uid()
        with self._con() as con:
            con.execute("INSERT INTO conversations(id,connection_id,title,"
                        "created_at,updated_at) VALUES(?,?,?,?,?)",
                        (cid, connection_id, title, _now(), _now()))
        return {"id": cid, "connection_id": connection_id, "title": title}

    def get_conversation(self, conversation_id: str) -> dict | None:
        with self._con() as con:
            c = con.execute("SELECT * FROM conversations WHERE id=?",
                            (conversation_id,)).fetchone()
        if not c:
            return None
        out = dict(c)
        out["turns"] = self.list_turns(conversation_id)
        return out

    def list_conversations(self, connection_id: str | None = None,
                          limit: int = 50) -> list[dict]:
        with self._con() as con:
            if connection_id:
                rows = con.execute(
                    "SELECT * FROM conversations WHERE connection_id=? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (connection_id, limit)).fetchall()
            else:
                rows = con.execute("SELECT * FROM conversations "
                                   "ORDER BY updated_at DESC LIMIT ?",
                                   (limit,)).fetchall()
        return [dict(r) for r in rows]

    def list_turns(self, conversation_id: str) -> list[dict]:
        """Ordered turns in a thread, each with its full result payload."""
        with self._con() as con:
            rows = con.execute(
                "SELECT * FROM queries WHERE conversation_id=? "
                "ORDER BY turn_index ASC, created_at ASC",
                (conversation_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("assumptions", "result_meta", "payload", "context"):
                d[k] = json.loads(d[k]) if d.get(k) else None
            out.append(d)
        return out

    def conversation_context(self, conversation_id: str) -> list[dict]:
        """Compact per-turn context (question + plan + result summary) used by
        the follow-up resolver — oldest first."""
        return [{"question": t["question"], "sql": t.get("sql"),
                 "context": t.get("context") or {}}
                for t in self.list_turns(conversation_id)]

    def next_turn_index(self, conversation_id: str) -> int:
        with self._con() as con:
            r = con.execute("SELECT COALESCE(MAX(turn_index),-1)+1 FROM queries "
                            "WHERE conversation_id=?", (conversation_id,)).fetchone()
        return int(r[0])

    # --- queries / history ---
    def save_query(self, connection_id: str, question: str, sql: str | None,
                   confidence: str | None, assumptions: list | None,
                   result_meta: dict | None, payload: dict | None,
                   user_id: str | None = None, query_id: str | None = None,
                   conversation_id: str | None = None,
                   turn_index: int | None = None,
                   context: dict | None = None) -> str:
        qid = query_id or _uid()
        with self._con() as con:
            con.execute(
                "INSERT OR REPLACE INTO queries(id,user_id,connection_id,question,"
                "sql,confidence,assumptions,result_meta,payload,created_at,"
                "conversation_id,turn_index,context) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (qid, user_id, connection_id, question, sql, confidence,
                 json.dumps(assumptions or []), json.dumps(result_meta or {}),
                 json.dumps(payload or {}), _now(),
                 conversation_id, turn_index,
                 json.dumps(context) if context is not None else None))
            if conversation_id:
                con.execute("UPDATE conversations SET updated_at=? WHERE id=?",
                            (_now(), conversation_id))
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


    # --- feedback (👍/👎) ---
    def add_feedback(self, query_id: str, rating: str, note: str | None = None,
                     connection_id: str | None = None, question: str | None = None,
                     sql: str | None = None) -> str:
        fid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO feedback(id,query_id,connection_id,question,sql,rating,"
                "note,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (fid, query_id, connection_id, question, sql, rating, note, _now()))
        return fid

    def feedback_stats(self) -> dict:
        with self._con() as con:
            up = con.execute("SELECT COUNT(*) FROM feedback WHERE rating='up'").fetchone()[0]
            down = con.execute("SELECT COUNT(*) FROM feedback WHERE rating='down'").fetchone()[0]
        total = up + down
        return {"up": up, "down": down, "total": total,
                "satisfaction_rate": round(up / total, 4) if total else None}

    def vetted_examples(self, limit: int = 20) -> list[dict]:
        """👍'd answers become verified (question -> SQL) few-shot examples."""
        with self._con() as con:
            rows = con.execute(
                "SELECT DISTINCT question, sql FROM feedback WHERE rating='up' "
                "AND sql IS NOT NULL ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    # --- monitors ---
    def create_monitor(self, name: str, question: str, connection_id: str,
                       schedule: str | None = None) -> dict:
        mid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO monitors(id,name,question,connection_id,schedule,"
                "enabled,created_at) VALUES(?,?,?,?,?,?,?)",
                (mid, name, question, connection_id, schedule, 1, _now()))
        return self.get_monitor(mid)

    def get_monitor(self, mid: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM monitors WHERE id=?", (mid,)).fetchone()
        return dict(r) if r else None

    def list_monitors(self, enabled_only: bool = False) -> list[dict]:
        with self._con() as con:
            q = "SELECT * FROM monitors"
            if enabled_only:
                q += " WHERE enabled=1"
            rows = con.execute(q + " ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def mark_monitor_run(self, mid: str, status: str) -> None:
        with self._con() as con:
            con.execute("UPDATE monitors SET last_run_at=?, last_status=? WHERE id=?",
                        (_now(), status, mid))

    def set_monitor_enabled(self, mid: str, enabled: bool) -> None:
        with self._con() as con:
            con.execute("UPDATE monitors SET enabled=? WHERE id=?",
                        (int(enabled), mid))

    def delete_monitor(self, mid: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM monitors WHERE id=?", (mid,))

    # --- alerts ---
    def add_alert(self, monitor_id: str, monitor_name: str, severity: str,
                  message: str, metric: float | None = None,
                  detail: dict | None = None) -> str:
        aid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO alerts(id,monitor_id,monitor_name,severity,message,"
                "metric,detail,acknowledged,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (aid, monitor_id, monitor_name, severity, message, metric,
                 json.dumps(detail or {}), 0, _now()))
        return aid

    def list_alerts(self, limit: int = 100) -> list[dict]:
        with self._con() as con:
            rows = con.execute("SELECT * FROM alerts ORDER BY created_at DESC "
                               "LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d["detail"]) if d.get("detail") else {}
            out.append(d)
        return out

    def acknowledge_alert(self, aid: str) -> None:
        with self._con() as con:
            con.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (aid,))


_store: AppStore | None = None


def get_store() -> AppStore:
    global _store
    if _store is None:
        _store = AppStore()
    return _store
