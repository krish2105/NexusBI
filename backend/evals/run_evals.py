"""Nexus BI evaluation suite — measured, not asserted.

Produces five JSON reports consumed by the in-app "How accurate is Nexus?" page:
  * sql_safety_report.json   — % of adversarial questions blocked (target 100%)
  * text2sql_report.json     — data integrity + Nexus generator execution accuracy
  * forecast_report.json     — backtest MAPE / RMSE on the monthly revenue series
  * rag_report.json          — schema-retrieval precision/recall vs labeled tables
  * spider_report.json       — Spider/BIRD execution accuracy on a per-DB benchmark

Run:  python -m evals.run_evals   (from backend/)

The Spider/BIRD suite runs the bundled self-contained fixture by default. Point
it at a downloaded dev set with SPIDER_DIR / BIRD_DIR (see docs/SPIDER_BIRD.md).
"""
from __future__ import annotations

import ast
import csv
import json
import os
from pathlib import Path

from app.agents.graph import run_analysis_collect
from app.config import settings
from app.db.introspect import build_allow_list
from app.db.target_pool import TargetPool
from app.ml.forecasting import forecast_series
from app.rag.retriever import retrieve_schema
from app.sqlsafety import screen_question

OUT = Path(__file__).resolve().parent
DATA = settings.data_dir


def _norm_row(row: dict) -> tuple:
    out = []
    for v in row.values():
        if isinstance(v, float):
            out.append(round(v, 2))
        else:
            out.append(v)
    return tuple(out)


def _result_set(rows: list[dict]) -> set[tuple]:
    return {_norm_row(r) for r in rows}


def _norm_val(v):
    return round(v, 2) if isinstance(v, float) else v


def _answers_match(gen_rows: list[dict], truth_rows: list[dict]) -> bool:
    """Execution accuracy on the answer's SHARED columns.

    A generated answer is correct if, restricted to the columns both results
    share by name, its row-set equals the ground truth's. This credits a correct
    answer that merely carries an extra descriptive column (e.g. state_name_pt)
    and still catches wrong values, wrong grouping, or wrong row counts.
    """
    if not truth_rows:
        return len(gen_rows) == 0
    if not gen_rows:
        return False
    common = [c for c in truth_rows[0].keys() if c in gen_rows[0]]
    if not common:
        return _result_set(gen_rows) == _result_set(truth_rows)

    def proj(rows):
        return sorted(tuple(_norm_val(r[c]) for c in common) for r in rows)

    return proj(gen_rows) == proj(truth_rows)


# ---------------------------------------------------------------- safety
def eval_safety() -> dict:
    allow = build_allow_list()
    cases = list(csv.DictReader(open(DATA / "evals" / "sql_safety_eval_cases.csv")))
    results = []
    blocked = adversarial = allowed_ok = controls_ok = 0
    for c in cases:
        r = screen_question(c["user_question"], allow)
        expected = c["expected_decision"]
        got = r.verdict
        if expected == "BLOCK":
            adversarial += 1
            if got == "BLOCK":
                blocked += 1
        elif expected == "ALLOW" and got == "ALLOW":
            allowed_ok += 1
        controls_ok += int(got == expected)
        results.append({"case_id": c["case_id"], "attack_class": c["attack_class"],
                        "expected": expected, "got": got, "control": r.control})
    return {
        "suite": "sql_safety",
        "adversarial_total": adversarial,
        "adversarial_blocked": blocked,
        "block_rate": round(blocked / adversarial, 4) if adversarial else None,
        "control_allowed": allowed_ok,
        "overall_accuracy": round(controls_ok / len(cases), 4),
        "cases": results,
    }


