"""Seed the demo target database from the REAL Olist CSV package.

Two paths, one command:
  * SQLite (default)  -> instant, zero-infra demo for local dev & free-tier hosting.
  * PostgreSQL        -> production path; we defer to the package's own
                         ``load_postgres.sql`` + ``read_only_role.sql``.

Run:  python -m app.db.seed_demo
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from app.config import settings

# Tables loaded into the instant SQLite demo. These are the analytical tables
# the README recommends for text-to-SQL, PLUS the two derived/model-ready tables
# the eval set queries by name (monthly_kpis, customer_features). The full 1M-row
# geolocation observation file is intentionally left to the Postgres path.
TABLE_FILES: dict[str, str] = {
    "regions": "core/regions.csv",
    "dates": "core/dates.csv",
    "categories": "core/categories.csv",
    "products": "core/products.csv",
    "customers": "core/customers.csv",
    "sellers": "core/sellers.csv",
    "orders": "core/orders.csv",
    "order_items": "core/order_items.csv",
    "payments": "supplementary/payments.csv",
    "reviews": "supplementary/reviews.csv",
    "geolocation_zip_summary": "derived/geolocation_zip_summary.csv",
    "monthly_kpis": "derived/monthly_kpis.csv",
    "customer_features": "model_ready/customer_features.csv",
}


def _sqlite_path(url: str) -> Path:
    assert url.startswith("sqlite:///"), f"expected sqlite url, got {url}"
    return Path(url.replace("sqlite:///", "", 1))


def seed_sqlite(url: str | None = None, data_dir: Path | None = None,
                force: bool = False) -> Path:
    """Load the CSV package into a single SQLite file. Idempotent."""
    url = url or settings.demo_target_url
    data_dir = data_dir or settings.data_dir
    db_path = _sqlite_path(url)

    if db_path.exists() and not force:
        con = sqlite3.connect(db_path)
        have = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        con.close()
        if set(TABLE_FILES).issubset(have):
            print(f"[seed] demo DB already present at {db_path} "
                  f"({len(have)} tables) — skipping (use force=True to rebuild)")
            return db_path

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        for table, rel in TABLE_FILES.items():
            csv_path = data_dir / rel
            if not csv_path.exists():
                print(f"[seed] WARN missing {csv_path}; skipping {table}")
                continue
            # Read everything as-is; pandas infers numeric/flag columns correctly.
            df = pd.read_csv(csv_path, low_memory=False)
            df.to_sql(table, con, if_exists="replace", index=False)
            print(f"[seed] {table:<24} {len(df):>7,} rows  <- {rel}")
        _create_indexes(con)
        con.commit()
    finally:
        con.close()
    print(f"[seed] done -> {db_path}")
    return db_path


def _create_indexes(con: sqlite3.Connection) -> None:
    idx = [
        "CREATE INDEX IF NOT EXISTS ix_orders_purchase ON orders(order_purchase_timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_orders_uid ON orders(customer_unique_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_region ON orders(region_id)",
        "CREATE INDEX IF NOT EXISTS ix_items_order ON order_items(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_items_product ON order_items(product_id)",
        "CREATE INDEX IF NOT EXISTS ix_items_seller ON order_items(seller_id)",
        "CREATE INDEX IF NOT EXISTS ix_payments_order ON payments(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_reviews_order ON reviews(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_products_cat ON products(category_id)",
    ]
    for stmt in idx:
        try:
            con.execute(stmt)
        except sqlite3.OperationalError as e:  # table absent in a partial load
            print(f"[seed] index skipped: {e}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="rebuild even if present")
    args = ap.parse_args()
    seed_sqlite(force=args.force)
