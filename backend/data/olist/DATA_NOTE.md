# Data package note

This directory is the Nexus BI–adapted **Olist Brazilian E-Commerce** package
(CC BY-NC-SA 4.0 — see `LICENSE_DATA.md`). It is committed so the project is
clone-and-run: `python -m app.db.seed_demo` loads it straight into SQLite.

## Two files are intentionally excluded from git (size)

The SQLite demo does **not** load either of these, so they are omitted to keep
the repo lean. Download the full package from Kaggle if you need them:

| File | Size | Why excluded |
|---|---:|---|
| `supplementary/geolocation.csv` | ~80 MB | 1,000,163 raw observations; the demo uses `derived/geolocation_zip_summary.csv` instead. |
| `model_ready/order_items_flat.csv` | ~50 MB | Denormalized convenience view; the normalized `core/order_items.csv` is loaded instead. |

Full source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
For the production Postgres path, load everything via `load_postgres.sql`.
