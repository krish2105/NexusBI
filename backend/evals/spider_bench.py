"""Spider / BIRD text-to-SQL benchmark — end-to-end, execution-accuracy based.

Runs the *whole* Nexus pipeline (grounding → generation → 5-layer safety gate →
dialect transpile → read-only execution) against a text-to-SQL benchmark and
scores it with **execution accuracy (EX)** — the standard Spider/BIRD metric:
a prediction is correct when its result set equals the gold query's result set.

Three things make this a real benchmark, not a mock:

  * Each example runs against its own SQLite database via ``connection_url`` — the
    same per-connection catalog/allow-list/retriever/generator path the product
    uses, so nothing about the Olist demo leaks in.
  * The gold SQL is executed as reference truth on the same database.
  * The matcher is the recognized EX semantics: order-agnostic multiset equality,
    order-sensitive when the gold query has a top-level ORDER BY, with column
    permutation so column ordering doesn't matter and an extra descriptive
    column (which Nexus sometimes adds) doesn't wrongly fail a correct answer.

Dataset formats (auto-detected by :func:`load_examples`):

  * **Spider**  — ``dev.json`` with ``query`` gold + ``database/<db_id>/<db_id>.sqlite``
  * **BIRD**    — ``dev.json`` with ``SQL`` gold + ``dev_databases/<db_id>/<db_id>.sqlite``

With no dataset provided it builds and runs a small self-contained Spider-format
fixture (``evals/spider/fixture.py``) so the benchmark always runs.

CLI::

    python -m evals.spider_bench                       # bundled fixture
    python -m evals.spider_bench --dir /data/spider    # full Spider dev set
    python -m evals.spider_bench --dir /data/bird --dataset bird --limit 200
"""
from __future__ import annotations

import itertools
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.agents.graph import run_analysis_collect
from app.config import settings

OUT = Path(__file__).resolve().parent
_FIXTURE_CACHE = settings.data_dir.parent.parent / "var" / "spider_fixture"

# Cap column-permutation search so a wide result set can't blow up the matcher.
_MAX_PERM_COLS = 7


