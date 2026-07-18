"""Self-contained Spider-format benchmark fixture.

The real Spider / BIRD dev sets are large external downloads (Google Drive,
~100 MB+). To keep this repo text-only and the benchmark runnable in CI with no
network, this module *builds a genuine Spider-format dataset on disk* from inline
schema + data:

    <root>/
      dev.json                       # [{db_id, question, query, db_difficulty}]
      database/<db_id>/<db_id>.sqlite

The exact same loader (`spider_bench.load_examples`) then runs it — so the
fixture exercises the real end-to-end path, just on a small curated slice of
real SQLite databases instead of the full dev set. Point the benchmark at a
downloaded Spider/BIRD directory to run the whole thing (see docs/SPIDER_BIRD.md).

The question mix is deliberately honest: single-table aggregations the zero-key
deterministic generator can answer, plus join/filter questions it cannot — so
the reported execution accuracy reflects the real ceiling of each generator mode
rather than a curated best case.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# (db_id, schema+seed SQL). Standard SQLite; every gold query below runs on it.
_DATABASES: dict[str, str] = {
    "music_festival": """
        CREATE TABLE stadium (
            stadium_id INTEGER PRIMARY KEY, name TEXT, city TEXT, capacity INTEGER);
        INSERT INTO stadium VALUES
            (1,'Riverside','Lyon',42000),(2,'Highfield','Lyon',58000),
            (3,'Bay Arena','Nice',31000),(4,'North Park','Paris',67000);

        CREATE TABLE singer (
            singer_id INTEGER PRIMARY KEY, name TEXT, country TEXT, age INTEGER);
        INSERT INTO singer VALUES
            (1,'Ava Stone','France',52),(2,'Ben Cole','France',41),
            (3,'Cira Nova','United States',33),(4,'Dane Ito','United States',29),
            (5,'Emi Ruiz','Spain',46);

        CREATE TABLE concert (
            concert_id INTEGER PRIMARY KEY, concert_name TEXT, stadium_id INTEGER,
            year INTEGER, ticket_price REAL);
        -- Row counts are kept distinct across tables (stadium=4, singer=5,
        -- concert=6) so a wrong query can't coincidentally match a COUNT(*) gold.
        INSERT INTO concert VALUES
            (1,'Auto Fest',1,2014,80.0),(2,'Homecoming',2,2014,120.0),
            (3,'Levels',3,2015,60.0),(4,'Night Waves',2,2015,95.0),
            (5,'Sunset',1,2015,75.0),(6,'Encore',3,2016,50.0);

        CREATE TABLE singer_in_concert (concert_id INTEGER, singer_id INTEGER);
        INSERT INTO singer_in_concert VALUES
            (1,1),(1,2),(2,3),(2,1),(3,4),(4,5),(4,2),(5,1);
    """,
    "store_sales": """
        CREATE TABLE customer (
            customer_id INTEGER PRIMARY KEY, name TEXT, city TEXT, segment TEXT);
        INSERT INTO customer VALUES
            (1,'Acme','Berlin','Enterprise'),(2,'Bloom','Berlin','SMB'),
            (3,'Crest','Munich','Enterprise'),(4,'Delta','Munich','SMB'),
            (5,'Echo','Hamburg','SMB');

        CREATE TABLE product (
            product_id INTEGER PRIMARY KEY, product_name TEXT, category TEXT,
            unit_price REAL);
        INSERT INTO product VALUES
            (1,'Widget','Hardware',25.0),(2,'Gadget','Hardware',40.0),
            (3,'License','Software',300.0),(4,'Support','Services',150.0);

        CREATE TABLE sales_order (
            order_id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER,
            quantity INTEGER, amount REAL, order_date TEXT);
        INSERT INTO sales_order VALUES
            (1,1,3,2,600.0,'2023-01-15'),(2,2,1,10,250.0,'2023-01-20'),
            (3,3,3,1,300.0,'2023-02-05'),(4,1,4,3,450.0,'2023-02-11'),
            (5,4,2,5,200.0,'2023-03-02'),(6,5,1,4,100.0,'2023-03-19'),
            (7,3,4,2,300.0,'2023-03-22'),(8,2,2,6,240.0,'2023-04-01');
    """,
}

# Spider-format examples. `query` is the gold SQL (executed as reference truth).
# `db_difficulty` follows Spider's easy / medium / hard labeling convention.
_EXAMPLES: list[dict] = [
    # --- music_festival ---
    {"db_id": "music_festival", "db_difficulty": "easy",
     "question": "How many singers are there?",
     "query": "SELECT COUNT(*) FROM singer"},
    {"db_id": "music_festival", "db_difficulty": "easy",
     "question": "What is the average age of the singers?",
     "query": "SELECT AVG(age) FROM singer"},
    {"db_id": "music_festival", "db_difficulty": "easy",
     "question": "How many singers are there from each country?",
     "query": "SELECT country, COUNT(*) FROM singer GROUP BY country"},
    {"db_id": "music_festival", "db_difficulty": "easy",
     "question": "What is the total capacity of all stadiums?",
     "query": "SELECT SUM(capacity) FROM stadium"},
    {"db_id": "music_festival", "db_difficulty": "medium",
     "question": "What is the maximum ticket price among all concerts?",
     "query": "SELECT MAX(ticket_price) FROM concert"},
    {"db_id": "music_festival", "db_difficulty": "medium",
     "question": "How many stadiums are in each city?",
     "query": "SELECT city, COUNT(*) FROM stadium GROUP BY city"},
    {"db_id": "music_festival", "db_difficulty": "hard",
     "question": "What are the names of stadiums that have hosted more than one concert?",
     "query": ("SELECT T2.name FROM concert AS T1 JOIN stadium AS T2 "
               "ON T1.stadium_id = T2.stadium_id GROUP BY T1.stadium_id "
               "HAVING COUNT(*) > 1")},
    {"db_id": "music_festival", "db_difficulty": "hard",
     "question": "For each singer, how many concerts have they performed in?",
     "query": ("SELECT T2.name, COUNT(*) FROM singer_in_concert AS T1 "
               "JOIN singer AS T2 ON T1.singer_id = T2.singer_id "
               "GROUP BY T1.singer_id")},
    # --- store_sales ---
    {"db_id": "store_sales", "db_difficulty": "easy",
     "question": "How many customers are there?",
     "query": "SELECT COUNT(*) FROM customer"},
    {"db_id": "store_sales", "db_difficulty": "easy",
     "question": "What is the total amount across all orders?",
     "query": "SELECT SUM(amount) FROM sales_order"},
    {"db_id": "store_sales", "db_difficulty": "medium",
     "question": "How many customers are in each segment?",
     "query": "SELECT segment, COUNT(*) FROM customer GROUP BY segment"},
    {"db_id": "store_sales", "db_difficulty": "medium",
     "question": "What is the average unit price for each product category?",
     "query": "SELECT category, AVG(unit_price) FROM product GROUP BY category"},
    {"db_id": "store_sales", "db_difficulty": "hard",
     "question": "What is the total order amount for each customer city?",
     "query": ("SELECT T2.city, SUM(T1.amount) FROM sales_order AS T1 "
               "JOIN customer AS T2 ON T1.customer_id = T2.customer_id "
               "GROUP BY T2.city")},
    {"db_id": "store_sales", "db_difficulty": "hard",
     "question": "What is the total revenue for each product category?",
     "query": ("SELECT T2.category, SUM(T1.amount) FROM sales_order AS T1 "
               "JOIN product AS T2 ON T1.product_id = T2.product_id "
               "GROUP BY T2.category")},
]


def build_fixture(root: Path) -> Path:
    """Materialize the Spider-format dataset under ``root`` (idempotent).

    Writes ``root/dev.json`` and ``root/database/<db_id>/<db_id>.sqlite``.
    Returns ``root``.
    """
    root = Path(root)
    db_dir = root / "database"
    db_dir.mkdir(parents=True, exist_ok=True)

    for db_id, ddl in _DATABASES.items():
        target = db_dir / db_id / f"{db_id}.sqlite"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Rebuild deterministically so a stale/partial file never lingers.
        if target.exists():
            target.unlink()
        con = sqlite3.connect(target)
        try:
            con.executescript(ddl)
            con.commit()
        finally:
            con.close()

    (root / "dev.json").write_text(json.dumps(_EXAMPLES, indent=2))
    return root


if __name__ == "__main__":  # pragma: no cover - manual build
    import sys

    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("var/spider_fixture")
    build_fixture(dest)
    print(f"Fixture written to {dest} "
          f"({len(_DATABASES)} databases, {len(_EXAMPLES)} questions).")
