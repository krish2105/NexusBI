"""Nexus BI text-to-SQL safety layer — defense in depth.

Layer 1  read-only role / engine        (db/target_pool.py)
Layer 2  AST validation (sqlglot)        (validator.py)
Layer 3  allow-list + LIMIT + timeouts   (policy.py)
Layer 4  NL-input injection defense       (sanitizer.py)
Layer 5  dry-run EXPLAIN + repair loop    (guard.py + agents/sql_validator.py)

`guard.py` composes these into the two entry points the agent graph uses:
    screen_question(...)   -- before the LLM (Layer 4)
    validate_sql(...)      -- after the LLM  (Layers 2 + 3, and the Layer-5 hook)
"""
from app.sqlsafety.guard import (  # noqa: F401
    SafetyReport,
    ScreenResult,
    screen_question,
    validate_sql,
)
