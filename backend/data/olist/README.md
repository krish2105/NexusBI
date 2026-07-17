# Nexus BI — Olist Real-World E-commerce Data Package

Build timestamp: **2026-07-17T15:38:18+00:00**

## What this is

A reproducible, loss-aware CSV package prepared for the Nexus BI autonomous business-analyst copilot. It converts the anonymized real commercial Olist e-commerce release into the project’s required retail schema (`customers`, `orders`, `order_items`, `products`, `categories`, `regions`, `dates`) and adds the complete official geolocation release, source-preserving payment/review/seller files, model-ready views, glossary assets, and evaluation files.

The official source describes approximately 100,000 Brazilian marketplace orders from 2016–2018 with order, item, payment, freight, customer, product, seller, geography, and review information. Olist states that the data is real commercial data and anonymized.

Official dataset: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

## Non-hallucination / missing-data policy

- **No source record was silently removed** from any of the nine official source CSVs, including all 1,000,163 geolocation observations.
- **No statistical value was imputed.** Genuine source nulls stay null and are listed column-by-column in `missingness_report.csv`.
- Missing source categories are mapped to the explicit key `__unknown__`, with `source_category_missing_flag=1`.
- The two category labels lacking a source English translation retain their Portuguese source labels and are marked `portuguese_source_fallback`; no translation was guessed.
- Operational anomalies are preserved and flagged. They are not rewritten to make the data look cleaner.
- Review text is only Unicode/whitespace normalized; words are not translated, classified, or rewritten.

## Data coverage

- Source purchase range: **2016-09-04 through 2018-10-17**.
- Complete date dimension across every source timestamp: **2016-09-04 through 2020-04-09**.
- 99,441 orders, 112,650 order items, 103,886 payment rows, 99,224 review rows, 32,951 products, 3,095 sellers, 99,441 order-scoped customer records, 96,096 stable shopper IDs, and 1,000,163 source geolocation observations.
- `customer_id` is the source order-scoped customer key. Use `customer_unique_id` for repeat-customer analysis.

## Files

| File | Rows | Bytes |
|---|---:|---:|
| `core/regions.csv` | 27 | 1,383 |
| `supplementary/geolocation.csv` | 1,000,163 | 84,166,741 |
| `derived/geolocation_zip_summary.csv` | 19,023 | 1,580,479 |
| `core/dates.csv` | 1,314 | 126,709 |
| `core/categories.csv` | 74 | 6,727 |
| `core/products.csv` | 32,951 | 4,984,283 |
| `core/customers.csv` | 99,441 | 13,657,930 |
| `core/sellers.csv` | 3,095 | 364,217 |
| `core/orders.csv` | 99,441 | 33,543,138 |
| `core/order_items.csv` | 112,650 | 17,691,645 |
| `supplementary/payments.csv` | 103,886 | 5,647,780 |
| `supplementary/reviews.csv` | 99,224 | 17,516,992 |
| `derived/monthly_kpis.csv` | 25 | 3,044 |
| `model_ready/customer_features.csv` | 96,096 | 18,618,923 |
| `model_ready/order_items_flat.csv` | 112,650 | 52,471,552 |

Supporting files:

- `data_dictionary.csv` — every exported column, type, nullability, grain, and definition.
- `missingness_report.csv` — exact missing count and percentage for every output column.
- `data_quality_report.csv` — structural checks, source warnings, and reconciliation results.
- `source_manifest.csv` — source files, hashes, row counts, columns, official URL, and license.
- `schema_relationships.csv` — join keys and cardinalities.
- `transformation_log.csv` — every material cleaning/feature-engineering rule and null policy.
- `business_glossary.csv` — grounded metric definitions for Nexus RAG/text-to-SQL.
- `evals/text2sql_eval.csv` — 40 executable, result-hashed business questions and SQL queries.
- `evals/sql_safety_eval_cases.csv` — adversarial and control prompts with expected policy outcomes; run these through the project validator before claiming a measured block rate.
- `load_postgres.sql` — PostgreSQL schema and `\copy` loader.
- `read_only_role.sql` — least-privilege role pattern aligned with the Nexus SQL safety design.
- `checksums.sha256` — SHA-256 integrity hashes for package files.

## Important real-world warnings

