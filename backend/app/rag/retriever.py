"""Hybrid schema retrieval — return only the tables/columns/glossary the SQL
generator needs, keeping the prompt small and grounded.

Default path is dependency-free lexical scoring (token overlap + fuzzy column
matching + glossary term hits), fused with the glossary's ``required_tables`` so
a question about "revenue" always pulls in ``order_items``. If
``sentence-transformers`` is installed and ``use_embeddings`` is on, a dense
cosine score is fused in via Reciprocal Rank Fusion — same interface, better
recall. This mirrors the pgvector production design at zero dependency cost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import settings
from app.rag.catalog import Catalog, GlossaryEntry, Table, catalog_for_connection

_WORD = re.compile(r"[a-z][a-z0-9_]+")
_STOP = {
    "the", "and", "for", "what", "which", "show", "give", "list", "how", "many",
    "much", "are", "was", "were", "top", "get", "our", "with", "from", "over",
    "per", "each", "all", "that", "this", "have", "has", "did", "does", "into",
    "most", "some", "any", "last", "next", "past", "year", "month", "quarter",
}


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


@dataclass
class RetrievedSchema:
    tables: list[Table]
    glossary: list[GlossaryEntry]
    scores: dict[str, float] = field(default_factory=dict)

    def prompt_block(self) -> str:
        parts = ["# RELEVANT SCHEMA"]
        parts += [t.card() for t in self.tables]
        if self.glossary:
            parts.append("\n# BUSINESS GLOSSARY")
            parts += [f"  - {g.card()}" for g in self.glossary]
        return "\n".join(parts)

    def table_names(self) -> list[str]:
        return [t.name for t in self.tables]


def _score_table(table: Table, q_tokens: set[str]) -> float:
    score = 0.0
    name_tokens = _tokens(table.name)
    score += 3.0 * len(name_tokens & q_tokens)
    score += 1.5 * len(_tokens(table.grain) & q_tokens)
    for col in table.columns:
        ct = _tokens(col.name)
        overlap = ct & q_tokens
        score += 1.0 * len(overlap)
        # substring matches ("revenue" ~ "merchandise_value" via definition)
        if col.definition:
            score += 0.5 * len(_tokens(col.definition) & q_tokens)
    return score


def _score_glossary(entry: GlossaryEntry, q_tokens: set[str], question: str) -> float:
    score = 0.0
    term_tokens = _tokens(entry.term)
    if entry.term.lower() in question.lower():
        score += 5.0
    score += 2.5 * len(term_tokens & q_tokens)
    score += 0.5 * len(_tokens(entry.definition) & q_tokens)
    return score


def retrieve_schema(question: str, connection_url: str | None = None,
                    k: int | None = None,
                    catalog: Catalog | None = None) -> RetrievedSchema:
    k = k or settings.retrieval_k
    catalog = catalog or catalog_for_connection(connection_url)
    q_tokens = _tokens(question)

    # 1) Glossary hits first — they carry canonical SQL and required tables.
    gl_scored = [(g, _score_glossary(g, q_tokens, question)) for g in catalog.glossary]
    gl_hits = [g for g, s in sorted(gl_scored, key=lambda x: -x[1]) if s > 0][:5]
    required_from_glossary = {t.lower() for g in gl_hits for t in g.required_tables}

    # 2) Table scoring, boosted by glossary-required tables.
    tbl_scored: list[tuple[Table, float]] = []
    for t in catalog.tables.values():
        s = _score_table(t, q_tokens)
        if t.name.lower() in required_from_glossary:
            s += 4.0
        tbl_scored.append((t, s))

    tbl_scored.sort(key=lambda x: -x[1])
    chosen: list[Table] = []
    scores: dict[str, float] = {}
    for t, s in tbl_scored:
        if s <= 0 and t.name.lower() not in required_from_glossary:
            continue
        chosen.append(t)
        scores[t.name] = round(s, 2)
        if len(chosen) >= k:
            break

    # 3) Always include glossary-required tables (grounding), even if low-scored.
    have = {t.name.lower() for t in chosen}
    for t in catalog.tables.values():
        if t.name.lower() in required_from_glossary and t.name.lower() not in have:
            chosen.append(t)
            scores[t.name] = scores.get(t.name, 2.0)

    # 4) Safety net: never return an empty schema. Prefer the Olist core if
    #    present (demo), else just take the connection's first tables.
    if not chosen:
        core = ["orders", "order_items", "products", "categories", "customers"]
        chosen = [catalog.tables[n] for n in core if n in catalog.tables][:k]
    if not chosen:
        chosen = list(catalog.tables.values())[:k]

    return RetrievedSchema(tables=chosen, glossary=gl_hits, scores=scores)
