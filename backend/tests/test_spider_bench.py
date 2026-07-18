"""Spider/BIRD benchmark — matcher unit tests + end-to-end fixture run.

The end-to-end test runs the *whole* Nexus pipeline against the bundled
Spider-format fixture and checks execution accuracy is measured correctly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from evals.spider_bench import (
    _gold_has_order_by,
    execution_match,
    load_examples,
    run_benchmark,
)


# ----------------------------------------------------------- matcher: EX
def test_exact_match_unordered():
    gold = [(1, "a"), (2, "b")]
    pred = [(2, "b"), (1, "a")]  # different row order, no ORDER BY in gold
    assert execution_match(pred, gold, order_matters=False)


def test_order_matters_rejects_reordered():
    gold = [(1,), (2,), (3,)]
    pred = [(3,), (2,), (1,)]
    assert not execution_match(pred, gold, order_matters=True)
    # ...but the same rows in order pass.
    assert execution_match([(1,), (2,), (3,)], gold, order_matters=True)


def test_column_order_ignored():
    gold = [("France", 2), ("US", 1)]
    pred = [(2, "France"), (1, "US")]  # columns swapped
    assert execution_match(pred, gold, order_matters=False)


def test_extra_predicted_column_tolerated():
    # Nexus adds a descriptive column; the gold columns are still all present.
    gold = [("Hardware", 65.0)]
    pred = [("Hardware", "H", 65.0)]
    assert execution_match(pred, gold, order_matters=False)


def test_numeric_normalization():
    # int 4 (COUNT) vs float 4.0, and rounding.
    assert execution_match([(4.0,)], [(4,)], order_matters=False)
    assert execution_match([(38.75,)], [(38.750001,)], order_matters=False)
    # numeric-looking strings normalize like numbers ("300" == 300.0).
    assert execution_match([("300",)], [(300.0,)], order_matters=False)


def test_wrong_values_rejected():
    assert not execution_match([(5,)], [(4,)], order_matters=False)


def test_row_count_mismatch_rejected():
    assert not execution_match([(1,), (2,)], [(1,)], order_matters=False)


def test_fewer_predicted_columns_rejected():
    # Prediction is missing a gold column entirely.
    assert not execution_match([("France",)], [("France", 2)], order_matters=False)


def test_per_column_match_still_checks_full_rows():
    # Each column individually contains {1,2} and {"a","b"}, but the ROW pairing
    # differs — must be rejected (per-column equality alone is not enough).
    gold = [(1, "a"), (2, "b")]
    pred = [(1, "b"), (2, "a")]
    assert not execution_match(pred, gold, order_matters=False)


def test_both_empty_match():
    assert execution_match([], [], order_matters=False)


# ---------------------------------------------------- top-level ORDER BY
def test_order_by_detection():
    assert _gold_has_order_by("SELECT a FROM t ORDER BY a")
    assert not _gold_has_order_by("SELECT a FROM t")
    # ORDER BY inside a subquery does not constrain the outer result.
    assert not _gold_has_order_by(
        "SELECT a FROM (SELECT a FROM t ORDER BY a LIMIT 5)")


# ------------------------------------------------------------ loader
def test_bird_format_detection(tmp_path):
    (tmp_path / "dev_databases" / "toy").mkdir(parents=True)
    import sqlite3

    db = tmp_path / "dev_databases" / "toy" / "toy.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (x INT)")
    con.commit()
    con.close()
    (tmp_path / "dev.json").write_text(json.dumps(
        [{"db_id": "toy", "question": "how many rows?",
          "SQL": "SELECT COUNT(*) FROM t", "difficulty": "simple"}]))
    examples, db_root, gold_key = load_examples(tmp_path, dataset="auto")
    assert gold_key == "SQL"               # BIRD uses the SQL key
    assert db_root.name == "dev_databases"
    assert examples[0]["db_id"] == "toy"


# -------------------------------------------------- end-to-end fixture
@pytest.fixture(scope="module")
def report():
    return run_benchmark(root=None)  # bundled fixture


def test_fixture_runs_end_to_end(report):
    assert report["suite"] == "spider_bird"
    assert report["dataset_format"] == "spider"
    assert report["total"] == 14
    assert report["skipped"] == 0
    assert report["gold_errors"] == 0        # every gold query is valid SQL
    assert report["blocked"] == 0            # safety gate blocks none of these


def test_fixture_execution_accuracy_measured(report):
    acc = report["execution_accuracy"]
    assert acc is not None
    # The deterministic single-table generator answers the aggregations but not
    # the joins — an honest, non-trivial slice of the accuracy band.
    assert 0.3 <= acc <= 1.0
    assert report["correct"] == round(acc * report["total"])


def test_fixture_answers_single_table_aggregations(report):
    """Questions the zero-key generator should get right must score correct."""
    by_q = {d["question"]: d for d in report["details"]}
    for q in ("What is the average age of the singers?",
              "What is the total amount across all orders?",
              "How many singers are there from each country?"):
        assert by_q[q]["status"] == "correct", f"regressed on: {q}"


# ------------------------------------------------------------- determinism
def test_benchmark_is_deterministic_across_hash_seeds():
    """The benchmark score (and the SQL behind it) must not depend on
    PYTHONHASHSEED.

    Regression for a real bug: the catalog built its table map by iterating a
    *set* of table names, so `catalog.tables` insertion order — and therefore
    every downstream tie-break (schema retrieval, base-table choice) — varied
    per process. The same fixture scored anywhere from 7/14 to 9/14 run to run,
    which also meant a user could get different SQL for the same question after
    a restart. Runs in subprocesses because PYTHONHASHSEED is fixed at
    interpreter start and cannot be changed in-process.
    """
    import subprocess
    import sys

    prog = (
        "import json, hashlib;"
        "from evals.spider_bench import run_benchmark;"
        "r = run_benchmark(None);"
        "p = json.dumps([(d['question'], d['status'], d.get('predicted_sql'))"
        "                for d in r['details']], sort_keys=True);"
        "print(hashlib.sha256(p.encode()).hexdigest(), r['correct'])"
    )
    fingerprints = set()
    for seed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run([sys.executable, "-c", prog], capture_output=True,
                             text=True, env=env,
                             cwd=Path(__file__).resolve().parent.parent)
        assert out.returncode == 0, f"seed {seed} failed:\n{out.stderr[-2000:]}"
        fingerprints.add(out.stdout.strip())
    assert len(fingerprints) == 1, (
        f"benchmark is hash-seed dependent; got {len(fingerprints)} distinct "
        f"results: {fingerprints}")


def test_catalog_table_order_is_sorted():
    """The root cause, pinned directly: catalog table order must be stable
    (sorted), not set-iteration order."""
    import sqlite3
    import tempfile

    from app.db.target_pool import TargetPool
    from app.rag.catalog import build_catalog

    path = Path(tempfile.mkdtemp()) / "t.sqlite"
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE zebra (id INT); CREATE TABLE alpha (id INT);"
                      "CREATE TABLE middle (id INT);")
    con.commit()
    con.close()
    cat = build_catalog(TargetPool(url=f"sqlite:///{path}"), with_samples=False,
                        use_reference_dictionary=False)
    assert list(cat.tables.keys()) == ["alpha", "middle", "zebra"]
