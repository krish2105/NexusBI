"""sqlguard — a deterministic, dialect-aware safety guard for LLM-generated SQL.

Make destructive or exfiltrating queries impossible by construction: a query is
accepted only when it parses to a single read-only SELECT whose entire AST is
free of DML/DDL, dangerous functions, and system-catalog access — optionally
allow-listed against your real schema, with a LIMIT enforced and the safe query
transpiled to your database's dialect. No LLM, no network; fully deterministic.

    from sqlguard import SqlGuard
    guard = SqlGuard({"orders": {"id", "amount"}}, target_dialect="mysql")
    report = guard.check("SELECT amount FROM orders")
    report.allowed     # True
    report.safe_sql    # 'SELECT `amount` FROM `orders` LIMIT 10000'
"""
from .guard import GuardReport, SqlBlocked, SqlGuard, validate_sql
from .policy import DEFAULT_ROW_LIMIT, AllowList, PolicyResult, enforce_policy
from .sanitizer import ScreenResult, screen_question
from .validator import ValidationResult, validate_ast

__version__ = "0.1.0"

__all__ = [
    "SqlGuard", "GuardReport", "SqlBlocked", "validate_sql",
    "screen_question", "ScreenResult",
    "validate_ast", "ValidationResult",
    "enforce_policy", "PolicyResult", "AllowList", "DEFAULT_ROW_LIMIT",
    "__version__",
]
