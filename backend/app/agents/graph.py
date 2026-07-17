"""The agent graph — bounded-autonomy decision pipeline.

    planner -> schema_retriever -> sql_generator -> sql_validator (SAFETY GATE)
        -> [repair loop <=2] -> executor -> analyst -> forecaster/anomaly -> narrator

Implemented as an explicit, streaming state machine so it runs with or without
``langgraph`` installed (a thin LangGraph adapter can wrap ``run_analysis`` for
checkpointing). Every node transition is yielded as an event for SSE streaming,
so the UI shows the analysis being built. The safety gate is deterministic and
never bypassable: unvalidated SQL cannot reach the executor.
"""
from __future__ import annotations

import time
import uuid
from typing import Iterator

from app.agents.narrator import narrate
from app.agents.planner import plan_question
from app.agents.sql_generator import generate_sql, repair_sql
from app.agents.state import AnalysisState
from app.config import settings
from app.core.tracing import QueryTrace
from app.db.app_store import get_store
from app.db.introspect import cached_allow_list
from app.db.target_pool import ReadOnlyExecutionError, TargetPool
from app.ml.anomaly_detect import detect_anomalies
from app.ml.chart_selector import select_chart
from app.ml.forecasting import forecast_series
from app.rag.retriever import retrieve_schema
from app.sqlsafety import screen_question
from app.sqlsafety.guard import validate_sql

MAX_REPAIRS = 2


def _event(node: str, status: str, **data) -> dict:
    return {"node": node, "status": status, "ts": round(time.time(), 3), **data}


