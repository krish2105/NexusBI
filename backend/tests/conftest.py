import csv
from pathlib import Path

import pytest

from app.config import settings
from app.db.introspect import build_allow_list
from app.db.seed_demo import seed_sqlite

BACKEND = Path(__file__).resolve().parent.parent
SAFETY_CSV = settings.data_dir / "evals" / "sql_safety_eval_cases.csv"
T2SQL_CSV = settings.data_dir / "evals" / "text2sql_eval.csv"


@pytest.fixture(scope="session", autouse=True)
def _demo_db():
    # Ensure the SQLite demo exists for the whole test session.
    seed_sqlite()
    yield


@pytest.fixture(scope="session")
def allow_list():
    return build_allow_list()


@pytest.fixture(scope="session")
def safety_cases():
    with open(SAFETY_CSV, newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def t2sql_cases():
    with open(T2SQL_CSV, newline="") as f:
        return list(csv.DictReader(f))
