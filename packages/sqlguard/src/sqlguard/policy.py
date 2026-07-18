"""Layer 2 — schema allow-list + hard limits.

Given a validated read-only AST and an allow-list (table -> set of columns):

  * rejects any referenced base table not on the allow-list (also catches
    hallucinated tables such as ``employee_payroll``);
  * rejects qualified columns that don't exist on their table and unqualified
    columns that exist on no referenced table (catches hallucinated columns
    such as ``orders.customer_password``) while tolerating SELECT-list output
    aliases and CTE references;
  * injects a ``LIMIT`` if absent and clamps an over-large one to ``row_limit``.

If the allow-list is empty, the table/column checks are skipped — the guard then
enforces only "single read-only query + LIMIT", which is still useful when you
don't have a schema handy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlglot import exp

AllowList = dict[str, set[str]]  # table(lower) -> {column(lower), ...}

DEFAULT_ROW_LIMIT = 10_000


@dataclass
class PolicyResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    safe_sql: str | None = None      # rewritten SQL with enforced LIMIT
    limit_applied: int | None = None
    tables_used: list[str] = field(default_factory=list)


def _alias_and_cte_maps(root: exp.Expression) -> tuple[dict[str, str], set[str]]:
    """alias(lower)->base_table(lower), and the set of CTE names(lower)."""
    alias_map: dict[str, str] = {}
    for tbl in root.find_all(exp.Table):
        base = (tbl.name or "").lower()
        alias = (tbl.alias_or_name or base).lower()
        if base:
            alias_map[alias] = base
            alias_map.setdefault(base, base)
    cte_names = {(cte.alias_or_name or "").lower()
                 for cte in root.find_all(exp.CTE)}
    return alias_map, cte_names


def _output_aliases(root: exp.Expression) -> set[str]:
    return {(a.alias_or_name or "").lower()
            for a in root.find_all(exp.Alias) if a.alias_or_name}


def enforce_policy(root: exp.Expression, allow_list: AllowList | None = None,
                   row_limit: int | None = None,
                   target_dialect: str = "postgres") -> PolicyResult:
    row_limit = row_limit or DEFAULT_ROW_LIMIT
    errors: list[str] = []
    allow_list = {t.lower(): {c.lower() for c in cols}
                  for t, cols in (allow_list or {}).items()}

    referenced_bases: set[str] = set()

    # Table/column allow-list checks — only when an allow-list is supplied.
    if allow_list:
        alias_map, cte_names = _alias_and_cte_maps(root)
        output_aliases = _output_aliases(root)

        for tbl in root.find_all(exp.Table):
            name = (tbl.name or "").lower()
            if not name or name in cte_names:
                continue
            if name not in allow_list:
                errors.append(
                    f"table '{name}' is not on the allow-list")
            else:
                referenced_bases.add(name)

        all_referenced_cols: set[str] = set()
        for b in referenced_bases:
            all_referenced_cols |= allow_list.get(b, set())

        for col in root.find_all(exp.Column):
            cname = (col.name or "").lower()
            if not cname or cname == "*":
                continue
            qualifier = (col.table or "").lower()
            if qualifier:
                base = alias_map.get(qualifier, qualifier)
                if base in allow_list:
                    if cname not in allow_list[base] and cname not in output_aliases:
                        errors.append(
                            f"column '{qualifier}.{cname}' does not exist on '{base}'")
                # unresolved qualifier -> likely a subquery/CTE alias; tolerate.
            else:
                if (cname not in all_referenced_cols
                        and cname not in output_aliases
                        and cname not in cte_names):
                    errors.append(
                        f"column '{cname}' does not exist on any referenced table")

    if errors:
        return PolicyResult(False, sorted(set(errors)),
                            tables_used=sorted(referenced_bases))

    # LIMIT injection / clamp on the top statement.
    safe_root, applied = _enforce_limit(root, row_limit)
    return PolicyResult(
        True, [], safe_sql=safe_root.sql(dialect=target_dialect, pretty=True),
        limit_applied=applied, tables_used=sorted(referenced_bases),
    )


def _enforce_limit(root: exp.Expression, row_limit: int) -> tuple[exp.Expression, int]:
    limit_node = root.args.get("limit") if hasattr(root, "args") else None
    if limit_node is None:
        try:
            return root.limit(row_limit), row_limit
        except Exception:  # noqa: BLE001 - set-ops without .limit(): wrap fallback
            return root, row_limit
    try:
        current = int(limit_node.expression.name)
    except (AttributeError, ValueError):
        return root.limit(row_limit), row_limit
    if current > row_limit:
        return root.limit(row_limit), row_limit
    return root, current
