"""Layer 4 — NL-input injection & intent defense.

The user's *question* is untrusted input. Before it ever reaches the SQL
generator we screen it for: prompt-injection ("ignore your instructions..."),
destructive intent (delete/drop/update...), system-catalog probing, dangerous
functions, credential/exfiltration requests, tenant-escape, and resource-abuse /
unbounded-scan intent. Allow-list awareness lets us flag probes for tables or
columns that don't exist on the connection without blocking legitimate questions.

Deterministic and explainable — every block cites the rule that fired. A real
deployment can add a constrained LLM intent-classifier behind this same
interface; the deterministic screen is the fast, auditable first pass.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.sqlsafety.policy import AllowList


@dataclass
class ScreenResult:
    blocked: bool
    control: str | None = None       # which control fired
    reasons: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return "BLOCK" if self.blocked else "ALLOW"


# (control_label, rule_name, compiled_pattern)
_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    # --- prompt injection ---
    ("NL injection screen", "ignore-instructions",
     re.compile(r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|all|above|your)\b.{0,20}\b(rule|rules|instruction|instructions|prompt)\b", re.I)),
    ("NL injection screen", "developer-mode",
     re.compile(r"\b(developer|god|admin|jailbreak|dan)\s*mode\b", re.I)),
    ("NL injection screen", "reveal-system-prompt",
     re.compile(r"\b(reveal|show|print|expose|leak)\b.{0,25}\b(system\s*prompt|instructions|hidden\s*rules)\b", re.I)),
    ("NL injection screen", "decode-and-execute",
     re.compile(r"\b(decode|deobfuscate|unescape)\b.{0,30}\b(execute|run|payload)\b", re.I)),
    # --- destructive DML / DDL intent ---
    ("NL intent screen (DML/DDL)", "destructive-verb",
     re.compile(r"\b(delete|drop|truncate|alter|update|insert\s+into|overwrite|wipe|erase|purge)\b", re.I)),
    ("NL intent screen (DML/DDL)", "grant-revoke",
     re.compile(r"\b(grant|revoke)\b.{0,30}\b(access|privilege|superuser|role|permission)\b", re.I)),
    ("NL intent screen (DML/DDL)", "create-table",
     re.compile(r"\bcreate\b.{0,15}\b(table|view|database|schema|role|user)\b", re.I)),
    ("NL intent screen (DML/DDL)", "select-into",
     re.compile(r"\b(select\b.{0,40}\binto|into\s+\w*backup|copy\b.{0,20}\binto)\b", re.I)),
    # --- system catalog probing ---
    ("system-catalog deny-list", "pg-catalog",
     re.compile(r"\b(pg_catalog|information_schema|pg_shadow|pg_authid|pg_roles|pg_user|pg_tables|pg_class)\b", re.I)),
    # --- dangerous functions / file & network access ---
    ("dangerous-function deny-list", "dangerous-fn",
     re.compile(r"\b(pg_sleep|pg_read_file|pg_read_binary_file|pg_ls_dir|dblink|lo_import|lo_export|load_file|readfile|xp_cmdshell)\b", re.I)),
    ("dangerous-function deny-list", "local-file",
     re.compile(r"(/etc/passwd|/etc/shadow|file://|\bread\b.{0,15}\bfile\b)", re.I)),
    # --- credential / exfiltration ---
    # No trailing \b: must still match plural probes ("connection strings", "API keys").
    ("intent screen (credentials)", "credentials",
     re.compile(r"\b(password|passwd|api[_\s-]?key|secret|token|connection\s*string|credential|superuser)", re.I)),
    ("AST/command + read-only", "exfiltration",
     re.compile(r"\b(copy)\b.{0,20}\b(to\s+program|to\s+stdout)\b|\bcurl\b|\bexfiltrat", re.I)),
    ("procedure/command", "stored-proc",
     re.compile(r"\b(call|exec|execute)\b.{0,25}\b(procedure|proc|function|sp_)\b", re.I)),
    # --- tenant escape ---
    ("per-connection isolation", "tenant-escape",
     re.compile(r"\b(ignore|switch|change)\b.{0,30}\b(selected\s+connection|another\s+(customer|database|tenant)|other\s+database)\b", re.I)),
    # --- resource abuse / unbounded scan ---
    ("cost/EXPLAIN + row cap", "resource-abuse",
     re.compile(r"\bcross\s+join\b|\bjoin\b.{0,20}\bitself\b|\b(ten|hundred|1000|a\s+million)\s+times\b", re.I)),
    ("scope policy + enforced LIMIT", "unbounded-scan",
     re.compile(r"\bevery\s+table\b|\ball\s+tables\b|(\bevery\s+row\b.{0,30}\bevery\s+column\b)|\b(dump|export)\b.{0,15}\b(everything|all\s+data)\b", re.I)),
]

# Standalone SQL keyword smuggled into an NL box (e.g. "Show revenue; DROP TABLE").
_SEMI_CHAIN = re.compile(r";\s*\w+", re.I)
# A snake_case identifier is almost always a schema probe, not natural language.
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
# Dotted table.column reference.
_DOTTED = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", re.I)


def screen_question(question: str, allow_list: AllowList | None = None) -> ScreenResult:
    reasons: list[str] = []
    rules: list[str] = []
    controls: list[str] = []

    for control, rule, pattern in _RULES:
        if pattern.search(question):
            controls.append(control)
            rules.append(rule)
            reasons.append(f"matched '{rule}'")

    # Multi-statement smuggling inside the NL box.
    if question.count(";") >= 1 and _SEMI_CHAIN.search(question):
        # only meaningful if it looks like chained SQL, not prose with a semicolon
        if re.search(r";\s*(drop|delete|update|insert|truncate|alter|grant|select)\b",
                     question, re.I):
            controls.append("single-statement AST rule")
            rules.append("semicolon-chain")
            reasons.append("statement chaining detected in question")

    # Allow-list-aware probes for tables/columns that don't exist.
    if allow_list is not None:
        tables = {t.lower() for t in allow_list}
        cols_by_table = {t.lower(): {c.lower() for c in cs}
                         for t, cs in allow_list.items()}
        all_cols = set().union(*cols_by_table.values()) if cols_by_table else set()

        for m in _DOTTED.finditer(question):
            t, c = m.group(1).lower(), m.group(2).lower()
            if t in cols_by_table and c not in cols_by_table[t]:
                controls.append("column allow-list")
                rules.append("unknown-column")
                reasons.append(f"'{t}.{c}' is not a real column")

        for m in _SNAKE.finditer(question):
            tok = m.group(0).lower()
            if tok in tables or tok in all_cols:
                continue
            if "." in tok:
                continue
            # snake_case token that is neither a real table nor column: schema probe
            controls.append("connection-specific table allow-list")
            rules.append("unknown-identifier")
            reasons.append(f"'{tok}' is not a known table or column on this connection")

    blocked = bool(rules)
    return ScreenResult(
        blocked=blocked,
        control=controls[0] if controls else None,
        reasons=sorted(set(reasons)),
        matched_rules=sorted(set(rules)),
    )
