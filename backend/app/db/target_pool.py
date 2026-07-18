"""READ-ONLY connection pool to the *target* (user) database — multi-dialect.

This is **Layer 1** of the SQL safety design: read-only by construction. Even if
every other layer failed and a destructive statement reached execution, the
database itself refuses it. One interface, four dialects:

  * SQLite   -> ``mode=ro`` immutable URI + ``PRAGMA query_only=ON``.
  * Postgres -> ``default_transaction_read_only = on`` in a read-only transaction.
  * MySQL    -> ``SET SESSION TRANSACTION READ ONLY`` + a least-privilege role.
  * BigQuery -> SELECT-only jobs (a non-SELECT never survives the AST layer),
                with a bytes-billed cap.

The generator writes standard (Postgres) SQL; the safety layer transpiles it to
the connection's dialect via sqlglot, so grounding + validation are shared and
only execution is dialect-specific. The target pool is separate from the
app-metadata DB — they never mix.

DSN forms:
  sqlite:///abs/path.db
  postgresql://user:pass@host:5432/db
  mysql://user:pass@host:3306/db
  bigquery://project/dataset          (creds via GOOGLE_APPLICATION_CREDENTIALS)
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.config import settings

# DSN scheme -> sqlglot dialect name (also our internal kind).
_SCHEME_DIALECT = {
    "sqlite": "sqlite",
    "postgresql": "postgres", "postgres": "postgres",
    "mysql": "mysql", "mysql+pymysql": "mysql",
    "bigquery": "bigquery",
}


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


def dialect_of(url: str) -> str:
    scheme = url.split(":", 1)[0].lower()
    return _SCHEME_DIALECT.get(scheme, "postgres")


class TargetPool:
    """Minimal read-only execution surface for a single target connection."""

    def __init__(self, url: str | None = None,
                 statement_timeout_s: int | None = None,
                 row_cap: int | None = None):
        self.url = url or settings.demo_target_url
        self.dialect = dialect_of(self.url)   # sqlglot dialect + internal kind
        self.statement_timeout_s = statement_timeout_s or settings.target_statement_timeout_s
        self.row_cap = row_cap or settings.target_row_cap

    # sqlglot dialect the generated SQL should be transpiled to for this target.
    @property
    def sqlglot_dialect(self) -> str:
        return self.dialect

    # -- introspection -------------------------------------------------------
    def list_tables(self) -> list[str]:
        if self.dialect == "sqlite":
            with self._sqlite_ro() as con:
                return [r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        if self.dialect == "mysql":  # pragma: no cover - exercised via live MySQL
            con = self._mysql_conn()
            try:
                cur = con.cursor()
                cur.execute("SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = DATABASE() ORDER BY table_name")
                return [r[0] for r in cur.fetchall()]
            finally:
                con.close()
        if self.dialect == "bigquery":  # pragma: no cover - cloud service
            client, dataset = self._bq_client()
            rows = client.query(
                f"SELECT table_name FROM `{dataset}.INFORMATION_SCHEMA.TABLES` "
                "ORDER BY table_name").result()
            return [r["table_name"] for r in rows]
        with self._pg_conn() as con:  # pragma: no cover
            cur = con.cursor()
            cur.execute("SELECT tablename FROM pg_tables "
                        "WHERE schemaname = current_schema() ORDER BY tablename")
            return [r[0] for r in cur.fetchall()]

    def table_columns(self, table: str) -> list[tuple[str, str]]:
        if self.dialect == "sqlite":
            with self._sqlite_ro() as con:
                info = con.execute(f'PRAGMA table_info("{table}")').fetchall()
                return [(r[1], (r[2] or "TEXT").upper()) for r in info]
        if self.dialect == "mysql":  # pragma: no cover
            con = self._mysql_conn()
            try:
                cur = con.cursor()
                cur.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = %s "
                    "ORDER BY ordinal_position", (table,))
                return [(r[0], (r[1] or "text").upper()) for r in cur.fetchall()]
            finally:
                con.close()
        if self.dialect == "bigquery":  # pragma: no cover
            client, dataset = self._bq_client()
            rows = client.query(
                f"SELECT column_name, data_type FROM "
                f"`{dataset}.INFORMATION_SCHEMA.COLUMNS` WHERE table_name = @t "
                "ORDER BY ordinal_position",
                job_config=self._bq_params(t=table)).result()
            return [(r["column_name"], (r["data_type"] or "STRING").upper())
                    for r in rows]
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
        if self.dialect == "mysql":  # pragma: no cover
            return self._execute_mysql(sql)
        if self.dialect == "bigquery":  # pragma: no cover
            return self._execute_bigquery(sql)
        return self._execute_pg(sql)  # pragma: no cover

    def explain(self, sql: str) -> None:
        """Dry-run plan (Layer 5). Raises on a planning error; returns nothing."""
        if self.dialect == "sqlite":
            with self._sqlite_ro() as con:
                con.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
            return
        if self.dialect == "mysql":  # pragma: no cover
            con = self._mysql_conn()
            try:
                con.cursor().execute(f"EXPLAIN {sql}")
            except Exception as e:  # noqa: BLE001
                raise ReadOnlyExecutionError(str(e)) from e
            finally:
                con.close()
            return
        if self.dialect == "bigquery":  # pragma: no cover
            client, _ = self._bq_client()
            from google.cloud import bigquery

            client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True))
            return
        with self._pg_conn() as con:  # pragma: no cover
            con.cursor().execute(f"EXPLAIN {sql}")

    # -- sqlite internals ----------------------------------------------------
    def _sqlite_ro(self) -> sqlite3.Connection:
        path = Path(self.url.replace("sqlite:///", "", 1))
        uri = f"{path.as_uri()}?mode=ro&immutable=1"
        con = sqlite3.connect(uri, uri=True, timeout=self.statement_timeout_s)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only = ON")
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
        return self._pack(cols, fetched, t0, "sqlite", notes, as_dict=True)

    # -- mysql internals -----------------------------------------------------
    def _mysql_conn(self):  # pragma: no cover - requires a live server
        import pymysql

        p = urlparse(self.url)
        con = pymysql.connect(
            host=p.hostname or "localhost", port=p.port or 3306,
            user=unquote(p.username or ""), password=unquote(p.password or ""),
            database=(p.path or "/").lstrip("/") or None,
            read_timeout=self.statement_timeout_s,
            connect_timeout=self.statement_timeout_s,
            cursorclass=pymysql.cursors.Cursor)
        cur = con.cursor()
        cur.execute("SET SESSION TRANSACTION READ ONLY")
        try:  # MySQL 5.7.8+ / 8.0
            cur.execute(f"SET SESSION max_execution_time = "
                        f"{self.statement_timeout_s * 1000}")
        except Exception:  # noqa: BLE001 - older MySQL / MariaDB
            pass
        return con

    def _execute_mysql(self, sql: str) -> ExecResult:  # pragma: no cover
        t0 = time.perf_counter()
        con = self._mysql_conn()
        try:
            cur = con.cursor()
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            fetched = cur.fetchmany(self.row_cap + 1)
        except Exception as e:  # noqa: BLE001
            raise ReadOnlyExecutionError(str(e)) from e
        finally:
            con.close()
        return self._pack(cols, fetched, t0, "mysql", [], as_dict=False)

    # -- bigquery internals --------------------------------------------------
    def _bq_client(self):  # pragma: no cover - cloud service
        from google.cloud import bigquery

        p = urlparse(self.url)
        project = p.hostname
        dataset = (p.path or "/").lstrip("/")
        client = bigquery.Client(project=project)
        return client, dataset

    def _bq_params(self, **params):  # pragma: no cover
        from google.cloud import bigquery

        qp = [bigquery.ScalarQueryParameter(k, "STRING", v)
              for k, v in params.items()]
        return bigquery.QueryJobConfig(query_parameters=qp)

    def _execute_bigquery(self, sql: str) -> ExecResult:  # pragma: no cover
        from google.cloud import bigquery

        t0 = time.perf_counter()
        client, _ = self._bq_client()
        cfg = bigquery.QueryJobConfig(
            maximum_bytes_billed=int(2e9),  # ~2 GB cap, cost guardrail
            use_query_cache=True)
        try:
            job = client.query(sql, job_config=cfg)
            it = job.result(max_results=self.row_cap + 1)
            cols = [f.name for f in it.schema]
            fetched = [tuple(row.values()) for row in it]
        except Exception as e:  # noqa: BLE001
            raise ReadOnlyExecutionError(str(e)) from e
        return self._pack(cols, fetched, t0, "bigquery", [], as_dict=False)

    # -- postgres internals --------------------------------------------------
    def _pg_conn(self):  # pragma: no cover - requires a live server
        import psycopg2

        con = psycopg2.connect(self.url)
        con.set_session(readonly=True, autocommit=False)
        cur = con.cursor()
        cur.execute("SET default_transaction_read_only = on")
        cur.execute(f"SET statement_timeout = '{self.statement_timeout_s}s'")
        return con

    def _execute_pg(self, sql: str) -> ExecResult:  # pragma: no cover
        t0 = time.perf_counter()
        try:
            with self._pg_conn() as con:
                cur = con.cursor()
                cur.execute(sql)
                cols = [d[0] for d in cur.description] if cur.description else []
                fetched = cur.fetchmany(self.row_cap + 1)
        except Exception as e:  # noqa: BLE001
            raise ReadOnlyExecutionError(str(e)) from e
        return self._pack(cols, fetched, t0, "postgres", [], as_dict=False)

    # -- shared result packing ----------------------------------------------
    @staticmethod
    def _norm(v: Any) -> Any:
        """Normalize driver-specific types so results are uniform + JSON-safe
        across dialects (MySQL Decimal/datetime, BigQuery types, etc.)."""
        import datetime
        import decimal

        if isinstance(v, decimal.Decimal):
            return float(v)
        if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
            return v.isoformat()
        if isinstance(v, (bytes, bytearray)):
            return v.decode("utf-8", "replace")
        return v

    def _pack(self, cols, fetched, t0, dialect, notes, as_dict) -> ExecResult:
        truncated = len(fetched) > self.row_cap
        if truncated:
            fetched = fetched[: self.row_cap]
            notes = [*notes, f"result truncated to row cap {self.row_cap:,}"]
        if as_dict:
            rows = [{k: self._norm(v) for k, v in dict(r).items()} for r in fetched]
        else:
            rows = [{c: self._norm(v) for c, v in zip(cols, r)} for r in fetched]
        return ExecResult(
            columns=cols, rows=rows, row_count=len(rows),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            truncated=truncated, dialect=dialect, notes=notes,
        )
