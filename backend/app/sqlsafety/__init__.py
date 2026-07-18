"""Nexus BI text-to-SQL safety layer — defense in depth.

Layer 1  read-only role / engine          (db/target_pool.py)
Layer 2  AST validation (sqlglot)          -> sqlguard.validator
Layer 3  allow-list + LIMIT + timeouts     -> sqlguard.policy
Layer 4  NL-input injection defense        -> sqlguard.sanitizer
Layer 5  dry-run EXPLAIN + repair loop     (guard.py + agents/graph.py)

**Layers 2–4 are the `sqlguard` package** (github.com/krish2105/sqlguard) — our
own OSS extraction of this guard, pinned in requirements.txt. Nexus consumes the
published library instead of vendoring a copy, so there is exactly one
implementation of the safety rules and it is the one users `pip install`.
Layers 1 and 5 stay here because they need a live database connection.

`guard.py` is the thin app adapter (Nexus's row cap, execution dialect, and layer
labels) exposing the two entry points the agent graph uses:
    screen_question(...)   -- before the LLM (Layer 4)
    validate_sql(...)      -- after the LLM  (Layers 2 + 3, and the Layer-5 hook)
"""
from sqlguard.policy import AllowList, PolicyResult, enforce_policy  # noqa: F401
from sqlguard.validator import ValidationResult, validate_ast  # noqa: F401

from app.sqlsafety.guard import (  # noqa: F401
    SafetyReport,
    ScreenResult,
    screen_question,
    validate_sql,
)

__all__ = [
    "SafetyReport", "ScreenResult", "screen_question", "validate_sql",
    "AllowList", "PolicyResult", "enforce_policy",
    "ValidationResult", "validate_ast",
]
