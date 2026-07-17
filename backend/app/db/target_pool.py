"""READ-ONLY connection pool to the *target* (user) database.

This is **Layer 1** of the SQL safety design: read-only by construction. Even if
every other layer failed and a destructive statement reached execution, the
database itself refuses it. We support two dialects behind one interface:

  * SQLite  -> opened with ``mode=ro`` immutable URI + ``PRAGMA query_only=ON``.
  * Postgres-> session forced to ``default_transaction_read_only = on`` and run
               inside a read-only transaction with a hard ``statement_timeout``.

The target pool is deliberately separate from the app-metadata DB. They never mix.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings


@dataclass
class ExecResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    latency_ms: float
    truncated: bool = False
    dialect: str = "sqlite"
    notes: list[str] = field(default_factory=list)


class ReadOnlyExecutionError(RuntimeError):
    """Raised when execution fails or a write somehow reaches the engine."""


class TargetPool:
    """Minimal read-only execution surface for a single target connection."""

    def __init__(self, url: str | None = None,
                 statement_timeout_s: int | None = None,
                 row_cap: int | None = None):
        self.url = url or settings.demo_target_url
        self.dialect = "sqlite" if self.url.startswith("sqlite") else "postgres"
        self.statement_timeout_s = statement_timeout_s or settings.target_statement_timeout_s
        self.row_cap = row_cap or settings.target_row_cap

    # -- introspection -------------------------------------------------------
    def list_tables(self) -> list[str]:
        if self.dialect == "sqlite":
            with self._sqlite_ro() as con:
                return [r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "ORDER BY name")]
        with self._pg_conn() as con:  # pragma: no cover - exercised in prod
            cur = con.cursor()
            cur.execute("SELECT tablename FROM pg_tables "
                        "WHERE schemaname = current_schema() ORDER BY tablename")
            return [r[0] for r in cur.fetchall()]

    def table_columns(self, table: str) -> list[tuple[str, str]]:
        if self.dialect == "sqlite":
            with self._sqlite_ro() as con:
                # PRAGMA cannot bind params; table name is validated by caller
                # against the introspected allow-list before reaching here.
                info = con.execute(f'PRAGMA table_info("{table}")').fetchall()
                return [(r[1], (r[2] or "TEXT").upper()) for r in info]
        with self._pg_conn() as con:  # pragma: no cover
            cur = con.cursor()
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = %s AND table_schema = current_schema() "
                "ORDER BY ordinal_position", (table,))
            return [(r[0], r[1]) for r in cur.fetchall()]

    # -- execution -----------------------------------------------------------
    def execute(self, sql: str) -> ExecResult:
        """Run an ALREADY-VALIDATED read-only SELECT. Never call with raw LLM SQL."""
        if self.dialect == "sqlite":
            return self._execute_sqlite(sql)
        return self._execute_pg(sql)  # pragma: no cover

    def explain(self, sql: str) -> None:
        """Dry-run plan (Layer 5). Raises on a planning error; returns nothing."""
        if self.dialect == "sqlite":
            with self._sqlite_ro() as con:
                con.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
            return
        with self._pg_conn() as con:  # pragma: no cover
            con.cursor().execute(f"EXPLAIN {sql}")

    # -- sqlite internals ----------------------------------------------------
    def _sqlite_ro(self) -> sqlite3.Connection:
        # DSN form is sqlite:///<absolute path>; the path may contain spaces,
        # so build the URI via Path.as_uri() which percent-encodes correctly.
        path = Path(self.url.replace("sqlite:///", "", 1))
        uri = f"{path.as_uri()}?mode=ro&immutable=1"
        con = sqlite3.connect(uri, uri=True, timeout=self.statement_timeout_s)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only = ON")  # belt: reject writes at session
        # Enforce a wall-clock budget via a progress handler.
        deadline = time.monotonic() + self.statement_timeout_s
        con.set_progress_handler(
            lambda: 1 if time.monotonic() > deadline else 0, 2_000)
        return con

    def _execute_sqlite(self, sql: str) -> ExecResult:
        t0 = time.perf_counter()
        notes: list[str] = []
        try:
            with self._sqlite_ro() as con:
                cur = con.execute(sql)
                cols = [d[0] for d in cur.description] if cur.description else []
                fetched = cur.fetchmany(self.row_cap + 1)
        except sqlite3.OperationalError as e:
            raise ReadOnlyExecutionError(str(e)) from e
        truncated = len(fetched) > self.row_cap
        if truncated:
            fetched = fetched[: self.row_cap]
            notes.append(f"result truncated to row cap {self.row_cap:,}")
        rows = [dict(r) for r in fetched]
        return ExecResult(
            columns=cols, rows=rows, row_count=len(rows),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            truncated=truncated, dialect="sqlite", notes=notes,
        )

    # -- postgres internals (production path) --------------------------------
    def _pg_conn(self):  # pragma: no cover - requires a live server
        import psycopg2  # local import keeps sqlite-only installs light

        con = psycopg2.connect(self.url)
        con.set_session(readonly=True, autocommit=False)
        cur = con.cursor()
        cur.execute("SET default_transaction_read_only = on")
        cur.execute(f"SET statement_timeout = '{self.statement_timeout_s}s'")
        return con

    def _execute_pg(self, sql: str) -> ExecResult:  # pragma: no cover
        t0 = time.perf_counter()
        notes: list[str] = []
        try:
            with self._pg_conn() as con:
                cur = con.cursor()
                cur.execute(sql)
                cols = [d[0] for d in cur.description] if cur.description else []
                fetched = cur.fetchmany(self.row_cap + 1)
        except Exception as e:  # noqa: BLE001 - normalized for the caller
            raise ReadOnlyExecutionError(str(e)) from e
        truncated = len(fetched) > self.row_cap
        if truncated:
            fetched = fetched[: self.row_cap]
            notes.append(f"result truncated to row cap {self.row_cap:,}")
        rows = [dict(zip(cols, r)) for r in fetched]
        return ExecResult(
            columns=cols, rows=rows, row_count=len(rows),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            truncated=truncated, dialect="postgres", notes=notes,
        )
