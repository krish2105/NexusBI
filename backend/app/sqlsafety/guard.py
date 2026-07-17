"""Composition of the safety layers into the interfaces the agent graph calls.

    screen_question(question, allow_list)  -> ScreenResult   (Layer 4, pre-LLM)
    validate_sql(sql, allow_list, ...)     -> SafetyReport    (Layers 2+3, post-LLM)

The graph's ``sql_validator`` node calls ``validate_sql``; on BLOCK it feeds the
structured errors back to ``sql_generator`` for a capped repair (Layer 5), and
never lets unvalidated SQL reach the executor.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings
from app.sqlsafety.policy import AllowList, PolicyResult, enforce_policy
from app.sqlsafety.sanitizer import ScreenResult, screen_question
from app.sqlsafety.validator import ValidationResult, validate_ast

__all__ = ["SafetyReport", "ScreenResult", "screen_question", "validate_sql"]


@dataclass
class SafetyReport:
    verdict: str                                  # "ALLOW" | "BLOCK"
    safe_sql: str | None = None                   # LIMIT-enforced SQL to execute
    errors: list[str] = field(default_factory=list)
    tables_used: list[str] = field(default_factory=list)
    limit_applied: int | None = None
    layer: str | None = None                      # which layer produced a BLOCK
    validation: ValidationResult | None = None
    policy: PolicyResult | None = None

    @property
    def allowed(self) -> bool:
        return self.verdict == "ALLOW"


def validate_sql(sql: str, allow_list: AllowList,
                 source_dialect: str = "postgres",
                 target_dialect: str = "sqlite",
                 row_cap: int | None = None) -> SafetyReport:
    """Run Layers 2 (AST) then 3 (allow-list + LIMIT) on generated SQL.

    ``source_dialect`` is what the LLM writes in; ``target_dialect`` is the engine
    we execute against (the SQLite demo transpiles cleanly from Postgres SQL).
    """
    row_cap = row_cap or settings.target_row_cap

    v = validate_ast(sql, dialect=source_dialect)
    if not v.valid:
        return SafetyReport(verdict="BLOCK", errors=v.errors, layer="AST validation (L2)",
                            validation=v)

    p = enforce_policy(v.ast, allow_list, row_cap=row_cap, target_dialect=target_dialect)
    if not p.ok:
        return SafetyReport(verdict="BLOCK", errors=p.errors,
                            layer="allow-list policy (L3)", validation=v, policy=p)

    return SafetyReport(
        verdict="ALLOW", safe_sql=p.safe_sql, tables_used=p.tables_used,
        limit_applied=p.limit_applied, validation=v, policy=p,
    )
