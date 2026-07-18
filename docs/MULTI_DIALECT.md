# Multi-Dialect Support (SQLite · Postgres · MySQL · BigQuery)

Nexus connects to more than one database engine without duplicating its brains.
The trick: **grounding, generation, and validation are dialect-agnostic; only
execution is dialect-specific.**

```
question ─► plan ─► generate STANDARD SQL (Postgres grammar)
                         │
                         ▼
                 sql_validator  ── AST safety rules (dialect-agnostic)
                         │        allow-list + LIMIT
                         ▼
             transpile to the connection's dialect (sqlglot)
                         │
                         ▼
                   execute (per-dialect driver, READ-ONLY)
```

The SQL generator always emits standard SQL. The safety layer parses it to an
AST (the rules — single read-only SELECT, no DML/DDL nodes, allow-listed
tables/columns, injected LIMIT — don't care about dialect) and then **`sqlglot`
transpiles the validated query to the target dialect**, handling identifier
quoting (`"col"` → `` `col` `` for MySQL/BigQuery), `NULLS LAST` emulation,
function differences, etc. So a `DROP TABLE` is blocked identically whether the
target is Postgres or BigQuery, and a valid query runs natively on each.

## Read-only, per dialect (Layer 1)

| Dialect | How read-only is enforced | How it's verified on connect |
|---|---|---|
| **SQLite** | `mode=ro` immutable URI + `PRAGMA query_only=ON` | enforced by the pool itself |
| **Postgres** | `default_transaction_read_only = on` in a read-only txn | probe the role with a raw connection; reject if it can write |
| **MySQL** | `SET SESSION TRANSACTION READ ONLY` + a least-privilege role | probe the role; a `SELECT`-only grant refuses the write |
| **BigQuery** | SELECT jobs can't mutate; `maximum_bytes_billed` cap | read-only by job type |

For Postgres/MySQL, always connect Nexus with a **`SELECT`-only role** — the
connect-time check *rejects a writable role* so this isn't optional in practice.

## Connecting

In the app: **Data → Connect a database**, paste a DSN:

```
postgresql://ro_user:pass@host:5432/db
mysql://ro_user:pass@host:3306/db
bigquery://my-project/my_dataset      # creds via GOOGLE_APPLICATION_CREDENTIALS
```

The DSN is **SSRF-screened** (private/loopback/metadata hosts blocked unless
`ALLOW_LOCAL_TARGETS=true` for local dev), **verified read-only**, and
**encrypted at rest** before it's stored. Then it appears in the workspace
connection picker and every feature — conversations, dashboards, briefing —
works against it.

Install only the driver you need:
```
pip install pymysql               # MySQL / MariaDB
pip install psycopg2-binary       # Postgres
pip install google-cloud-bigquery # BigQuery
```

## Proven, not just claimed

- **Cross-dialect transpilation** is unit-tested (`tests/test_multidialect.py`):
  the same validated query re-parses cleanly in sqlite/postgres/mysql/bigquery,
  and attacks are blocked in every dialect.
- **A full MySQL round-trip** is a reproducible live test
  (`tests/test_mysql_live.py`, skipped unless a MySQL is reachable): it
  provisions a table + a read-only user and verifies introspection, read-only
  verification (RO accepted / writable rejected), generation → transpile →
  execute, and that writes + attacks are blocked. Values are normalized
  (`Decimal`→float, dates→ISO) so results and charts are uniform across dialects.

Postgres and BigQuery execution paths are structured identically; they run in
production against a live server / the BigQuery API.
