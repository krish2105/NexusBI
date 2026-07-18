"""Cross-dialect golden regression suite — the guard's behavior is *frozen*.

Why this exists: the safety layer parses SQL with ``sqlglot``, so a transitive
parser change could silently alter what it accepts, rejects, or transpiles to.
This suite snapshots the verdict + transpiled ``safe_sql`` for a fixed corpus
across postgres/mysql/sqlite/bigquery into ``fixtures/guard_golden.json`` and
asserts current behavior matches it exactly. Any drift (a sqlglot bump that
changes a verdict or an emitted query) fails CI loudly instead of shipping.

Regenerate deliberately after an intended change:

    SQLGUARD_UPDATE_SNAPSHOTS=1 python -m pytest tests/test_regression.py
"""
import json
import os
from pathlib import Path

from sqlguard import validate_sql
from regression_corpus import ALLOW_LIST, CORPUS, DIALECTS  # sibling module

GOLDEN = Path(__file__).parent / "fixtures" / "guard_golden.json"


def _snapshot() -> dict:
    """verdict + layer + errors + safe_sql for every (case, target-dialect)."""
    out: dict = {}
    for case_id, sql in CORPUS:
        out[case_id] = {"sql": sql, "dialects": {}}
        for dialect in DIALECTS:
            r = validate_sql(sql, ALLOW_LIST, source_dialect="postgres",
                             target_dialect=dialect)
            out[case_id]["dialects"][dialect] = {
                "verdict": r.verdict,
                "layer": r.layer,
                "errors": r.errors,
                "safe_sql": r.safe_sql,
                "limit_applied": r.limit_applied,
            }
    return out


def test_guard_behavior_matches_golden_snapshot():
    current = _snapshot()

    if os.environ.get("SQLGUARD_UPDATE_SNAPSHOTS"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        import pytest
        pytest.skip(f"regenerated golden snapshot ({len(current)} cases)")

    assert GOLDEN.exists(), (
        "golden snapshot missing — run: "
        "SQLGUARD_UPDATE_SNAPSHOTS=1 python -m pytest tests/test_regression.py")
    golden = json.loads(GOLDEN.read_text())

    # Compare per (case, dialect) so a failure names exactly what drifted.
    drift = []
    for case_id in current:
        for dialect in DIALECTS:
            cur = current[case_id]["dialects"][dialect]
            exp = golden.get(case_id, {}).get("dialects", {}).get(dialect)
            if cur != exp:
                drift.append(f"{case_id}/{dialect}: {exp} -> {cur}")
    assert not drift, (
        "guard behavior changed vs golden (likely a sqlglot bump). If intended, "
        "regenerate with SQLGUARD_UPDATE_SNAPSHOTS=1. Drift:\n" + "\n".join(drift))


def test_semantic_invariants_hold_across_all_dialects():
    """Independent of exact strings: every allow_* case ALLOWs and every block_*
    case BLOCKs, in every dialect. Guards against a golden regenerated on a bug."""
    for case_id, sql in CORPUS:
        expect_allow = case_id.startswith("allow_")
        for dialect in DIALECTS:
            r = validate_sql(sql, ALLOW_LIST, source_dialect="postgres",
                             target_dialect=dialect)
            assert r.allowed == expect_allow, f"{case_id}/{dialect}: {r.verdict}"
            if r.allowed:
                assert "LIMIT" in (r.safe_sql or "").upper()
