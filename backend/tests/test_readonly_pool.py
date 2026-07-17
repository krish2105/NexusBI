"""Layer 1 tests — the read-only pool refuses writes at the engine itself."""
import pytest

from app.db.target_pool import ReadOnlyExecutionError, TargetPool


def test_select_returns_rows():
    r = TargetPool().execute("SELECT COUNT(*) AS n FROM orders LIMIT 10000")
    assert r.rows and r.rows[0]["n"] == 99441


def test_write_is_rejected_by_engine():
    # Even a bare write must fail — Layer 1 is the ultimate backstop.
    with pytest.raises(ReadOnlyExecutionError):
        TargetPool().execute("DELETE FROM orders")


def test_row_cap_truncates():
    p = TargetPool(row_cap=100)
    r = p.execute("SELECT order_id FROM orders LIMIT 10000")
    assert r.row_count == 100
    assert r.truncated
