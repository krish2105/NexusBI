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

from app.agents.followup import resolve as resolve_followup
from app.agents.narrator import narrate
from app.agents.planner import plan_question
from app.agents.sql_generator import generate_sql, repair_sql
from app.agents.state import AnalysisState
from app.ml.rootcause import explain_change
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
                 persist: bool = True,
                 conversation_id: str | None = None,
                 history: list[dict] | None = None,
                 seed_plan: dict | None = None) -> Iterator[dict]:
    """Run the pipeline, yielding events. The final event carries the full result.

    When ``conversation_id`` is set, prior turns in the thread are loaded and the
    question is resolved as a follow-up (drill/filter/pivot or a "why" root-cause)
    before planning — turning independent queries into an analyst dialogue."""
    url = connection_url or settings.demo_target_url
    qid = query_id or uuid.uuid4().hex
    store = get_store() if persist else None
    allow = cached_allow_list(url)
    pool = TargetPool(url=url)

    if history is None and conversation_id and store:
        history = store.conversation_context(conversation_id)

    state: AnalysisState = {
        "query_id": qid, "connection_id": connection_id, "connection_url": url,
        "question": question, "repair_attempts": 0, "assumptions": [], "events": [],
        "conversation_id": conversation_id,
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

    # --- context resolver (multi-turn follow-up understanding) ---
    resolution = None
    display_question = question
    if history:
        yield emit(_event("context_resolver", "running", label="Understanding context"))
        resolution = resolve_followup(question, history, url)
        if resolution.is_followup:
            display_question = resolution.standalone_question
            yield emit(_event("context_resolver", "ok", mode=resolution.mode,
                              resolved=resolution.standalone_question,
                              inherited=resolution.inherited,
                              changed=resolution.changed))
            # "why did it change?" -> root-cause decomposition branch
            if resolution.mode == "why":
                yield from _run_rootcause(state, resolution, url, allow, store,
                                          connection_id, emit)
                return
        else:
            yield emit(_event("context_resolver", "ok", mode="fresh"))

    # --- planner ---
    yield emit(_event("planner", "running", label="Planning analysis"))
    if seed_plan is not None:
        plan = seed_plan              # caller-supplied plan (e.g. a dashboard tile)
    elif resolution and resolution.mode == "refine" and resolution.seed_plan:
        plan = resolution.seed_plan   # carried forward from the prior turn + delta
    else:
        plan = plan_question(question)
    # Semantic layer: if the question names a governed metric, compute it from the
    # *certified* definition rather than the planner's guess. Skip when a caller
    # supplied the plan (dashboard tile) or a follow-up carried it forward — those
    # already carry a resolved metric.
    governed_metric = None
    if store and seed_plan is None and not (resolution and resolution.mode == "refine"):
        try:
            from app.agents.semantic import resolve_metric, seed_demo_metrics
            if connection_id == "demo":
                seed_demo_metrics(store, connection_id)
            resolved = resolve_metric(display_question, store.list_metrics(connection_id))
            if resolved:
                plan["metric"] = {k: resolved[k] for k in ("expr", "base", "alias", "term")}
                governed_metric = resolved["governed"]
                # A governed metric overrides the planner's default-revenue guess.
                plan["assumptions"] = [a for a in plan.get("assumptions", [])
                                       if not a.startswith("Interpreted 'revenue'")]
        except Exception:  # noqa: BLE001 - never break analysis on the semantic layer
            governed_metric = None
    state["governed_metric"] = governed_metric
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
                      assumptions=state["assumptions"],
                      governed_metric=governed_metric))

    # --- schema retriever (RAG) — uses the resolved standalone question ---
    yield emit(_event("schema_retriever", "running", label="Retrieving schema"))
    schema = retrieve_schema(display_question, connection_url=url, catalog=None)
    state["retrieved_schema"] = [{"table": t.name, "columns": t.column_names()}
                                 for t in schema.tables]
    yield emit(_event("schema_retriever", "ok", tables=schema.table_names(),
                      glossary=[g.term for g in schema.glossary]))

    # --- generate -> validate -> (repair loop) ---
    yield emit(_event("sql_generator", "running", label="Writing SQL"))
    gen = generate_sql(display_question, schema, plan)
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
                              target_dialect=pool.sqlglot_dialect)
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
    told = narrate(display_question, res.columns, res.rows, chart, forecast, anomalies,
                   state["assumptions"])
    state["narrative"] = told["narrative"]
    state["confidence"] = told["confidence"]
    state["resolved_question"] = display_question if resolution and \
        resolution.is_followup else None
    state["suggested_followups"] = _suggest_followups(plan, chart)
    yield emit(_event("narrator", "ok", narrative=told["narrative"],
                      confidence=told["confidence"]))

    final = _finalize(state, blocked=False)
    if store:
        store.save_query(connection_id, question, report.safe_sql,
                         told["confidence"], state["assumptions"],
                         state["result_meta"], final["result"], query_id=qid,
                         conversation_id=conversation_id,
                         turn_index=(store.next_turn_index(conversation_id)
                                     if conversation_id else None),
                         context={"plan": _storable_plan(plan)})
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
        "conversation_id": state.get("conversation_id"),
        "resolved_question": state.get("resolved_question"),
        "suggested_followups": state.get("suggested_followups", []),
        "rootcause": state.get("rootcause"),
        "governed_metric": state.get("governed_metric"),
    }
    return _event("final", "blocked" if blocked else "ok", result=result)


