"""Decision-intelligence surfaces: RFM segments, feedback loop, Trust Center."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import (authorize_connection, get_current_user,
                          resolve_connection_url)
from app.core.tracing import is_enabled as tracing_enabled
from app.db.app_store import get_store
from app.llm.client import get_llm
from app.ml.segmentation import segment_customers

router = APIRouter(tags=["insights"])


# --- RFM segmentation -------------------------------------------------------
@router.get("/insights/segments")
def segments(connection_id: str = "demo",
             user: dict | None = Depends(get_current_user)):
    authorize_connection(connection_id, user)
    url = resolve_connection_url(connection_id)
    return segment_customers(url=url).to_dict()


# --- feedback loop ----------------------------------------------------------
class FeedbackRequest(BaseModel):
    rating: str            # "up" | "down"
    note: str | None = None


@router.post("/query/{query_id}/feedback")
def submit_feedback(query_id: str, req: FeedbackRequest):
    if req.rating not in ("up", "down"):
        raise HTTPException(400, "rating must be 'up' or 'down'")
    store = get_store()
    q = store.get_query(query_id)
    fid = store.add_feedback(
        query_id, req.rating, req.note,
        connection_id=q["connection_id"] if q else None,
        question=q["question"] if q else None,
        sql=q["sql"] if q else None)
    store.append_audit("query.feedback", verdict=req.rating,
                       detail={"query_id": query_id, "note": req.note})
    return {"id": fid, "rating": req.rating, "stats": store.feedback_stats()}


@router.get("/feedback/stats")
def feedback_stats():
    store = get_store()
    return {**store.feedback_stats(), "vetted_examples": store.vetted_examples(20)}


# --- Trust Center -----------------------------------------------------------
def _forecast_summary(forecast: dict) -> dict:
    """Compact forecast head-to-head for the Trust page: per grain, the engines'
    RMSE and the winner, plus whether the LSTM variant is present + reproducible."""
    comparison = forecast.get("comparison", {}) if isinstance(forecast, dict) else {}
    grains = {}
    for grain, cmp in comparison.items():
        if not isinstance(cmp, dict) or cmp.get("error"):
            continue
        engines = {}
        for name, m in (cmp.get("methods") or {}).items():
            engines[name] = None if not m else {
                "rmse": m.get("rmse"), "mape_pct": m.get("mape_pct"),
                "folds": m.get("folds"),
                "band_coverage_95": m.get("band_coverage_95"),
            }
        grains[grain] = {"best": cmp.get("best"), "n_origins": cmp.get("n_origins"),
                         "holdout": cmp.get("holdout"), "engines": engines}
    return {
        "eval": "rolling-origin walk-forward, errors pooled across folds",
        "torch_available": forecast.get("torch_available"),
        "lstm_reproducible": forecast.get("lstm_reproducible"),
        "backend": forecast.get("forecast_backend"),
        "grains": grains,
    }


@router.get("/trust/summary")
def trust_summary():
    """Everything that makes Nexus trustworthy, in one payload."""
    store = get_store()
    audit = store.list_audit(limit=1000)
    executed = sum(1 for a in audit if a["action"] == "query.executed")
    blocked = sum(1 for a in audit if a["verdict"] == "BLOCK")

    from app.api.misc import evals as _evals  # reuse eval-report loader
    reports = _evals()
    safety = reports.get("sql_safety", {}) if isinstance(reports, dict) else {}
    t2s = reports.get("text2sql", {}) if isinstance(reports, dict) else {}
    forecast = reports.get("forecast", {}) if isinstance(reports, dict) else {}
    rag = reports.get("rag", {}) if isinstance(reports, dict) else {}
    spider = reports.get("spider", {}) if isinstance(reports, dict) else {}

    return {
        "safety": {
            "block_rate": safety.get("block_rate"),
            "adversarial_blocked": safety.get("adversarial_blocked"),
            "adversarial_total": safety.get("adversarial_total"),
            "cases": safety.get("cases", []),
        },
        "accuracy": {
            "data_integrity_rate": t2s.get("data_integrity_rate"),
            "generator_execution_accuracy": t2s.get("nexus_generator_execution_accuracy"),
            "forecast_mape_pct": forecast.get("MAPE_pct"),
            "rag_table_recall": rag.get("table_recall"),
            "spider_execution_accuracy": spider.get("execution_accuracy"),
            "spider_dataset": spider.get("dataset_format"),
            "spider_generator_mode": spider.get("generator_mode"),
        },
        "forecast": _forecast_summary(forecast),
        "governance": {
            "queries_executed": executed,
            "queries_blocked": blocked,
            "audit_entries": len(audit),
        },
        "observability": {
            "tracing_enabled": tracing_enabled(),
            "llm_provider": get_llm().provider,
        },
        "feedback": store.feedback_stats(),
        "principles": [
            "Read-only by construction — destructive queries are impossible.",
            "The LLM plans & narrates; the database and ML compute every number.",
            "Every answer shows its SQL, assumptions, and confidence.",
            "Every query is logged to an append-only audit trail.",
        ],
    }
