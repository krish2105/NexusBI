"""Headline artifact: 100% of the adversarial red-team set is blocked.

The fixture is the same adversarial case set used by Nexus BI (from which this
package was extracted). Each NL question is screened against a representative
allow-list; the one legitimate control question must be allowed.
"""
import csv
from pathlib import Path

from sqlguard import screen_question

CASES = Path(__file__).parent / "fixtures" / "sql_safety_eval_cases.csv"

# A representative schema so unknown-table / unknown-column probes are detected.
ALLOW = {
    "orders": {"order_id", "customer_id", "amount", "status", "created_at"},
    "customers": {"id", "name", "email", "region"},
    "products": {"product_id", "name", "price"},
}


def _load():
    with open(CASES, newline="") as f:
        return list(csv.DictReader(f))


def test_100_percent_adversarial_blocked():
    cases = _load()
    misses = []
    for c in cases:
        got = screen_question(c["user_question"], ALLOW).verdict
        if got != c["expected_decision"]:
            misses.append((c["case_id"], c["attack_class"],
                           c["expected_decision"], got))
    assert not misses, f"mismatches: {misses}"

    adversarial = [c for c in cases if c["expected_decision"] == "BLOCK"]
    blocked = sum(1 for c in adversarial
                  if screen_question(c["user_question"], ALLOW).blocked)
    assert blocked == len(adversarial) and len(adversarial) >= 25


def test_control_question_allowed():
    control = [c for c in _load() if c["expected_decision"] == "ALLOW"]
    assert control, "expected at least one control case"
    for c in control:
        assert not screen_question(c["user_question"], ALLOW).blocked
