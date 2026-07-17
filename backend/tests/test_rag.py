"""RAG retrieval precision — does schema retrieval surface the right tables?"""
import pytest

from app.rag.retriever import retrieve_schema

CASES = [
    ("What were the top categories by merchandise revenue?",
     {"order_items", "categories"}),
    ("How many repeat customers do we have?", {"customers"}),
    ("Show monthly revenue over time.", {"order_items"}),
    ("Top customer states by number of orders.", {"orders"}),
]


@pytest.mark.parametrize("question,expected", CASES)
def test_retrieval_surfaces_expected_tables(question, expected):
    got = {t.lower() for t in retrieve_schema(question, k=6).table_names()}
    missing = expected - got
    assert not missing, f"missing tables {missing} for {question!r}; got {got}"


def test_glossary_grounds_revenue_terms():
    r = retrieve_schema("total merchandise revenue", k=4)
    terms = {g.term for g in r.glossary}
    assert "merchandise revenue" in terms
