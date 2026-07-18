"""FK-introspected join graph — the generalization beyond the hardcoded demo.

Covers the three discovery sources (introspected FKs / name inference / curated
Olist fallback), the pool's FK introspection, BFS multi-hop pathing, and — the
critical guarantee — that the demo graph is byte-for-byte the curated map so the
flagship revenue-over-time query still groups by *purchase* date, not shipping.
"""
import sqlite3
import tempfile

import pytest

from app.config import settings
from app.db.joingraph import (OLIST_EDGES, JoinGraph, build_join_graph,
                              cached_join_graph)
from app.db.target_pool import TargetPool


def _make_db(script: str) -> str:
    path = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(path)
    con.executescript(script)
    con.commit()
    con.close()
    return f"sqlite:///{path}"


# --- pool FK introspection --------------------------------------------------
def test_pool_foreign_keys_sqlite():
    url = _make_db(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);"
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, "
        "  customer_id INTEGER REFERENCES customers(id), amount REAL);")
    fks = TargetPool(url=url).foreign_keys()
    assert ("orders", "customer_id", "customers", "id") in fks


def test_pool_foreign_keys_empty_when_none_declared():
    url = _make_db("CREATE TABLE t (a INTEGER, b TEXT);")
    assert TargetPool(url=url).foreign_keys() == []


# --- graph from declared FKs (the real generalization) ----------------------
def test_graph_built_from_declared_fks():
    url = _make_db(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);"
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, "
        "  customer_id INTEGER REFERENCES customers(id), amount REAL);"
        "CREATE TABLE line_items (id INTEGER PRIMARY KEY, "
        "  order_id INTEGER REFERENCES orders(id), sku TEXT);")
    g = build_join_graph(url)
    assert g.source == "foreign_keys"
    assert g.edges[frozenset({"orders", "customers"})] == "orders.customer_id = customers.id"
    # multi-hop path resolves through the FK chain
    assert g.bfs_path("line_items", "customers") == ["line_items", "orders", "customers"]
    _, joins, unresolved = g.plan_joins({"line_items", "orders", "customers"}, "line_items")
    assert not unresolved and len(joins) == 2


# --- inference for FK-less schemas (BYO CSV uploads) ------------------------
def test_graph_infers_edges_from_naming_when_no_fks():
    url = _make_db(
        "CREATE TABLE products (product_id INTEGER, name TEXT);"
        "CREATE TABLE sales (id INTEGER, product_id INTEGER, revenue REAL);")
    g = build_join_graph(url)
    assert g.source == "inferred"
    assert g.edges[frozenset({"sales", "products"})] == "sales.product_id = products.product_id"


def test_declared_fks_win_over_inference():
    """A real FK must not be overridden by a name-inferred guess."""
    url = _make_db(
        "CREATE TABLE dim (id INTEGER PRIMARY KEY, dim_id INTEGER, label TEXT);"
        "CREATE TABLE fact (id INTEGER PRIMARY KEY, "
        "  dim_id INTEGER REFERENCES dim(id), v REAL);")
    g = build_join_graph(url)
    assert g.source in ("foreign_keys", "mixed")
    assert g.edges[frozenset({"fact", "dim"})] == "fact.dim_id = dim.id"  # FK, not dim.dim_id


def test_empty_graph_for_unrelated_tables():
    url = _make_db("CREATE TABLE a (x INTEGER); CREATE TABLE b (y TEXT);")
    g = build_join_graph(url)
    assert g.source == "empty" and g.edges == {}


# --- demo parity (must NOT change the flagship behavior) ---------------------
def test_demo_uses_curated_olist_edges_verbatim():
    from app.db.seed_demo import seed_sqlite
    seed_sqlite()
    g = cached_join_graph(settings.demo_target_url)
    assert g.source == "olist_curated"
    # every curated edge present, and dates reached via ORDER date (not shipping)
    assert g.edges == {k: v for k, v in OLIST_EDGES.items()}
    assert g.edges[frozenset({"orders", "dates"})] == "orders.order_date_id = dates.date_id"
    assert frozenset({"order_items", "dates"}) not in g.edges  # no shipping-date shortcut


def test_demo_revenue_over_time_groups_by_purchase_month():
    """Regression: the refactor must keep grouping the time series by order date."""
    from app.agents.sql_generator import synthesize_sql
    from app.agents.planner import plan_question
    q = "Show monthly merchandise revenue over time"
    sql, _, _ = synthesize_sql(q, plan_question(q))
    # served by the pre-aggregated monthly view OR grouped via orders.order_date_id
    assert "monthly_kpis" in sql or "order_date_id" in sql
    assert "shipping_limit_date_id" not in sql


# --- BYO-schema graph propagation (the actual point of the generalization) --
def test_synthesize_sql_forwards_graph_to_generic_path():
    """synthesize_sql's early-return for a non-Olist schema must forward the
    connection's own graph to synthesize_generic — not silently drop it and fall
    back to the (irrelevant) Olist demo graph. Without this, BYO/uploaded
    connections would never join across tables, defeating the whole feature."""
    from app.agents.planner import plan_question
    from app.agents.sql_generator import is_olist_schema, synthesize_sql
    from app.rag.catalog import Column, Table
    from app.rag.retriever import RetrievedSchema

    url = _make_db(
        "CREATE TABLE products (product_id INTEGER PRIMARY KEY, category TEXT, "
        "  price REAL);"
        "CREATE TABLE sales (id INTEGER PRIMARY KEY, "
        "  product_id INTEGER REFERENCES products(product_id), revenue REAL);")
    graph = build_join_graph(url)
    assert graph.source == "foreign_keys"  # sanity: this is NOT the Olist graph

    schema = RetrievedSchema(tables=[
        Table("sales", "one row per sale", [
            Column("id", "INTEGER", False), Column("product_id", "INTEGER", False),
            Column("revenue", "REAL", False)]),
        Table("products", "one row per product", [
            Column("product_id", "INTEGER", False), Column("category", "TEXT", False),
            Column("price", "REAL", False)]),
    ], glossary=[])
    assert not is_olist_schema(schema)  # confirms this exercises the generic path

    q = "total revenue by category"
    sql, _, _ = synthesize_sql(q, plan_question(q), schema, graph)
    # A real cross-table join, using THIS connection's FK — not a single-table
    # fallback, and not anything resembling the Olist schema.
    assert "JOIN" in sql and "products" in sql and "sales" in sql
    assert "category" in sql
