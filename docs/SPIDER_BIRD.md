# Spider / BIRD text-to-SQL benchmark

Nexus is measured on the standard academic text-to-SQL benchmarks with
**execution accuracy (EX)** — the metric Spider and BIRD themselves report: a
prediction is correct when *its result set equals the gold query's result set*.

What makes this an honest, end-to-end benchmark and not a demo:

- Every question runs against **its own SQLite database** via `connection_url` —
  the exact per-connection path the product uses (catalog → allow-list →
  retriever → generator → **5-layer safety gate** → dialect transpile →
  read-only execution). Nothing about the Olist demo leaks in.
- The **gold SQL is executed** on the same database as reference truth.
- The matcher is recognized EX semantics: order-agnostic multiset equality,
  order-sensitive only when the gold has a top-level `ORDER BY`, column order
  ignored, and an *extra* descriptive column (which Nexus sometimes adds) is
  tolerated as long as every gold column is present with the correct values.
  Table cardinalities in the bundled fixture are kept distinct so a wrong query
  can't coincidentally match a `COUNT(*)` gold.

## Run it

```bash
cd backend

# Bundled self-contained fixture (no download; runs in ~1.5s):
python -m evals.spider_bench

# It's also part of the full eval summary:
python -m evals.run_evals            # adds a SPIDER/BIRD line
```

The bundled fixture (`evals/spider/fixture.py`) builds a genuine Spider-format
dataset on disk — `dev.json` + `database/<db_id>/<db_id>.sqlite` — from two real
SQLite databases (a music-festival schema and a store-sales schema, 14 questions
across easy/medium/hard). The full dev set uses the identical loader.

## Run the real dev sets

The harness auto-detects both formats:

| Dataset | Gold key | DB directory | Download |
|---|---|---|---|
| **Spider** | `query` | `database/<db_id>/<db_id>.sqlite` | https://yale-lily.github.io/spider |
| **BIRD**   | `SQL`   | `dev_databases/<db_id>/<db_id>.sqlite` | https://bird-bench.github.io |

Point the benchmark at an unzipped dataset directory (the one containing
`dev.json`):

```bash
# Spider dev set (1034 questions) — cap with --limit for a quick pass:
python -m evals.spider_bench --dir /path/to/spider --dataset spider --limit 200

# BIRD dev set:
python -m evals.spider_bench --dir /path/to/bird --dataset bird
```

Or drive it through the eval suite with environment variables:

```bash
SPIDER_DIR=/path/to/spider SPIDER_LIMIT=200 python -m evals.run_evals
BIRD_DIR=/path/to/bird                       python -m evals.run_evals
```

Each run writes `evals/spider_report.json`: overall EX, a per-difficulty
breakdown, counts of blocked / skipped / gold-error rows, and per-question
detail (predicted SQL, gold SQL, verdict).

## Reproducibility

**The benchmark is deterministic: the same fixture yields the same score and the
same generated SQL on every run, on any machine, under any `PYTHONHASHSEED`.**
This is enforced by a test (`tests/test_spider_bench.py`) that runs the benchmark
in subprocesses under several hash seeds and asserts the per-question SQL is
byte-identical.

That guarantee had to be earned. The catalog originally built its table map by
iterating a **set** of table names, so `catalog.tables` insertion order — and
with it every downstream tie-break (schema retrieval, base-table choice) —
varied between processes. The same fixture scored anywhere from 7/14 to 9/14 run
to run. Worse, it wasn't only a benchmark artifact: a user could ask the same
question twice, across a restart, and get different SQL. The fix sorts that
iteration and makes base-table selection tie-break explicitly, so scores are
comparable across runs and a benchmark number means something.

## Interpreting the number — generator mode matters

The report always records `generator_mode`. **Zero-key (deterministic)** is the
default: a grounded, single-table synthesizer that never hallucinates
identifiers (so it always passes the safety gate) but does not compose joins —
it answers aggregations and group-bys and scores 0 on join questions. That is
the honest ceiling of the free-tier path, and the benchmark shows it plainly
(the bundled fixture's hard/join questions are all misses).

Set a free **Groq** key (`GROQ_API_KEY`) or a local **Ollama** endpoint and the
LLM generation path takes over — it handles joins and richer SQL, and the *same*
benchmark measures the lift. Because grounding, validation, and safety are shared
across both paths, the LLM only ever changes *generation*, never safety.
