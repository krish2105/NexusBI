"""Nexus's binding to the `sqlguard` package — the safety guard we publish.

The guard's *implementation* (AST validation, allow-list + LIMIT policy, NL input
screen) lives in **sqlguard** (github.com/krish2105/sqlguard), pinned in
requirements.txt. Nexus deliberately consumes that published artifact rather than
keeping a second copy of the safety code, so the library and the product can
never drift — the guard shipped to users is byte-for-byte the guard defending
this app.

This module is the thin app-specific adapter over it, and only does what an
adapter should:

  * applies Nexus's configured row cap (``settings.target_row_cap``) where the
    library takes a generic ``row_limit``;
  * defaults the execution dialect to the demo's SQLite (the library defaults to
    the source dialect, which is right for a general-purpose library but not for
    this app);
  * labels blocks with Nexus's documented layer numbering (L2 = AST, L3 =
    allow-list; L1 read-only connection and L5 dry-run EXPLAIN are enforced
    outside the library, by target_pool.py and the agent graph).

Entry points used by the app:

    screen_question(question, allow_list)  -> ScreenResult   (Layer 4, pre-LLM)
    validate_sql(sql, allow_list, ...)     -> SafetyReport    (Layers 2+3, post-LLM)
"""
from __future__ import annotations

from sqlguard import GuardReport as SafetyReport  # identical shape; Nexus's name
from sqlguard import ScreenResult, screen_question
from sqlguard import validate_sql as _guard_validate_sql
from sqlguard.policy import AllowList, PolicyResult
from sqlguard.validator import ValidationResult

from app.config import settings

__all__ = ["SafetyReport", "ScreenResult", "screen_question", "validate_sql",
           "AllowList", "PolicyResult", "ValidationResult"]

# Nexus's layer numbering (see docs/SQL_SAFETY.md) mapped onto the library's
# generic labels, so audit entries and the Trust page keep citing L2/L3.
_LAYER_LABELS = {
    "AST validation": "AST validation (L2)",
    "allow-list policy": "allow-list policy (L3)",
}


def validate_sql(sql: str, allow_list: AllowList,
                 source_dialect: str = "postgres",
                 target_dialect: str = "sqlite",
                 row_cap: int | None = None) -> SafetyReport:
    """Run Layers 2 (AST) then 3 (allow-list + LIMIT) on generated SQL.

    ``source_dialect`` is what the generator writes in; ``target_dialect`` is the
    engine we execute against (the SQLite demo transpiles cleanly from Postgres
    SQL). Thin wrapper over :func:`sqlguard.validate_sql`.
    """
    report = _guard_validate_sql(
        sql, allow_list,
        source_dialect=source_dialect,
        target_dialect=target_dialect,
        row_limit=row_cap or settings.target_row_cap,
    )
    if report.layer in _LAYER_LABELS:
        report.layer = _LAYER_LABELS[report.layer]
    return report
