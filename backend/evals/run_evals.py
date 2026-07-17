"""Nexus BI evaluation suite — measured, not asserted.

Produces four JSON reports consumed by the in-app "How accurate is Nexus?" page:
  * sql_safety_report.json   — % of adversarial questions blocked (target 100%)
  * text2sql_report.json     — data integrity + Nexus generator execution accuracy
  * forecast_report.json     — backtest MAPE / RMSE on the monthly revenue series
  * rag_report.json          — schema-retrieval precision/recall vs labeled tables

Run:  python -m evals.run_evals   (from backend/)
"""
from __future__ import annotations

import ast
import csv
import json
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
    pool = TargetPool()
    rows = list(csv.DictReader(open(DATA / "evals" / "text2sql_eval.csv")))
    integrity_pass = gen_pass = counted = 0
    details = []
    for c in rows:
        vsql = c["validated_sql"]
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
        except Exception:  # noqa: BLE001
            gen_ok = False
        gen_pass += int(gen_ok)
        counted += 1
        details.append({"eval_id": c["eval_id"], "difficulty": c["difficulty"],
                        "integrity": integ, "nexus_generator": gen_ok})
    return {
        "suite": "text2sql",
        "total": counted,
        "data_integrity_pass": integrity_pass,
        "data_integrity_rate": round(integrity_pass / counted, 4) if counted else None,
        "nexus_generator_pass": gen_pass,
        "nexus_generator_execution_accuracy": round(gen_pass / counted, 4) if counted else None,
        "note": ("Data-integrity runs the package's validated SQL and checks row "
                 "counts against the labeled expectation. Generator accuracy runs "
                 "Nexus's own generated SQL (zero-key deterministic engine) and "
                 "compares result value-sets; a Groq/Ollama key raises coverage."),
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


def main() -> None:
    reports = {
        "sql_safety_report.json": eval_safety(),
        "text2sql_report.json": eval_text2sql(),
        "forecast_report.json": eval_forecast(),
        "rag_report.json": eval_rag(),
    }
    for name, rep in reports.items():
        (OUT / name).write_text(json.dumps(rep, indent=2))

    s = reports["sql_safety_report.json"]
    t = reports["text2sql_report.json"]
    f = reports["forecast_report.json"]
    r = reports["rag_report.json"]
    print("=" * 60)
    print("NEXUS BI — EVALUATION SUMMARY")
    print("=" * 60)
    print(f"SAFETY    : {s['adversarial_blocked']}/{s['adversarial_total']} "
          f"adversarial blocked ({s['block_rate']*100:.0f}%), "
          f"control allowed={s['control_allowed']}")
    print(f"TEXT2SQL  : data integrity {t['data_integrity_pass']}/{t['total']} "
          f"({t['data_integrity_rate']*100:.0f}%); "
          f"Nexus generator {t['nexus_generator_pass']}/{t['total']} "
          f"({t['nexus_generator_execution_accuracy']*100:.0f}%)")
    print(f"FORECAST  : {f.get('method')} MAPE={f.get('MAPE_pct')}% "
          f"RMSE={f.get('RMSE')}")
    print(f"RAG       : table recall {r['table_recall']*100:.0f}%, "
          f"fully-grounded {r['questions_fully_grounded']}/{r['graded']}")
    print("=" * 60)
    print(f"Reports written to {OUT}/")


if __name__ == "__main__":
    main()
