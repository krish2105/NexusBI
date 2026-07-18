"""Multi-dialect support — the safety layer + generated SQL are dialect-aware.

The generator writes standard (Postgres) SQL; the safety layer validates it
(dialect-agnostic AST) and transpiles the safe result to the target dialect via
sqlglot. These tests prove: (1) the same validated query renders as *valid* SQL
for sqlite/postgres/mysql/bigquery, with correct identifier quoting; (2) the AST
safety rules still block attacks written in each dialect; (3) DSN → dialect
detection is correct.
"""
import sqlglot
import pytest

from app.agents.planner import plan_question
from app.agents.sql_generator import synthesize_sql
from app.db.target_pool import dialect_of
from app.sqlsafety.guard import validate_sql

DIALECTS = ["sqlite", "postgres", "mysql", "bigquery"]


def test_dsn_dialect_detection():
    assert dialect_of("sqlite:///x.db") == "sqlite"
    assert dialect_of("postgresql://u:p@h/db") == "postgres"
    assert dialect_of("postgres://u:p@h/db") == "postgres"
    assert dialect_of("mysql://u:p@h:3306/db") == "mysql"
    assert dialect_of("mysql+pymysql://u:p@h/db") == "mysql"
    assert dialect_of("bigquery://my-project/my_dataset") == "bigquery"


@pytest.mark.parametrize("dialect", DIALECTS)
def test_generated_sql_transpiles_to_each_dialect(dialect, allow_list):
    # A representative grounded query (join + aggregate + group + order + limit).
    plan = plan_question("top 5 product categories by merchandise revenue")
    sql, _, _ = synthesize_sql(
        "top 5 product categories by merchandise revenue", plan)
    report = validate_sql(sql, allow_list, source_dialect="postgres",
                          target_dialect=dialect)
    assert report.verdict == "ALLOW", report.errors
    # The transpiled SQL must re-parse cleanly in the TARGET dialect.
    reparsed = sqlglot.parse_one(report.safe_sql, read=dialect)
    assert reparsed is not None
    assert "LIMIT" in report.safe_sql.upper()


def test_mysql_and_bigquery_identifier_quoting(allow_list):
    # generic (uploaded-data) path uses quoted identifiers; verify they render as
    # backticks for mysql/bigquery and don't break.
    from app.agents.sql_generator import synthesize_generic
    from app.rag.catalog import Column, Table
    from app.rag.retriever import RetrievedSchema

    schema = RetrievedSchema(
        tables=[Table("sales", "one row per sale", [
            Column("region", "TEXT", True), Column("revenue", "REAL", True)])],
        glossary=[])
    sql, _, _ = synthesize_generic("total revenue by region",
                                   plan_question("total revenue by region"), schema)
    for dialect, quote in (("mysql", "`"), ("bigquery", "`")):
        r = validate_sql(sql, {"sales": {"region", "revenue"}},
                         source_dialect="postgres", target_dialect=dialect)
        assert r.verdict == "ALLOW", r.errors
        assert quote in r.safe_sql          # backtick-quoted identifiers
        assert sqlglot.parse_one(r.safe_sql, read=dialect) is not None


@pytest.mark.parametrize("dialect", DIALECTS)
def test_attacks_blocked_in_every_dialect(dialect, allow_list):
    attacks = ["DROP TABLE orders", "DELETE FROM orders",
               "SELECT 1; DROP TABLE orders",
               "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x"]
    for sql in attacks:
        r = validate_sql(sql, allow_list, source_dialect=dialect,
                         target_dialect=dialect)
        assert r.verdict == "BLOCK", f"{dialect}: {sql!r} was not blocked"
