"""Semantic catalog — grounds SQL generation in the *real* schema + business meaning.

Built from three real sources shipped with the data package:
  * ``data_dictionary.csv`` — every column's type, nullability, grain, definition;
  * ``business_glossary.csv`` — metric term -> canonical SQL (revenue, AOV, ...);
  * the live introspected schema — authoritative column list + sample values.

The catalog is what stops the model inventing column names: the generator only
ever sees tables/columns that exist, described in the org's own language.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from functools import lru_cache

from app.config import settings
from app.db.target_pool import TargetPool


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool
    definition: str = ""
    samples: list[str] = field(default_factory=list)


@dataclass
class Table:
    name: str
    grain: str
    columns: list[Column] = field(default_factory=list)

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def card(self, max_cols: int = 40) -> str:
        """Compact, prompt-friendly description for the SQL generator."""
        lines = [f"TABLE {self.name} — {self.grain}"]
        for c in self.columns[:max_cols]:
            extra = f" e.g. {', '.join(map(str, c.samples[:3]))}" if c.samples else ""
            defn = f" — {c.definition}" if c.definition else ""
            lines.append(f"  - {c.name} ({c.data_type}){defn}{extra}")
        return "\n".join(lines)


@dataclass
class GlossaryEntry:
    term: str
    definition: str
    canonical_sql: str
    required_tables: list[str]
    caveats: str = ""

    def card(self) -> str:
        req = ", ".join(self.required_tables)
        return (f'"{self.term}" = {self.canonical_sql}  '
                f"(tables: {req}){'; ' + self.caveats if self.caveats else ''}")


@dataclass
class Catalog:
    tables: dict[str, Table]
    glossary: list[GlossaryEntry]

    def allow_list(self) -> dict[str, set[str]]:
        return {t.name.lower(): {c.name.lower() for c in t.columns}
                for t in self.tables.values()}


def _load_data_dictionary(path) -> dict[str, dict]:
    by_table: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = row["table_name"].strip()
            by_table.setdefault(t, {"grain": row.get("grain", ""), "cols": []})
            by_table[t]["cols"].append({
                "name": row["column_name"].strip(),
                "type": row["data_type"].strip(),
                "nullable": row.get("nullable", "").strip().lower() in ("yes", "true", "1"),
                "definition": row.get("definition", "").strip(),
            })
    return by_table


def _load_glossary(path) -> list[GlossaryEntry]:
    entries: list[GlossaryEntry] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            req = [t.strip() for t in row.get("required_tables", "").split(",") if t.strip()]
            entries.append(GlossaryEntry(
                term=row["term"].strip(),
                definition=row.get("definition", "").strip(),
                canonical_sql=row.get("canonical_sql", "").strip(),
                required_tables=req,
                caveats=row.get("caveats", "").strip(),
            ))
    return entries


def _sample_values(pool: TargetPool, table: str, column: str,
                   data_type: str) -> list[str]:
    # Sample a couple of real values for low-cardinality text/id columns to aid grounding.
    if data_type.upper() not in ("TEXT", "VARCHAR", "CHAR"):
        return []
    try:
        r = pool.execute(
            f'SELECT DISTINCT "{column}" AS v FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL LIMIT 3')
        return [str(row["v"]) for row in r.rows]
    except Exception:  # noqa: BLE001 - sampling is best-effort
        return []


def build_catalog(pool: TargetPool | None = None, with_samples: bool = True) -> Catalog:
    pool = pool or TargetPool()
    dict_path = settings.data_dir / "data_dictionary.csv"
    gloss_path = settings.data_dir / "business_glossary.csv"

    dd = _load_data_dictionary(dict_path)
    glossary = _load_glossary(gloss_path)
    live_tables = {t.lower() for t in pool.list_tables()}

    tables: dict[str, Table] = {}
    for tname, meta in dd.items():
        if tname.lower() not in live_tables:
            continue  # dictionary describes tables not loaded in the SQLite demo
        live_cols = {c.lower() for c, _ in pool.table_columns(tname)}
        cols: list[Column] = []
        for c in meta["cols"]:
            if c["name"].lower() not in live_cols:
                continue
            samples = (_sample_values(pool, tname, c["name"], c["type"])
                       if with_samples else [])
            cols.append(Column(c["name"], c["type"], c["nullable"],
                               c["definition"], samples))
        # Include any live columns the dictionary missed (keeps allow-list complete).
        described = {c.name.lower() for c in cols}
        for c, ctype in pool.table_columns(tname):
            if c.lower() not in described:
                cols.append(Column(c, ctype, True, "", []))
        tables[tname] = Table(tname, meta["grain"], cols)

    # Any live table with no dictionary entry (e.g. monthly_kpis) still belongs.
    for tname in live_tables:
        if tname not in {t.lower() for t in tables}:
            cols = [Column(c, ctype, True, "", []) for c, ctype in pool.table_columns(tname)]
            tables[tname] = Table(tname, f"One row per {tname} record.", cols)

    return Catalog(tables=tables, glossary=glossary)


@lru_cache(maxsize=4)
def cached_catalog(url: str) -> Catalog:
    return build_catalog(TargetPool(url=url))


def get_catalog() -> Catalog:
    return cached_catalog(settings.demo_target_url)