def _storable_plan(plan: dict) -> dict:
    """Compact, JSON-safe slice of the plan stored as turn context for follow-ups."""
    return {k: plan.get(k) for k in
            ("metric", "dimension", "shape", "top_n", "filters", "is_time_series")}


def _suggest_followups(plan: dict, chart: dict) -> list[str]:
    """Context-aware next questions to power one-click follow-up chips."""
    out: list[str] = []
    ctype = chart.get("type")
    dim = (plan.get("dimension") or {}).get("label")
    has_filter = bool(plan.get("filters"))
    if ctype in ("bar", "grouped_bar"):
        out.append("Show it monthly over time")
        if dim != "state_code":
            out.append("Break it down by state")
        out.append("Just the North region")
    if ctype == "line":
        out.append("Why did it change?")
        out.append("Break it down by category")
        out.append("Just delivered orders")
    if ctype == "kpi":
        out.append("Break it down by category")
        out.append("Show it monthly over time")
    if has_filter:
        out.append("Compare across all regions")
    # de-dup, cap at 3
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:3]


def _run_rootcause(state, resolution, url, allow, store, connection_id, emit):
    """The 'why did it change?' branch — contribution/decomposition analysis."""
    yield emit(_event("rootcause", "running", label="Decomposing the change"))
    plan = resolution.why_context["plan"]
    rc = explain_change(plan, url=url)
    if not rc.get("available"):
        state.update(error=rc.get("reason"))
        yield emit(_event("rootcause", "skipped", reason=rc.get("reason")))
        yield emit(_finalize(state, blocked=False,
                             message="I couldn't decompose that change "
                                     f"({rc.get('reason')})."))
        return

    contributors = rc["contributors"]
    columns = ["member", "from", "to", "delta", "contribution_pct"]
    rows = [{k: c.get(k) for k in columns} for c in contributors]
    chart = {"type": "bar", "reason": "contribution to change",
             "encodings": {"x": "member", "y": "delta"}, "forecastable": False}
    state.update(
        sql=rc.get("sql"), safe_sql=rc.get("sql"),
        sql_explanation=f"Contribution of each {rc['decomposition_dimension']} to the "
                        f"change from {rc['period_from']} to {rc['period_to']}.",
        generator="deterministic", result_columns=columns, result_rows=rows,
        result_meta={"row_count": len(rows), "latency_ms": 0},
        chart_spec=chart, narrative=rc["narrative"], confidence="HIGH",
        rootcause=rc,
        suggested_followups=[f"Show {contributors[0]['member']} over time",
                             "Break it down by region"] if contributors else [],
    )
    if store:
        store.append_audit("query.rootcause", actor=connection_id,
                           sql_text=rc.get("sql"), verdict="ALLOW",
                           detail={"dimension": rc["decomposition_dimension"]})
    yield emit(_event("rootcause", "ok", narrative=rc["narrative"],
                      contributors=contributors))
    final = _finalize(state, blocked=False)
    if store:
        store.save_query(connection_id, state["question"], rc.get("sql"), "HIGH", [],
                         state["result_meta"], final["result"],
                         query_id=state["query_id"],
                         conversation_id=state.get("conversation_id"),
                         turn_index=(store.next_turn_index(state["conversation_id"])
                                     if state.get("conversation_id") else None),
                         context={"plan": _storable_plan(plan)})
    yield emit(final)


def run_analysis_collect(question: str, **kwargs) -> dict:
    """Convenience: run the pipeline and return only the final result."""
    final = None
    for ev in run_analysis(question, **kwargs):
        if ev.get("node") == "final":
            final = ev["result"]
    return final or {"error": "no final event"}