# ----------------------------------------------------------------- EX matcher
def _norm_scalar(v: Any) -> Any:
    """Normalize a cell so trivially-equal values compare equal.

    Numbers → rounded float (so int 4 == 4.0 from AVG/SUM, and 38.750001 == 38.75);
    everything else → its stripped string form.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).strip()
    # A numeric-looking string ("300", "300.0") normalizes like a number.
    try:
        return round(float(s), 2)
    except (TypeError, ValueError):
        return s


def _as_row_tuples(rows: list) -> list[tuple]:
    """Coerce rows (list[dict] from Nexus, or list[tuple] from sqlite) to tuples."""
    out: list[tuple] = []
    for r in rows:
        if isinstance(r, dict):
            out.append(tuple(_norm_scalar(v) for v in r.values()))
        elif isinstance(r, (list, tuple)):
            out.append(tuple(_norm_scalar(v) for v in r))
        else:
            out.append((_norm_scalar(r),))
    return out


def _gold_has_order_by(sql: str) -> bool:
    """True when the gold query's own result order is significant.

    ORDER BY inside a subquery doesn't constrain the outer result, so only a
    top-level ORDER BY counts. A light depth scan (parens) approximates this
    without a full parse and is robust to the dialect the gold is written in.
    """
    depth = 0
    for m in re.finditer(r"[()]|order\s+by", sql, re.IGNORECASE):
        tok = m.group(0)
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            return True
    return False


def _multiset(rows: list[tuple]) -> dict:
    counts: dict[tuple, int] = {}
    for r in rows:
        counts[r] = counts.get(r, 0) + 1
    return counts


def execution_match(pred_rows: list, gold_rows: list, order_matters: bool) -> bool:
    """Execution accuracy: do the predicted rows equal the gold rows?

    Column ordering is ignored (we search a column permutation), and a prediction
    carrying *extra* columns still matches if some subset of its columns equals
    the gold columns — this credits Nexus adding a descriptive label column while
    still requiring every gold column to be present with the correct values.
    """
    gold = _as_row_tuples(gold_rows)
    pred = _as_row_tuples(pred_rows)

    if len(gold) != len(pred):
        return False
    if not gold:  # both empty
        return True

    g_cols = len(gold[0])
    p_cols = len(pred[0])
    if p_cols < g_cols:
        return False

    # Column-major view of each side.
    gold_cm = [tuple(row[i] for row in gold) for i in range(g_cols)]
    pred_cm = [tuple(row[i] for row in pred) for i in range(p_cols)]

    def cols_equal(gc: tuple, pc: tuple) -> bool:
        return gc == pc if order_matters else _multiset([(x,) for x in gc]) == \
            _multiset([(x,) for x in pc])

    # Fast path: exact column count and identical column order.
    if g_cols == p_cols:
        if order_matters:
            if gold == pred:
                return True
        else:
            if _multiset(gold) == _multiset(pred):
                return True

    # Search an assignment of gold columns to (distinct) predicted columns.
    # Bounded by _MAX_PERM_COLS so this stays cheap.
    if p_cols > _MAX_PERM_COLS:
        # Too wide to permute safely: fall back to same-position comparison.
        if g_cols != p_cols:
            return False
        return (gold == pred) if order_matters else (_multiset(gold) == _multiset(pred))

    # Candidate predicted columns for each gold column (prune by column equality).
    candidates = [
        [j for j in range(p_cols) if cols_equal(gold_cm[i], pred_cm[j])]
        for i in range(g_cols)
    ]
    if any(not c for c in candidates):
        return False

    # Try injective assignments; verify the full ROW multiset (not just per-column),
    # because per-column equality alone can't guarantee rows line up.
    for perm in itertools.product(*candidates):
        if len(set(perm)) != g_cols:
            continue
        projected = [tuple(row[j] for j in perm) for row in pred]
        if order_matters:
            if projected == gold:
                return True
        elif _multiset(projected) == _multiset(gold):
            return True
    return False


# ------------------------------------------------------------------- loading
def load_examples(root: Path, dataset: str = "auto") -> tuple[list[dict], Path, str]:
    """Load a Spider/BIRD dataset. Returns (examples, db_root, gold_key).

    ``examples`` are dicts with at least ``db_id``, ``question`` and the gold SQL
    (under whichever key the format uses). ``db_root`` is the directory holding
    ``<db_id>/<db_id>.sqlite`` subfolders.
    """
    root = Path(root)
    # Locate the manifest.
    manifest = None
    for cand in (root / "dev.json", root / "dev" / "dev.json", root / "train.json"):
        if cand.exists():
            manifest = cand
            break
    if manifest is None:
        raise FileNotFoundError(f"no dev.json/train.json found under {root}")
    examples = json.loads(manifest.read_text())

    # Locate the database directory (Spider: database/, BIRD: dev_databases/).
    db_root = None
    for cand in (root / "database", root / "dev_databases", root / "databases"):
        if cand.exists():
            db_root = cand
            break
    if db_root is None:
        raise FileNotFoundError(f"no database/ or dev_databases/ dir under {root}")

    # Gold SQL key: Spider uses "query", BIRD uses "SQL".
    sample = examples[0] if examples else {}
    if dataset == "spider" or "query" in sample:
        gold_key = "query"
    elif dataset == "bird" or "SQL" in sample:
        gold_key = "SQL"
    else:
        gold_key = "query" if "query" in sample else "SQL"
    return examples, db_root, gold_key


def _db_path(db_root: Path, db_id: str) -> Path:
    return db_root / db_id / f"{db_id}.sqlite"


def _run_gold(db_file: Path, sql: str) -> list[tuple]:
    """Execute the gold query as trusted reference truth (read-only)."""
    uri = f"{db_file.as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=15)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# ------------------------------------------------------------------ runner
def run_benchmark(root: Path | None = None, dataset: str = "auto",
                  limit: int | None = None) -> dict:
    """Run the benchmark and return a report dict (also the run_evals entrypoint)."""
    from app.llm.client import get_llm

    if root is None:
        from evals.spider.fixture import build_fixture

        root = build_fixture(_FIXTURE_CACHE)
        dataset = "spider"
        source = "bundled fixture (evals/spider/fixture.py)"
    else:
        source = str(root)

    examples, db_root, gold_key = load_examples(Path(root), dataset)
    if limit:
        examples = examples[:limit]

    generator_mode = get_llm().provider
    correct = counted = skipped = blocked = gold_errors = 0
    by_diff: dict[str, dict[str, int]] = {}
    details = []
    t0 = time.perf_counter()

    for ex in examples:
        db_id = ex["db_id"]
        question = ex["question"]
        gold_sql = ex.get(gold_key)
        db_file = _db_path(db_root, db_id)
        diff = (ex.get("db_difficulty") or ex.get("difficulty") or "unknown").lower()
        by_diff.setdefault(diff, {"correct": 0, "total": 0})

        if not db_file.exists() or not gold_sql:
            skipped += 1
            details.append({"db_id": db_id, "question": question,
                            "status": "skipped", "reason": "missing db or gold"})
            continue

        # Reference truth first: if the gold itself can't run, don't score it.
        try:
            gold_rows = _run_gold(db_file, gold_sql)
        except Exception as e:  # noqa: BLE001
            gold_errors += 1
            details.append({"db_id": db_id, "question": question,
                            "status": "gold_error", "reason": str(e)[:120]})
            continue

        url = f"sqlite:///{db_file}"
        try:
            res = run_analysis_collect(question, connection_url=url,
                                       connection_id=f"spider:{db_id}", persist=False)
        except Exception as e:  # noqa: BLE001
            res = {"blocked": True, "error": str(e)[:120]}

        counted += 1
        by_diff[diff]["total"] += 1
        was_blocked = bool(res.get("blocked"))
        blocked += int(was_blocked)
        pred_rows = res.get("rows") or []
        ok = (not was_blocked) and execution_match(
            pred_rows, gold_rows, _gold_has_order_by(gold_sql))
        correct += int(ok)
        by_diff[diff]["correct"] += int(ok)
        details.append({
            "db_id": db_id, "question": question, "difficulty": diff,
            "status": "correct" if ok else ("blocked" if was_blocked else "wrong"),
            "generator": res.get("generator"),
            "predicted_sql": (res.get("sql") or "").replace("\n", " ").strip(),
            "gold_sql": gold_sql, "gold_rows": len(gold_rows),
            "pred_rows": len(pred_rows),
        })

    by_diff_rates = {
        d: round(v["correct"] / v["total"], 4) if v["total"] else None
        for d, v in sorted(by_diff.items())
    }
    return {
        "suite": "spider_bird",
        "source": source,
        "dataset_format": "bird" if gold_key == "SQL" else "spider",
        "generator_mode": generator_mode,
        "total": counted,
        "correct": correct,
        "execution_accuracy": round(correct / counted, 4) if counted else None,
        "blocked": blocked,
        "skipped": skipped,
        "gold_errors": gold_errors,
        "accuracy_by_difficulty": by_diff_rates,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "metric": ("Execution accuracy (EX): predicted result set equals the gold "
                   "query's result set — order-agnostic unless the gold has a "
                   "top-level ORDER BY; column order ignored; extra predicted "
                   "columns tolerated."),
        "note": (f"Full pipeline (safety gate included) per example, "
                 f"generator_mode={generator_mode}. Each question runs against its "
                 "own database via connection_url."),
        "details": details,
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Nexus BI Spider/BIRD benchmark (EX).")
    ap.add_argument("--dir", type=str, default=None,
                    help="Path to a Spider/BIRD dataset dir (default: bundled fixture).")
    ap.add_argument("--dataset", choices=["auto", "spider", "bird"], default="auto")
    ap.add_argument("--limit", type=int, default=None, help="Max examples to run.")
    ap.add_argument("--out", type=str, default=str(OUT / "spider_report.json"))
    args = ap.parse_args()

    rep = run_benchmark(Path(args.dir) if args.dir else None,
                        dataset=args.dataset, limit=args.limit)
    Path(args.out).write_text(json.dumps(rep, indent=2))

    print("=" * 60)
    print("NEXUS BI — SPIDER/BIRD BENCHMARK (execution accuracy)")
    print("=" * 60)
    print(f"source    : {rep['source']}  [{rep['dataset_format']}]")
    print(f"generator : {rep['generator_mode']}")
    acc = rep["execution_accuracy"]
    print(f"EX        : {rep['correct']}/{rep['total']} "
          f"({acc * 100:.1f}%)" if acc is not None else "EX        : n/a")
    if rep["accuracy_by_difficulty"]:
        by_d = ", ".join(f"{d}={round(v * 100)}%" if v is not None else f"{d}=—"
                         for d, v in rep["accuracy_by_difficulty"].items())
        print(f"by diff   : {by_d}")
    print(f"blocked   : {rep['blocked']}   skipped: {rep['skipped']}   "
          f"gold_errors: {rep['gold_errors']}   ({rep['elapsed_s']}s)")
    print("=" * 60)
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
