"""Audit log is append-only and captures every verdict."""
from app.db.app_store import AppStore


def test_audit_is_append_only_interface():
    store = AppStore()
    # The store exposes append + read, but no update/delete for audit_log.
    assert hasattr(store, "append_audit")
    assert hasattr(store, "list_audit")
    assert not any(
        m for m in dir(store)
        if m.startswith(("update_audit", "delete_audit", "edit_audit")))


def test_audit_records_verdict_and_reads_back():
    store = AppStore()
    aid = store.append_audit("query.blocked", sql_text="DROP TABLE orders",
                             verdict="BLOCK", detail={"layer": "AST validation (L2)"})
    rows = store.list_audit(limit=5)
    assert any(r["id"] == aid and r["verdict"] == "BLOCK" for r in rows)