| Area | Finding | Count | Handling |
|---|---|---:|---|
| products | Products with missing source category metadata. | 610 | Retained as __unknown__; no category was invented. |
| products | Products with incomplete physical dimensions. | 2 | Physical values remain null. |
| orders | Orders missing source approval timestamp. | 160 | Expected in real operational data; preserved. |
| orders | Orders missing carrier-handoff timestamp. | 1783 | Preserved and flagged. |
| orders | Orders missing actual customer-delivery timestamp. | 2965 | Preserved and flagged. |
| orders | Orders without an item row. | 775 | Mostly non-completed lifecycle records; no order was dropped. |
| orders | Orders without a payment row. | 1 | Payment value stays null. |
| orders | Orders without a review row. | 768 | Review measures stay null. |
| orders | Orders with chronology anomaly flag. | 189 | 166 carrier-before-purchase and 23 delivery-before-carrier cases; preserved for audit. |
| reviews | Distinct duplicated source review IDs. | 789 | No exact duplicate review rows were found; surrogate review_row_id preserves each row. |
| reviews | Orders with multiple review rows. | 547 | Order aggregates expose review_count and average/latest score. |
| orders | Orders with item and payment totals differing by more than 0.02. | 280 | Real source discrepancy; difference is exposed per order. |
| categories | Source categories without an English translation. | 2 | Portuguese source labels are retained rather than guessed. |
| order_items | Shipping-limit timestamps in calendar year 2020. | 4 | The purchase data ends in 2018; four source shipping deadlines extend to 2020 and are preserved. |
| reviews | Review response lags longer than 365 days. | 10 | Long source lags are preserved for investigation. |
| geolocation | Extra rows beyond one copy in exact duplicate source geolocation groups. | 261831 | All duplicate source observations are retained; use the postal-prefix/state summary for non-duplicating joins. |
| geolocation | Coordinate observations outside the documented coarse Brazil screening envelope. | 29 | Rows are preserved and flagged; summary fields provide both all-observation and in-envelope means. |
| geolocation_zip_summary | Postal-prefix/state pairs with no coordinate inside the coarse screening envelope. | 4 | All-observation means remain available; in-envelope means stay null rather than being invented. |
| geolocation | Postal prefixes observed in more than one state. | 8 | Join geolocation on both postal prefix and state, not postal prefix alone. |
| orders | Orders with both item and payment records reconcile within 0.02. | 98385 | Non-reconciled orders remain identifiable; no balancing adjustment was applied. |

The 280 order/payment mismatches are not balanced or overwritten. The order-level fields `payment_reconciliation_difference` and `payment_reconciled_flag` expose them directly.

## Recommended Nexus BI tables

Use the normalized analytical tables for text-to-SQL: `regions`, `dates`, `categories`, `products`, `customers`, `sellers`, `orders`, `order_items`, `payments`, `reviews`, and `geolocation_zip_summary`. Keep full `geolocation` available for audit and advanced spatial work.

For customer/seller geography, join `derived/geolocation_zip_summary.csv` on both postal prefix and state; joining the full observation file directly would multiply rows. Use `derived/monthly_kpis.csv` for forecasting demonstrations. Use `model_ready/customer_features.csv` for clustering/RFM experiments. Use `model_ready/order_items_flat.csv` for notebooks or BI tools that prefer one wide file.

### Flat-file warning

`model_ready/order_items_flat.csv` is at **order-item grain**. Columns beginning with `order_` are repeated for every item in the same order. For revenue totals, sum `line_merchandise_value` or `line_total_value`; do not sum repeated order-level values unless orders are deduplicated first.

## Load into PostgreSQL

```bash
createdb nexus_demo
psql "$DATABASE_URL" -f load_postgres.sql
psql "$DATABASE_URL" -f read_only_role.sql
```

Run `load_postgres.sql` from this package’s root so its relative CSV paths resolve.

## License and attribution

Source data: **Brazilian E-Commerce Public Dataset by Olist**, published by Olist on Kaggle, licensed **CC BY-NC-SA 4.0**. This cleaned/adapted package is distributed under the same terms. Attribution, noncommercial use, and ShareAlike conditions apply. See `LICENSE_DATA.md` and https://creativecommons.org/licenses/by-nc-sa/4.0/.

This package is a derivative transformation and is not endorsed by Olist, Kaggle, or IBGE.