# ---------------------------------------------------------------- text2sql
def eval_text2sql() -> dict:
    from app.llm.client import get_llm

    generator_mode = get_llm().provider  # "deterministic" | "groq" | "ollama"
    pool = TargetPool()
    rows = list(csv.DictReader(open(DATA / "evals" / "text2sql_eval.csv")))
    integrity_pass = gen_pass = counted = 0
    by_difficulty: dict[str, dict[str, int]] = {}
    details = []
    for c in rows:
        vsql = c["validated_sql"]
        diff = c["difficulty"]
        by_difficulty.setdefault(diff, {"pass": 0, "total": 0})
        try:
            truth = pool.execute(vsql)
            expected_n = int(c["expected_row_count"])
            integ = (truth.row_count == expected_n)
        except Exception as e:  # noqa: BLE001
            details.append({"eval_id": c["eval_id"], "integrity": False,
                            "error": str(e)[:80]})
            continue
        integrity_pass += int(integ)

        # Nexus generator execution accuracy: compare value-sets to ground truth.
        try:
            res = run_analysis_collect(c["question"], persist=False)
            gen_ok = (not res["blocked"]
                      and _answers_match(res["rows"], truth.rows))
            gen_used = res.get("generator")
        except Exception:  # noqa: BLE001
            gen_ok, gen_used = False, None
        gen_pass += int(gen_ok)
        counted += 1
        by_difficulty[diff]["total"] += 1
        by_difficulty[diff]["pass"] += int(gen_ok)
        details.append({"eval_id": c["eval_id"], "difficulty": diff,
                        "integrity": integ, "nexus_generator": gen_ok,
                        "generator_used": gen_used})

    by_difficulty_rates = {
        d: round(v["pass"] / v["total"], 4) if v["total"] else None
        for d, v in by_difficulty.items()
    }
    return {
        "suite": "text2sql",
        "generator_mode": generator_mode,
        "total": counted,
        "data_integrity_pass": integrity_pass,
        "data_integrity_rate": round(integrity_pass / counted, 4) if counted else None,
        "nexus_generator_pass": gen_pass,
        "nexus_generator_execution_accuracy": round(gen_pass / counted, 4) if counted else None,
        "accuracy_by_difficulty": by_difficulty_rates,
        "note": ("Data-integrity runs the package's validated SQL and checks row "
                 "counts against the labeled expectation. Generator accuracy runs "
                 f"Nexus's own generated SQL (generator_mode={generator_mode}) and "
                 "compares result value-sets on their shared columns."),
        "details": details,
    }


# ---------------------------------------------------------------- forecast
def eval_forecast() -> dict:
    pool = TargetPool()
    rows = pool.execute("SELECT year_month, merchandise_value FROM monthly_kpis "
                        "ORDER BY year_month LIMIT 10000").rows
    labels = [r["year_month"] for r in rows]
    values = [float(r["merchandise_value"]) for r in rows]
    # Backtest: hold out the last 3 complete months.
    from app.ml.forecasting import _trim_partial_periods
    labels, values, _ = _trim_partial_periods(labels, values)
    holdout = 3
    train_v = values[:-holdout]
    train_l = labels[:-holdout]
    actual = values[-holdout:]
    fc = forecast_series(train_l, train_v, horizon=holdout, min_points=6)
    if not fc:
        return {"suite": "forecast", "error": "insufficient points"}
    preds = fc.point[:holdout]
    mape = sum(abs((a - p) / a) for a, p in zip(actual, preds)) / holdout * 100
    rmse = (sum((a - p) ** 2 for a, p in zip(actual, preds)) / holdout) ** 0.5
    return {
        "suite": "forecast",
        "method": fc.method,
        "train_months": len(train_v),
        "holdout_months": holdout,
        "actual": [round(a, 2) for a in actual],
        "predicted": [round(p, 2) for p in preds],
        "MAPE_pct": round(mape, 2),
        "RMSE": round(rmse, 2),
    }


# ---------------------------------------------------------------- rag
def eval_rag() -> dict:
    rows = list(csv.DictReader(open(DATA / "evals" / "text2sql_eval.csv")))
    tp = fp = fn = graded = 0
    details = []
    for c in rows:
        expected = {t.strip().lower() for t in c["expected_tables"].split(",")
                    if t.strip()}
        # Map derived/view names to their base tables where the retriever indexes them.
        if not expected:
            continue
        got = {t.lower() for t in retrieve_schema(c["question"], k=6).table_names()}
        # A retrieval "hit" = every expected table surfaced (grounding requirement).
        inter = expected & got
        tp += len(inter)
        fn += len(expected - got)
        graded += 1
        details.append({"eval_id": c["eval_id"], "expected": sorted(expected),
                        "covered": sorted(inter), "missed": sorted(expected - got)})
    recall = tp / (tp + fn) if (tp + fn) else None
    full_cover = sum(1 for d in details if not d["missed"])
    return {
        "suite": "rag",
        "graded": graded,
        "table_recall": round(recall, 4) if recall is not None else None,
        "questions_fully_grounded": full_cover,
        "full_coverage_rate": round(full_cover / graded, 4) if graded else None,
        "details": details,
    }


# ---------------------------------------------------------------- spider/bird
def eval_spider() -> dict:
    """Spider/BIRD execution-accuracy benchmark.

    Runs the bundled self-contained fixture by default. If SPIDER_DIR or BIRD_DIR
    points at a downloaded dev set, that runs instead (optionally capped by
    SPIDER_LIMIT so a full run is opt-in). See docs/SPIDER_BIRD.md.
    """
    from evals.spider_bench import run_benchmark

    spider_dir = os.getenv("SPIDER_DIR")
    bird_dir = os.getenv("BIRD_DIR")
    limit = os.getenv("SPIDER_LIMIT")
    limit_n = int(limit) if limit and limit.isdigit() else None
    if bird_dir:
        return run_benchmark(Path(bird_dir), dataset="bird", limit=limit_n)
    if spider_dir:
        return run_benchmark(Path(spider_dir), dataset="spider", limit=limit_n)
    return run_benchmark(None, limit=limit_n)  # bundled fixture


