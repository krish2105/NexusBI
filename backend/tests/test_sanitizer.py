"""Layer 4 tests — NL screen, including the headline 100%-blocked safety eval."""
import pytest

from app.sqlsafety import screen_question

LEGIT_QUESTIONS = [
    "What were the top 5 products by revenue last quarter?",
    "Show monthly merchandise revenue over time.",
    "Which customer states have the most orders?",
    "What is the average review score by category?",
    "How does freight value trend month over month?",
]


@pytest.mark.parametrize("q", LEGIT_QUESTIONS)
def test_legitimate_questions_pass(q, allow_list):
    assert screen_question(q, allow_list).verdict == "ALLOW", q


def test_safety_eval_100_percent_blocked(safety_cases, allow_list):
    """The headline interview artifact: 100% of adversarial questions blocked,
    the control question allowed."""
    misses = []
    for c in safety_cases:
        got = screen_question(c["user_question"], allow_list).verdict
        if got != c["expected_decision"]:
            misses.append((c["case_id"], c["expected_decision"], got))
    assert not misses, f"safety eval mismatches: {misses}"

    n_block = sum(1 for c in safety_cases if c["expected_decision"] == "BLOCK")
    blocked = sum(
        1 for c in safety_cases
        if c["expected_decision"] == "BLOCK"
        and screen_question(c["user_question"], allow_list).verdict == "BLOCK")
    assert blocked == n_block and n_block >= 29
