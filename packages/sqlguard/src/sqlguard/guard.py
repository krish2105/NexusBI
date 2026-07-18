"""The composed guard.

Two entry points:

    guard = SqlGuard(allow_list, target_dialect="mysql")
    report = guard.check(sql)          # validate + allow-list + LIMIT + transpile
    screen = guard.screen_question(q)  # optional NL pre-screen

or functionally:

    from sqlguard import validate_sql, screen_question
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .policy import DEFAULT_ROW_LIMIT, AllowList, PolicyResult, enforce_policy
from .sanitizer import ScreenResult, screen_question
from .validator import ValidationResult, validate_ast


@dataclass
class GuardReport:
    verdict: str                                  # "ALLOW" | "BLOCK"
    safe_sql: str | None = None                   # LIMIT-enforced, transpiled SQL
    errors: list[str] = field(default_factory=list)
    tables_used: list[str] = field(default_factory=list)
    limit_applied: int | None = None
    layer: str | None = None                      # which layer produced a BLOCK
    validation: ValidationResult | None = None
    policy: PolicyResult | None = None

    @property
    def allowed(self) -> bool:
        return self.verdict == "ALLOW"

    def raise_for_verdict(self) -> "GuardReport":
        """Raise ``SqlBlocked`` if the query was not allowed; else return self."""
        if not self.allowed:
            raise SqlBlocked(self.errors, self.layer)
        return self


class SqlBlocked(Exception):
    """Raised by ``GuardReport.raise_for_verdict`` / ``SqlGuard.ensure`` on BLOCK."""

    def __init__(self, errors: list[str], layer: str | None = None):
        self.errors = errors
        self.layer = layer
        super().__init__(f"[{layer or 'sqlguard'}] " + "; ".join(errors))


def validate_sql(sql: str, allow_list: AllowList | None = None,
                 source_dialect: str = "postgres",
                 target_dialect: str | None = None,
                 row_limit: int | None = None) -> GuardReport:
    """Validate generated SQL and return a :class:`GuardReport`.

    ``source_dialect`` is the grammar the SQL is written in; ``target_dialect``
    (defaults to source) is what the safe query is transpiled to. If
    ``allow_list`` is empty/None, table/column checks are skipped (single
    read-only query + LIMIT is still enforced).
    """
    target_dialect = target_dialect or source_dialect
    row_limit = row_limit or DEFAULT_ROW_LIMIT

    v = validate_ast(sql, dialect=source_dialect)
    if not v.valid:
        return GuardReport(verdict="BLOCK", errors=v.errors,
                           layer="AST validation", validation=v)

    p = enforce_policy(v.ast, allow_list, row_limit=row_limit,
                       target_dialect=target_dialect)
    if not p.ok:
        return GuardReport(verdict="BLOCK", errors=p.errors,
                           layer="allow-list policy", validation=v, policy=p)

    return GuardReport(
        verdict="ALLOW", safe_sql=p.safe_sql, tables_used=p.tables_used,
        limit_applied=p.limit_applied, validation=v, policy=p,
    )


class SqlGuard:
    """Reusable guard bound to a schema + dialects.

    >>> guard = SqlGuard({"orders": {"id", "amount"}})
    >>> guard.check("SELECT amount FROM orders").allowed
    True
    >>> guard.check("DROP TABLE orders").allowed
    False
    """

    def __init__(self, allow_list: AllowList | None = None, *,
                 source_dialect: str = "postgres",
                 target_dialect: str | None = None,
                 row_limit: int = DEFAULT_ROW_LIMIT):
        self.allow_list = allow_list or {}
        self.source_dialect = source_dialect
        self.target_dialect = target_dialect or source_dialect
        self.row_limit = row_limit

    def check(self, sql: str) -> GuardReport:
        return validate_sql(sql, self.allow_list or None, self.source_dialect,
                            self.target_dialect, self.row_limit)

    def ensure(self, sql: str) -> str:
        """Return the safe SQL, or raise ``SqlBlocked``. Convenience for callers
        that want an exception rather than a report."""
        report = self.check(sql).raise_for_verdict()
        return report.safe_sql  # type: ignore[return-value]

    def screen_question(self, question: str) -> ScreenResult:
        return screen_question(question, self.allow_list or None)
