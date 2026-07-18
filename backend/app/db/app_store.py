"""App-metadata store — connections, query history, dashboards, audit log.

Runs on **SQLite** by default (stdlib, zero-setup, great for local dev) and on
**Postgres** in production for durability — pick the backend by ``app_db_url``
scheme (``sqlite:///…`` vs ``postgresql://…``). This matters on hosts with an
ephemeral filesystem (e.g. Render's free plan): point ``APP_DB_URL`` at a free
managed Postgres (Supabase/Neon) so users, connections + encrypted DSNs, the
audit log, monitors, feedback, dashboards and history survive a redeploy.

The two dialects share one set of methods via a thin shim (``_Conn`` + ``_to_pg``):
the method bodies write SQLite-flavoured SQL (``?`` params, ``INSERT OR REPLACE``)
and the shim rewrites it for Postgres (``%s`` params, ``ON CONFLICT`` upsert), so
there is exactly one place that knows about dialects.

The app DB is strictly separate from the target/user DB (target_pool.py).
The ``audit_log`` table is append-only by contract: this module exposes only
insert + read for it — never update or delete.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.crypto import decrypt, encrypt


def _load_payload(val: str | None) -> dict | None:
    """Query result payloads (which cache row data / PII) are encrypted at rest.
    ``decrypt`` tolerates legacy plaintext, so old rows still load."""
    if not val:
        return None
    return json.loads(decrypt(val))

# Types are chosen to be valid on BOTH engines: DOUBLE PRECISION (not REAL) so
# epoch timestamps keep full precision on Postgres, where REAL is only 4 bytes;
# SQLite maps DOUBLE PRECISION to its REAL (8-byte) affinity, so it's unchanged there.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
  api_key_hash TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL,
  password_hash TEXT, api_key_id TEXT, plan TEXT NOT NULL DEFAULT 'free',
  stripe_customer_id TEXT, byo_llm_key_enc TEXT
);
CREATE TABLE IF NOT EXISTS connections (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
  target_url TEXT NOT NULL, db_kind TEXT NOT NULL, is_readonly INTEGER NOT NULL,
  created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS glossary (
  id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, term TEXT NOT NULL,
  sql_definition TEXT, description TEXT, created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
  id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, name TEXT NOT NULL,
  expression TEXT NOT NULL, base_table TEXT NOT NULL, alias TEXT NOT NULL,
  synonyms TEXT, description TEXT, certified INTEGER NOT NULL DEFAULT 0,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, title TEXT,
  created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS queries (
  id TEXT PRIMARY KEY, user_id TEXT, connection_id TEXT NOT NULL,
  question TEXT NOT NULL, sql TEXT, confidence TEXT,
  assumptions TEXT, result_meta TEXT, payload TEXT, created_at DOUBLE PRECISION NOT NULL,
  conversation_id TEXT, turn_index INTEGER, context TEXT
);
CREATE TABLE IF NOT EXISTS dashboards (
  id TEXT PRIMARY KEY, user_id TEXT, name TEXT NOT NULL,
  layout TEXT, created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboard_items (
  id TEXT PRIMARY KEY, dashboard_id TEXT NOT NULL, query_id TEXT NOT NULL,
  position TEXT, created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY, actor TEXT, action TEXT NOT NULL, sql_text TEXT,
  row_count INTEGER, latency_ms DOUBLE PRECISION, verdict TEXT, detail TEXT,
  created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY, query_id TEXT NOT NULL, connection_id TEXT,
  question TEXT, sql TEXT, rating TEXT NOT NULL, note TEXT, created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS monitors (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, question TEXT NOT NULL,
  connection_id TEXT NOT NULL, schedule TEXT, enabled INTEGER NOT NULL,
  last_run_at DOUBLE PRECISION, last_status TEXT, created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, monitor_name TEXT,
  severity TEXT NOT NULL, message TEXT NOT NULL, metric DOUBLE PRECISION, detail TEXT,
  acknowledged INTEGER NOT NULL DEFAULT 0, created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, connection_id TEXT,
  created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_usage_user_time ON usage_events(user_id, created_at);
"""


# --- dialect shim: one place that knows SQLite-SQL differs from Postgres-SQL ---
_UPSERT_RE = re.compile(r"INSERT OR REPLACE INTO\s+(\w+)\s*\(([^)]+)\)", re.IGNORECASE)


def _rewrite_upsert(sql: str) -> str:
    """SQLite ``INSERT OR REPLACE`` → Postgres ``INSERT … ON CONFLICT (id) DO UPDATE``.
    The tables that use it are all keyed on ``id``."""
    m = _UPSERT_RE.search(sql)
    if not m:
        return sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
    cols = [c.strip() for c in m.group(2).split(",")]
    setters = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c.lower() != "id")
    sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
    return f"{sql} ON CONFLICT (id) DO UPDATE SET {setters}"


def _to_pg(sql: str) -> str:
    """Translate a SQLite-flavoured statement to Postgres: qmark params → ``%s``
    and ``INSERT OR REPLACE`` → an ``ON CONFLICT`` upsert. (The app-store SQL
    contains no ``%`` or ``?`` literals, so the substitution is safe.)"""
    if "OR REPLACE" in sql:
        sql = _rewrite_upsert(sql)
    return sql.replace("?", "%s")