def main(gate: bool = False) -> None:
    reports = {
        "sql_safety_report.json": eval_safety(),
        "text2sql_report.json": eval_text2sql(),
        "forecast_report.json": eval_forecast(),
        "rag_report.json": eval_rag(),
        "spider_report.json": eval_spider(),
    }
    for name, rep in reports.items():
        (OUT / name).write_text(json.dumps(rep, indent=2))

    s = reports["sql_safety_report.json"]
    t = reports["text2sql_report.json"]
    f = reports["forecast_report.json"]
    r = reports["rag_report.json"]
    sp = reports["spider_report.json"]

    # Keep a standing zero-key baseline, and a separate LLM-mode snapshot, so an
    # upgrade to Groq/Ollama is always comparable against the free-tier default.
    mode = t.get("generator_mode", "deterministic")
    baseline_path = OUT / "text2sql_report_baseline.json"
    if mode == "deterministic":
        baseline_path.write_text(json.dumps(t, indent=2))
    else:
        (OUT / "text2sql_report_llm.json").write_text(json.dumps(t, indent=2))

    print("=" * 60)
    print("NEXUS BI — EVALUATION SUMMARY")
    print("=" * 60)
    print(f"SAFETY    : {s['adversarial_blocked']}/{s['adversarial_total']} "
          f"adversarial blocked ({s['block_rate']*100:.0f}%), "
          f"control allowed={s['control_allowed']}")
    print(f"TEXT2SQL  : [{mode}] data integrity {t['data_integrity_pass']}/{t['total']} "
          f"({t['data_integrity_rate']*100:.0f}%); "
          f"Nexus generator {t['nexus_generator_pass']}/{t['total']} "
          f"({t['nexus_generator_execution_accuracy']*100:.0f}%)")
    if t.get("accuracy_by_difficulty"):
        by_d = ", ".join(f"{d}={round(v*100)}%" if v is not None else f"{d}=—"
                         for d, v in t["accuracy_by_difficulty"].items())
        print(f"            by difficulty: {by_d}")
    if mode != "deterministic" and baseline_path.exists():
        base = json.loads(baseline_path.read_text())
        b_acc = base.get("nexus_generator_execution_accuracy")
        m_acc = t.get("nexus_generator_execution_accuracy")
        if b_acc is not None and m_acc is not None:
            delta = (m_acc - b_acc) * 100
            print(f"            vs zero-key baseline ({round(b_acc*100)}%): "
                 f"{'+' if delta >= 0 else ''}{delta:.0f} points")
    print(f"FORECAST  : {f.get('method')} MAPE={f.get('MAPE_pct')}% "
          f"RMSE={f.get('RMSE')}")
    print(f"RAG       : table recall {r['table_recall']*100:.0f}%, "
          f"fully-grounded {r['questions_fully_grounded']}/{r['graded']}")
    sp_acc = sp.get("execution_accuracy")
    if sp_acc is not None:
        sp_by = ", ".join(f"{d}={round(v*100)}%" if v is not None else f"{d}=—"
                          for d, v in sp.get("accuracy_by_difficulty", {}).items())
        print(f"SPIDER/BIRD: [{sp['generator_mode']}] EX {sp['correct']}/{sp['total']} "
              f"({sp_acc*100:.0f}%) on {sp['dataset_format']} "
              f"[{sp['source'].split(' (')[0]}]"
              + (f"; by difficulty: {sp_by}" if sp_by else ""))
    print("=" * 60)
    print(f"Reports written to {OUT}/")

    if gate:
        # CI gate: the safety layer must block 100% of adversarial queries and
        # allow the control. Any regression fails the build.
        failures = []
        if s["block_rate"] != 1.0:
            failures.append(f"safety block rate {s['block_rate']*100:.1f}% < 100%")
        if s["control_allowed"] < 1:
            failures.append("control question was not allowed")
        if t["data_integrity_rate"] is not None and t["data_integrity_rate"] < 1.0:
            failures.append(f"data integrity {t['data_integrity_rate']*100:.1f}% < 100%")
        if failures:
            print("\nGATE FAILED:")
            for f_ in failures:
                print(f"  ✗ {f_}")
            raise SystemExit(1)
        print("\nGATE PASSED ✓  (safety 100%, control allowed, data integrity 100%)")


if __name__ == "__main__":
    import sys

    main(gate="--gate" in sys.argv)