def run_analysis(question: str, connection_id: str = "demo",
                 connection_url: str | None = None,
                 query_id: str | None = None,
                 persist: bool = True) -> Iterator[dict]:
    """Run the pipeline, yielding events. The final event carries the full result."""
    url = connection_url or settings.demo_target_url
    qid = query_id or uuid.uuid4().hex
    store = get_store() if persist else None
    allow = cached_allow_list(url)
    pool = TargetPool(url=url)

    state: AnalysisState = {
        "query_id": qid, "connection_id": connection_id, "connection_url": url,
        "question": question, "repair_attempts": 0, "assumptions": [], "events": [],
    }

    # Optional observability: no-ops entirely when LANGFUSE_* keys are unset.
    trace = QueryTrace(qid, question, connection_id)
    node_spans: dict[str, object] = {}

    def emit(ev: dict) -> dict:
        state["events"].append(ev)
        node, status = ev.get("node"), ev.get("status")
        if status == "running":
            meta = {k: v for k, v in ev.items() if k not in ("node", "status", "ts")}
            node_spans[node] = trace.node_span(node, **meta)
        elif node in node_spans:
            span = node_spans.pop(node)
            out = {k: v for k, v in ev.items()
                   if k not in ("node", "status", "ts", "preview")}
            level = "ERROR" if status == "blocked" else None
            span.update(output=out, level=level)
            span.end()
        if node == "final":
            result = ev.get("result", {})
            trace.finish(output={"blocked": result.get("blocked"),
                                 "confidence": result.get("confidence"),
                                 "generator": result.get("generator")})
            result["trace_url"] = trace.url()
        return ev

    yield emit(_event("start", "ok", query_id=qid, question=question))

    # --- Layer 4: NL input screen (before anything else) ---
    yield emit(_event("guard", "running", label="Screening question"))
    screen = screen_question(question, allow)
    if screen.blocked:
        if store:
            store.append_audit("query.blocked_nl", actor=connection_id,
                               verdict="BLOCK", detail={"control": screen.control,
                                                        "rules": screen.matched_rules,
                                                        "question": question})
        state.update(blocked=True, error="Question blocked by safety screen.")
        yield emit(_event("guard", "blocked", control=screen.control,
                          reasons=screen.reasons))
        yield emit(_finalize(state, blocked=True,
                             message=("This question was blocked by the input-safety "
                                      f"screen ({screen.control}). Nexus answers "
                                      "read-only analytical questions only.")))
        return
    yield emit(_event("guard", "ok"))

    # --- planner ---
    yield emit(_event("planner", "running", label="Planning analysis"))
    plan = plan_question(question)
    state["plan"] = plan
    state["assumptions"] = list(plan.get("assumptions", []))
    if plan.get("write_intent"):
        state.update(blocked=True, error="Write intent blocked.")
        if store:
            store.append_audit("query.blocked_write", actor=connection_id,
                               verdict="BLOCK", detail={"question": question})
        yield emit(_event("planner", "blocked", reason="write intent"))
        yield emit(_finalize(state, blocked=True,
                             message="Nexus is read-only and cannot modify data."))
        return
    yield emit(_event("planner", "ok", intent=plan["intent_summary"],
                      assumptions=state["assumptions"]))

    # --- schema retriever (RAG) ---
    yield emit(_event("schema_retriever", "running", label="Retrieving schema"))
    schema = retrieve_schema(question, connection_url=url, catalog=None)
    state["retrieved_schema"] = [{"table": t.name, "columns": t.column_names()}
                                 for t in schema.tables]
    yield emit(_event("schema_retriever", "ok", tables=schema.table_names(),
                      glossary=[g.term for g in schema.glossary]))

    # --- generate -> validate -> (repair loop) ---
    yield emit(_event("sql_generator", "running", label="Writing SQL"))
    gen = generate_sql(question, schema, plan)
    state["generator"] = gen["generator"]
    report = None
    while True:
        state["sql"] = gen["sql"]
        state["sql_explanation"] = gen["explanation"]
        for a in gen.get("assumptions", []):
            if a not in state["assumptions"]:
                state["assumptions"].append(a)
        yield emit(_event("sql_generator", "ok", sql=gen["sql"],
                          explanation=gen["explanation"], generator=gen["generator"]))

        yield emit(_event("sql_validator", "running", label="Validating (safety gate)"))
        report = validate_sql(gen["sql"], allow, source_dialect="postgres",
                              target_dialect="sqlite")
        if report.allowed:
            # Layer 5: dry-run EXPLAIN before committing to execution.
            try:
                pool.explain(report.safe_sql)
            except ReadOnlyExecutionError as e:
                report = _as_block(f"EXPLAIN failed: {e}")

        if report.allowed:
            state.update(sql_valid=True, safe_sql=report.safe_sql,
                         validation_errors=[])
            yield emit(_event("sql_validator", "ok", verdict="ALLOW",
                              safe_sql=report.safe_sql,
                              tables_used=report.tables_used,
                              limit=report.limit_applied))
            break

        # invalid -> repair loop (capped)
        state["validation_errors"] = report.errors
        if store:
            store.append_audit("sql.rejected", actor=connection_id, sql_text=gen["sql"],
                               verdict="BLOCK", detail={"errors": report.errors,
                                                        "layer": report.layer})
        yield emit(_event("sql_validator", "blocked", verdict="BLOCK",
                          layer=report.layer, errors=report.errors,
                          repair_attempt=state["repair_attempts"]))

        if state["repair_attempts"] >= MAX_REPAIRS:
            state.update(blocked=True, error="SQL failed validation after repairs.")
            yield emit(_finalize(state, blocked=True,
                                 message=("Nexus could not produce a query that passed "
                                          "the safety validator for this question.")))
            return
        state["repair_attempts"] += 1
        yield emit(_event("sql_generator", "running",
                          label=f"Repairing SQL (attempt {state['repair_attempts']})"))
        gen = repair_sql(question, schema, plan, report.errors)

    # --- executor ---
    yield emit(_event("executor", "running", label="Running query (read-only)"))
    try:
        res = pool.execute(report.safe_sql)
    except ReadOnlyExecutionError as e:
        state.update(error=str(e))
        yield emit(_finalize(state, blocked=True,
                             message="The validated query failed to execute."))
        return
    state["result_rows"] = res.rows
    state["result_columns"] = res.columns
    state["result_meta"] = {"row_count": res.row_count, "latency_ms": res.latency_ms,
                            "truncated": res.truncated, "dialect": res.dialect}
    if store:
        store.append_audit("query.executed", actor=connection_id,
                           sql_text=report.safe_sql, row_count=res.row_count,
                           latency_ms=res.latency_ms, verdict="ALLOW")
    yield emit(_event("executor", "ok", row_count=res.row_count,
                      latency_ms=res.latency_ms, columns=res.columns,
                      preview=res.rows[:20]))

    # --- analyst (chart selection) ---
    yield emit(_event("analyst", "running", label="Choosing visualization"))
    chart = select_chart(res.columns, res.rows)
    state["chart_spec"] = chart
    yield emit(_event("analyst", "ok", chart_spec=chart))

    # --- forecaster (conditional) ---
    forecast = None
    if chart.get("forecastable"):
        yield emit(_event("forecaster", "running", label="Forecasting"))
        enc = chart["encodings"]
        labels = [r[enc["x"]] for r in res.rows]
        values = [r[enc["y"]] for r in res.rows]
        fc = forecast_series(labels, values, horizon=settings.forecast_horizon,
                             min_points=settings.forecast_min_points)
        forecast = fc.to_dict() if fc else None
        state["forecast"] = forecast
        yield emit(_event("forecaster", "ok" if forecast else "skipped",
                          forecast=forecast))

    # --- anomaly (conditional) ---
    yield emit(_event("anomaly", "running", label="Scanning for anomalies"))
    anomalies = detect_anomalies(res.columns, res.rows, chart)
    state["anomalies"] = anomalies
    yield emit(_event("anomaly", "ok", anomalies=anomalies, count=len(anomalies)))

    # --- narrator ---
    yield emit(_event("narrator", "running", label="Writing insight"))
    told = narrate(question, res.columns, res.rows, chart, forecast, anomalies,
                   state["assumptions"])
    state["narrative"] = told["narrative"]
    state["confidence"] = told["confidence"]
    yield emit(_event("narrator", "ok", narrative=told["narrative"],
                      confidence=told["confidence"]))

    final = _finalize(state, blocked=False)
    if store:
        store.save_query(connection_id, question, report.safe_sql,
                         told["confidence"], state["assumptions"],
                         state["result_meta"], final["result"], query_id=qid)
    yield emit(final)


