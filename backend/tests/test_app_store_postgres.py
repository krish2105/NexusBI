"""AppStore Postgres backend — dialect-translation unit tests (always run) plus a
live round-trip (skipped unless a Postgres is reachable).

Why this matters: on a host with an ephemeral filesystem (Render's free plan) the
default SQLite app DB is wiped on every redeploy. Pointing ``APP_DB_URL`` at a
managed Postgres makes users, connections + encrypted DSNs, the audit log,
monitors, feedback, dashboards and history durable. This proves the same store
code runs on both engines.

Run the live test:

    docker run -d --name pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=nexus_app \
        -p 5433:5432 postgres:16-alpine
    NEXUS_TEST_PG_URL=postgresql://postgres:test@localhost:5433/nexus_app \
        pytest tests/test_app_store_postgres.py -v
"""
from __future__ import annotations

import os

import pytest

from app.db.app_store import _rewrite_upsert, _to_pg


# --------------------------------------------------- translation (no PG needed)
def test_qmark_params_become_pct_s():
    assert _to_pg("SELECT * FROM users WHERE id=? AND email=?") == \
        "SELECT * FROM users WHERE id=%s AND email=%s"


def test_insert_or_replace_becomes_on_conflict():
    sql = ("INSERT OR REPLACE INTO queries(id,user_id,question) "
           "VALUES(?,?,?)")
    out = _to_pg(sql)
    assert out.startswith("INSERT INTO queries(id,user_id,question) VALUES(%s,%s,%s)")
    assert "ON CONFLICT (id) DO UPDATE SET" in out
    assert "user_id=EXCLUDED.user_id" in out and "question=EXCLUDED.question" in out
    assert "id=EXCLUDED.id" not in out          # the conflict key is not re-set


def test_plain_insert_untouched():
    sql = "INSERT INTO users(id,email) VALUES(?,?)"
    assert _to_pg(sql) == "INSERT INTO users(id,email) VALUES(%s,%s)"


def test_rewrite_upsert_sets_every_non_id_column():
    out = _rewrite_upsert("INSERT OR REPLACE INTO t(id,a,b,c) VALUES(?,?,?,?)")
    assert out.endswith("ON CONFLICT (id) DO UPDATE SET a=EXCLUDED.a, "
                        "b=EXCLUDED.b, c=EXCLUDED.c")


# ------------------------------------------------------------- live round-trip
PG_URL = os.environ.get("NEXUS_TEST_PG_URL")
pg_live = pytest.mark.skipif(not PG_URL, reason="no NEXUS_TEST_PG_URL")


@pg_live
def test_full_store_round_trip_and_persistence():
    """Every table exercised on Postgres, then re-opened to prove durability."""
    import psycopg2

    # Fresh schema so counts are deterministic.
    con = psycopg2.connect(PG_URL)
    con.autocommit = True
    con.cursor().execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    con.close()

    from app.db.app_store import AppStore

    s = AppStore(url=PG_URL)
    assert s.kind == "postgres"

    u = s.create_user("live@test.com", "hash")
    assert s.get_user_by_email("live@test.com")["email"] == "live@test.com"
    c = s.create_connection(u["id"], "prod", "postgresql://ro@h/db", "postgres", True)
    assert len(s.list_connections(u["id"])) == 1

    # upsert: same id twice must UPDATE, not duplicate (ON CONFLICT path)
    qid = s.save_query(c["id"], "orig", "SELECT 1", "HIGH", ["a"], {"rows": 1},
                       {"data": [1]}, user_id=u["id"])
    s.save_query(c["id"], "updated", "SELECT 2", "LOW", [], {"rows": 2},
                 {"data": [2]}, user_id=u["id"], query_id=qid)
    assert s.get_query(qid)["question"] == "updated"
    assert len(s.list_queries()) == 1

    conv = s.create_conversation(c["id"], "t")
    s.save_query(c["id"], "turn0", None, "MED", None, None, None,
                 conversation_id=conv["id"], turn_index=0, context={"k": "v"})
    assert s.next_turn_index(conv["id"]) == 1
    assert s.conversation_context(conv["id"])[0]["context"] == {"k": "v"}

    s.append_audit("query.executed", actor="u", sql_text="SELECT 1", row_count=1,
                   latency_ms=12.5, verdict="ALLOW", detail={"x": 1})
    s.add_feedback(qid, "up", note="good", connection_id=c["id"],
                   question="orig", sql="SELECT 1")
    assert s.feedback_stats()["satisfaction_rate"] == 1.0
    assert len(s.vetted_examples()) == 1          # the GROUP BY/ORDER BY fix

    m = s.create_monitor("rev", "revenue?", c["id"])
    s.mark_monitor_run(m["id"], "ok")
    s.set_monitor_enabled(m["id"], False)
    assert len(s.list_monitors(enabled_only=True)) == 0
    aid = s.add_alert(m["id"], "rev", "high", "drop", metric=9.9, detail={"d": 1})
    s.acknowledge_alert(aid)
    assert len(s.list_alerts()) == 1

    d = s.create_dashboard("board", user_id=u["id"])
    s.pin_to_dashboard(d["id"], qid, {"x": 0})
    assert len(s.get_dashboard(d["id"])["items"]) == 1

    # DOUBLE PRECISION (not REAL): epoch timestamp keeps full precision on PG.
    import time
    assert abs(s.list_audit()[0]["created_at"] - time.time()) < 5

    # Durability: a fresh store (simulating a redeploy) sees the same data.
    s2 = AppStore(url=PG_URL)
    assert s2.get_user_by_email("live@test.com") is not None
    assert len(s2.list_connections(u["id"])) == 1
    assert len(s2.list_audit()) == 1


@pg_live
def test_unsupported_scheme_rejected():
    from app.db.app_store import AppStore

    with pytest.raises(ValueError):
        AppStore(url="mysql://root@localhost/db")
