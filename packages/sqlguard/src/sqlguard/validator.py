"""Layer 1 — deterministic AST validation with sqlglot. No LLM involved.

Rule of thumb: **reject unless proven safe.** SQL is accepted only when it parses
to exactly one read-only ``SELECT`` (or ``WITH ... SELECT``) whose entire tree is
free of DML/DDL/command nodes, dangerous functions, system-catalog access, and
write-producing constructs (``SELECT INTO``, ``... RETURNING`` inside a
data-modifying CTE, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# --- Any of these node types anywhere in the tree => reject ------------------
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Drop, exp.Alter, exp.Create, exp.TruncateTable,
    exp.Grant, exp.Copy, exp.Command,          # Command = catch-all for CALL/VACUUM/etc.
    exp.Into,                                   # SELECT ... INTO new_table
)
# Names in case an exotic dialect maps to a class we didn't import.
FORBIDDEN_NODE_NAMES = {
    "Insert", "Update", "Delete", "Merge", "Drop", "Alter", "Create",
    "TruncateTable", "Grant", "Revoke", "Copy", "Command", "Into",
    "Set", "Use", "Transaction", "Commit", "Rollback", "Vacuum", "Analyze",
}

# --- Dangerous / side-effecting or exfiltrating functions --------------------
DANGEROUS_FUNCTIONS = {
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir",
    "pg_stat_file", "pg_reload_conf", "pg_terminate_backend", "lo_import",
    "lo_export", "dblink", "dblink_exec", "dblink_connect", "copy_from",
    "query_to_xml", "xpath", "load_extension", "readfile", "load_file",
    "sys_exec", "sys_eval", "current_setting", "set_config",
}
DANGEROUS_PREFIXES = ("pg_", "dblink", "lo_")

# --- Schemas / catalogs that must never be reachable via generated SQL ------
BLOCKED_SCHEMAS = {"pg_catalog", "information_schema", "pg_temp", "pg_toast"}
BLOCKED_TABLE_PREFIXES = ("pg_",)  # pg_shadow, pg_authid, pg_stat_*, ...


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)   # referenced base tables
    statement_kind: str = "unknown"
    ast: exp.Expression | None = None

    @property
    def verdict(self) -> str:
        return "ALLOW" if self.valid else "BLOCK"


def _is_readonly_top(node: exp.Expression) -> bool:
    """Top statement must be a SELECT, a UNION/set-op of SELECTs, or WITH->SELECT."""
    if isinstance(node, exp.Select):
        return True
    if isinstance(node, (exp.Union, exp.Except, exp.Intersect)):
        return True
    if isinstance(node, exp.Subquery):
        return _is_readonly_top(node.this)
    return False


def validate_ast(sql: str, dialect: str = "postgres") -> ValidationResult:
    """Parse ``sql`` in ``dialect`` and validate it is a single read-only query."""
    errors: list[str] = []

    if not sql or not sql.strip():
        return ValidationResult(False, ["empty SQL"])

    # (a) Parse. Reject multiple statements (blocks ;-chaining / comment smuggling).
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except ParseError as e:
        return ValidationResult(False, [f"parse error: {str(e).splitlines()[0]}"])

    if len(statements) == 0:
        return ValidationResult(False, ["no statement parsed"])
    if len(statements) > 1:
        return ValidationResult(
            False, [f"multiple statements are not allowed (found {len(statements)})"])

    root = statements[0]

    # (b) Top-level node must be read-only.
    if not _is_readonly_top(root):
        return ValidationResult(
            False, [f"only SELECT / WITH...SELECT queries are allowed, "
                    f"got {type(root).__name__}"],
            statement_kind=type(root).__name__)

    # (c) No forbidden node type ANYWHERE in the tree (catches write CTEs, INTO...).
    for node in root.walk():
        tname = type(node).__name__
        if isinstance(node, FORBIDDEN_NODES) or tname in FORBIDDEN_NODE_NAMES:
            errors.append(f"forbidden {tname} node is not permitted in a read query")

    # (d) Dangerous functions.
    for fn in root.find_all(exp.Anonymous, exp.Func):
        name = (fn.name or "").lower()
        if not name:
            continue
        if name in DANGEROUS_FUNCTIONS or name.startswith(DANGEROUS_PREFIXES):
            errors.append(f"dangerous function '{name}' is denied")

    # (e) System catalog / blocked schema access.
    base_tables: list[str] = []
    for tbl in root.find_all(exp.Table):
        tname = (tbl.name or "").lower()
        schema = (tbl.db or "").lower()
        base_tables.append(tname)
        if schema in BLOCKED_SCHEMAS:
            errors.append(f"access to schema '{schema}' is denied")
        if tname.startswith(BLOCKED_TABLE_PREFIXES):
            errors.append(f"access to system catalog '{tname}' is denied")

    valid = not errors
    return ValidationResult(
        valid=valid,
        errors=sorted(set(errors)),
        tables=sorted(set(t for t in base_tables if t)),
        statement_kind=type(root).__name__,
        ast=root if valid else None,
    )