class _Conn:
    """Uniform connection wrapper over sqlite3 / psycopg2 so the store's methods
    are dialect-agnostic. Commits (or rolls back) and closes on ``with`` exit —
    per-call connections keep us well under managed-Postgres connection caps."""

    def __init__(self, raw, kind: str):
        self._raw = raw
        self._kind = kind

    def execute(self, sql: str, params: tuple = ()):  # returns a cursor
        if self._kind == "postgres":
            cur = self._raw.cursor()
            cur.execute(_to_pg(sql), params)
            return cur
        return self._raw.execute(sql, params)

    def executescript(self, script: str):
        if self._kind == "postgres":
            cur = self._raw.cursor()
            cur.execute(script)  # psycopg2 runs a multi-statement string in one call
            return cur
        return self._raw.executescript(script)

    def __enter__(self) -> "_Conn":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self._raw.commit()
            else:
                self._raw.rollback()
        finally:
            self._raw.close()


def _now() -> float:
    return time.time()


def _uid() -> str:
    return uuid.uuid4().hex


class AppStore:
    def __init__(self, url: str | None = None):
        self.url = url or settings.app_db_url
        if self.url.startswith("sqlite:///"):
            self.kind = "sqlite"
            self.path = Path(self.url.replace("sqlite:///", "", 1))
            self.path.parent.mkdir(parents=True, exist_ok=True)
        elif self.url.startswith(("postgresql://", "postgres://")):
            self.kind = "postgres"
            self.dsn = self.url
        else:
            raise ValueError(
                f"Unsupported app_db_url scheme (want sqlite:/// or postgresql://): "
                f"{self.url!r}")
        self._init_schema()

    def _con(self) -> _Conn:
        if self.kind == "sqlite":
            con = sqlite3.connect(self.path, timeout=10)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA journal_mode=WAL")
            return _Conn(con, "sqlite")
        import psycopg2
        import psycopg2.extras

        # DictCursor rows support BOTH r["col"] and r[0], matching sqlite3.Row,
        # so every method body reads rows the same way on either engine.
        con = psycopg2.connect(self.dsn, connect_timeout=10,
                               cursor_factory=psycopg2.extras.DictCursor)
        return _Conn(con, "postgres")

    def _existing_columns(self, con: _Conn, table: str) -> set[str]:
        if self.kind == "sqlite":
            return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        return {r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=?",
            (table,))}

    def _init_schema(self) -> None:
        with self._con() as con:
            con.executescript(_SCHEMA)
            # Lightweight migration: add conversation columns to a pre-existing
            # queries table (older app DBs created before multi-turn support).
            existing = self._existing_columns(con, "queries")
            for col, decl in (("conversation_id", "TEXT"),
                              ("turn_index", "INTEGER"),
                              ("context", "TEXT")):
                if col not in existing:
                    con.execute(f"ALTER TABLE queries ADD COLUMN {col} {decl}")
            # Phase 3: auth/billing columns on a pre-existing users table.
            ucols = self._existing_columns(con, "users")
            for col, decl in (("password_hash", "TEXT"),
                              ("api_key_id", "TEXT"),
                              ("plan", "TEXT NOT NULL DEFAULT 'free'"),
                              ("stripe_customer_id", "TEXT"),
                              ("byo_llm_key_enc", "TEXT")):
                if col not in ucols:
                    con.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
            # Index AFTER the migration so it never references a not-yet-added
            # column on a pre-existing users table.
            con.execute("CREATE INDEX IF NOT EXISTS ix_users_api_key_id "
                        "ON users(api_key_id)")

    # --- users ---
    def create_user(self, email: str, api_key_hash: str,
                    password_hash: str | None = None,
                    api_key_id: str | None = None, plan: str = "free") -> dict:
        uid = _uid()
        with self._con() as con:
            con.execute(
                "INSERT INTO users(id,email,api_key_hash,created_at,password_hash,"
                "api_key_id,plan) VALUES(?,?,?,?,?,?,?)",
                (uid, email, api_key_hash, _now(), password_hash, api_key_id, plan))
        return self.get_user(uid)

    def get_user(self, uid: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(r) if r else None

    def get_user_by_email(self, email: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(r) if r else None

    def get_user_by_api_key_id(self, api_key_id: str) -> dict | None:
        """Indexed lookup so API-key auth is O(1) + a single hash verify, not an
        O(n) PBKDF2 scan over every user (the assessment's auth finding)."""
        with self._con() as con:
            r = con.execute("SELECT * FROM users WHERE api_key_id=?",
                            (api_key_id,)).fetchone()
        return dict(r) if r else None

    def set_password(self, uid: str, password_hash: str) -> None:
        with self._con() as con:
            con.execute("UPDATE users SET password_hash=? WHERE id=?",
                        (password_hash, uid))

    def set_plan(self, uid: str, plan: str,
                 stripe_customer_id: str | None = None) -> None:
        with self._con() as con:
            if stripe_customer_id is not None:
                con.execute("UPDATE users SET plan=?, stripe_customer_id=? WHERE id=?",
                            (plan, stripe_customer_id, uid))
            else:
                con.execute("UPDATE users SET plan=? WHERE id=?", (plan, uid))

    def get_user_by_stripe_customer(self, customer_id: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM users WHERE stripe_customer_id=?",
                            (customer_id,)).fetchone()
        return dict(r) if r else None

    def set_byo_llm_key(self, uid: str, key_enc: str | None) -> None:
        with self._con() as con:
            con.execute("UPDATE users SET byo_llm_key_enc=? WHERE id=?",
                        (key_enc, uid))

    # --- usage metering (Free-tier caps) ---
    def record_usage(self, user_id: str, connection_id: str | None = None) -> None:
        with self._con() as con:
            con.execute("INSERT INTO usage_events(id,user_id,connection_id,created_at)"
                        " VALUES(?,?,?,?)", (_uid(), user_id, connection_id, _now()))

    def count_usage_since(self, user_id: str, since_epoch: float) -> int:
        with self._con() as con:
            r = con.execute(
                "SELECT COUNT(*) FROM usage_events WHERE user_id=? AND created_at>=?",
                (user_id, since_epoch)).fetchone()
        return int(r[0])

    def count_user_connections(self, user_id: str) -> int:
        with self._con() as con:
            r = con.execute("SELECT COUNT(*) FROM connections WHERE user_id=?",
                            (user_id,)).fetchone()
        return int(r[0])

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

    # --- semantic layer: governed metrics ---
    @staticmethod
    def _metric_row(r) -> dict:
        d = dict(r)
        d["synonyms"] = json.loads(d["synonyms"]) if d.get("synonyms") else []
        d["certified"] = bool(d.get("certified"))
        return d

    def create_metric(self, connection_id: str, name: str, expression: str,
                      base_table: str, alias: str, synonyms: list[str] | None = None,
                      description: str | None = None, certified: bool = False) -> dict:
        mid = _uid()
        now = _now()
        with self._con() as con:
            con.execute(
                "INSERT INTO metrics(id,connection_id,name,expression,base_table,"
                "alias,synonyms,description,certified,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (mid, connection_id, name, expression, base_table, alias,
                 json.dumps(synonyms or []), description, int(certified), now, now))
        return self.get_metric(mid)

    def get_metric(self, mid: str) -> dict | None:
        with self._con() as con:
            r = con.execute("SELECT * FROM metrics WHERE id=?", (mid,)).fetchone()
        return self._metric_row(r) if r else None

    def list_metrics(self, connection_id: str) -> list[dict]:
        with self._con() as con:
            rows = con.execute(
                "SELECT * FROM metrics WHERE connection_id=? "
                "ORDER BY certified DESC, name", (connection_id,)).fetchall()
        return [self._metric_row(r) for r in rows]

    def count_metrics(self, connection_id: str) -> int:
        with self._con() as con:
            r = con.execute("SELECT COUNT(*) FROM metrics WHERE connection_id=?",
                            (connection_id,)).fetchone()
        return int(r[0])

    def update_metric(self, mid: str, **fields) -> dict | None:
        """Patch any subset of {name, expression, base_table, alias, synonyms,
        description, certified}. ``synonyms`` is JSON-encoded, ``certified`` cast to int."""
        allowed = {"name", "expression", "base_table", "alias", "synonyms",
                   "description", "certified"}
        sets, params = [], []
        for k, v in fields.items():
            if k not in allowed or v is None:
                continue
            if k == "synonyms":
                v = json.dumps(v)
            elif k == "certified":
                v = int(bool(v))
            sets.append(f"{k}=?")
            params.append(v)
        if not sets:
            return self.get_metric(mid)
        sets.append("updated_at=?")
        params.extend([_now(), mid])
        with self._con() as con:
            con.execute(f"UPDATE metrics SET {', '.join(sets)} WHERE id=?", tuple(params))
        return self.get_metric(mid)

    def delete_metric(self, mid: str) -> None:
        with self._con() as con:
            con.execute("DELETE FROM metrics WHERE id=?", (mid,))

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
            for k in ("assumptions", "result_meta", "context"):
                d[k] = json.loads(d[k]) if d.get(k) else None
            d["payload"] = _load_payload(d.get("payload"))
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
                 encrypt(json.dumps(payload or {})), _now(),
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
        for k in ("assumptions", "result_meta"):
            d[k] = json.loads(d[k]) if d.get(k) else None
        d["payload"] = _load_payload(d.get("payload"))
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
        """👍'd answers become verified (question -> SQL) few-shot examples.

        GROUP BY (not SELECT DISTINCT) so the recency ORDER BY is valid on both
        engines — Postgres rejects ordering a DISTINCT by a non-selected column."""
        with self._con() as con:
            rows = con.execute(
                "SELECT question, sql FROM feedback WHERE rating='up' "
                "AND sql IS NOT NULL GROUP BY question, sql "
                "ORDER BY MAX(created_at) DESC LIMIT ?",
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