def _as_block(msg: str):
    from app.sqlsafety.guard import SafetyReport
    return SafetyReport(verdict="BLOCK", errors=[msg], layer="dry-run EXPLAIN (L5)")


def _finalize(state: AnalysisState, blocked: bool, message: str | None = None) -> dict:
    result = {
        "query_id": state["query_id"],
        "question": state["question"],
        "blocked": blocked,
        "sql": state.get("safe_sql") or state.get("sql"),
        "sql_explanation": state.get("sql_explanation"),
        "generator": state.get("generator"),
        "columns": state.get("result_columns", []),
        "rows": state.get("result_rows", []),
        "result_meta": state.get("result_meta", {}),
        "chart_spec": state.get("chart_spec", {}),
        "forecast": state.get("forecast"),
        "anomalies": state.get("anomalies", []),
        "narrative": state.get("narrative") or message or "",
        "confidence": state.get("confidence", "LOW"),
        "assumptions": state.get("assumptions", []),
        "validation_errors": state.get("validation_errors", []),
        "error": state.get("error"),
        "trace_url": None,
    }
    return _event("final", "blocked" if blocked else "ok", result=result)


def run_analysis_collect(question: str, **kwargs) -> dict:
    """Convenience: run the pipeline and return only the final result."""
    final = None
    for ev in run_analysis(question, **kwargs):
        if ev.get("node") == "final":
            final = ev["result"]
    return final or {"error": "no final event"}
