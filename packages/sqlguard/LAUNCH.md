# sqlguard — launch copy

Ready-to-post copy for when `sqlguard` goes live on PyPI (see [PUBLISHING.md](./PUBLISHING.md)).
Written to be honest, not hypey — the strongest version of this launch *volunteers*
the limitation (a read-only role covers most of it) and wins on the parts a role
doesn't: pre-execution rejection, hallucinated-schema catching, dialect portability,
and a frozen, tested rule set.

**Pre-flight before posting:** publish to PyPI, confirm `pip install sqlguard` works in
a clean venv, and check the CI badge is green on the standalone repo.

---

## Hacker News (Show HN)

**Title:**
`Show HN: sqlguard – make LLM-generated SQL provably read-only before you run it`

**Body:**
```
I build text-to-SQL and kept coming back to the same problem: the scary failure
isn't a wrong answer, it's a destructive one. DROP TABLE, a DELETE smuggled through
a CTE, pg_read_file('/etc/passwd'), or a query reading a table it should never see.

sqlguard is the gate you put between an LLM and your database. It parses the SQL to
a sqlglot AST and checks: single read-only statement, no write node anywhere in the
tree (including data-modifying CTEs), no dangerous functions or system catalogs,
optional schema allow-list (which also catches hallucinated columns), and an enforced
LIMIT. It's deterministic — no model, no network — and every rejection cites the rule
that fired, which is handy for a repair loop.

    from sqlguard import SqlGuard
    guard = SqlGuard({"orders": {"id", "amount"}}, target_dialect="postgres")
    guard.check("SELECT amount FROM orders").allowed   # True
    guard.check("DROP TABLE orders").allowed           # False

Honest limitation up front: a read replica + a read-only GRANT gives you most of this
for free, and you should absolutely still use one (it's the Layer 0 backstop). What
sqlguard adds is rejecting *before* execution (clean error + repair loop instead of a
runtime failure), catching hallucinated schema, enforcing row limits, and transpiling
the *validated* query to your dialect so the same DROP is blocked identically on
Postgres/MySQL/SQLite/BigQuery. Roles and sqlguard are complementary, not either/or.

Only dependency is sqlglot. It blocks 100% of a 29-case adversarial red-team set (run
in CI on 3.10–3.13), and a cross-dialect golden regression suite snapshots the verdict
AND the transpiled SQL so a sqlglot upgrade can't silently change what it accepts.

Extracted from a text-to-SQL analyst I built (Nexus BI), which now depends on the
published package rather than a copy — so the rules you pip install are the ones
actually guarding the app.

    pip install sqlguard

Repo: https://github.com/krish2105/sqlguard
Would love feedback on the rule set — especially evasions I haven't covered.
```

**Comment-reply drafts** (have these ready; HN will ask):

- *"Why not just a read-only role?"* → "You should, and sqlguard sits in front of one
  (defense in depth). A role gives you a runtime error after a bad query is sent;
  sqlguard rejects before execution, tells you which rule failed (great for a repair
  loop), catches hallucinated schema, and enforces row limits + dialect portability —
  none of which a role does. It's complementary, not a replacement. I say this in the
  README because it's the honest framing."
- *"sqlglot can't parse everything."* → "Right, and the guard fails closed — a parse
  error is a BLOCK, not an allow. So the failure mode is 'rejects a valid query,' not
  'runs a dangerous one.' The regression suite pins that behavior per dialect."
- *"What about `SELECT` that reads sensitive data?"* → "That's the allow-list layer —
  pass the tables/columns the connection is allowed to touch and anything else
  (including hallucinated names) is rejected. Skip it and you still get read-only +
  no-dangerous-functions + LIMIT."

---

## dev.to / blog post

**Title:** `The scariest bug in text-to-SQL isn't a wrong answer`

**Tags:** `python`, `llm`, `sql`, `ai`

```markdown
Everyone building text-to-SQL benchmarks accuracy. That's the wrong first problem.

If you hand a language model a database connection, the failure that ends the
conversation isn't a mis-joined GROUP BY. It's `DROP TABLE`. It's a `DELETE` hidden
inside a CTE. It's `pg_read_file('/etc/passwd')` reading the host filesystem. A wrong
number is embarrassing; a destructive query is a resume-generating event.

So before I optimized accuracy, I made destructive queries **impossible by
construction**. That guard is now a standalone package: `sqlguard`.

## The idea: validate the AST, not the string

Regex-on-SQL is a losing game — `dRoP tAbLe`, comment-smuggling, `;`-chaining, a write
buried three CTEs deep. So sqlguard parses to a [sqlglot](https://github.com/tobymao/sqlglot)
AST and reasons over the tree. Case-obfuscation is normalized by the parser before any
rule runs; a write is a write node no matter how deep you bury it.

A query is accepted only if **all** of these hold:

1. Single read-only statement (blocks chaining + comment-smuggling)
2. No write node anywhere in the AST (INSERT/UPDATE/DELETE/DROP/…, `SELECT … INTO`, data-modifying CTEs)
3. No dangerous functions or system catalogs (`pg_read_file`, `pg_catalog`, `information_schema`, …)
4. Optional schema allow-list — every table/column must exist, which also catches **hallucinated** identifiers
5. An enforced `LIMIT` (injected if absent, clamped if too large)

Then it transpiles the *validated* query to your dialect, so the same `DROP` is blocked
identically on Postgres, MySQL, SQLite, and BigQuery.

    from sqlguard import SqlGuard

    guard = SqlGuard({"orders": {"id", "amount"}}, target_dialect="postgres")
    guard.check("SELECT amount FROM orders").allowed   # True
    guard.check("DROP TABLE orders").allowed           # False
    guard.ensure("SELECT amount FROM orders")          # -> safe SQL, or raises

## The honest part

A read replica plus a read-only `GRANT` gives you most of this guarantee for free, and
you should use one — it's the ultimate backstop, and sqlguard is designed to sit in
front of it. What sqlguard adds over a role:

- It rejects **before** execution — a clean error and a repair loop, not a runtime failure.
- It catches **hallucinated schema** — the LLM inventing a `users.ssn` column.
- It enforces **row limits** and **dialect portability**.
- Every rejection **cites the rule that fired**, which you can feed back to the model.

Roles and sqlguard are complementary. I put that in the README because overselling a
safety tool is how people get burned.

## Making sure it can't rot

sqlguard parses with sqlglot, so a parser upgrade could silently change what it
accepts. To prevent that, a cross-dialect **golden regression suite** snapshots the
verdict *and* the transpiled SQL for a fixed corpus across all four dialects; CI fails
on any drift. It also blocks 100% of a 29-case adversarial red-team set, verified on
Python 3.10–3.13 on every push.

## Try it

    pip install sqlguard
    sqlguard check "SELECT amount FROM orders"      # exit 0
    sqlguard check "DROP TABLE users"               # exit 1, cites the rule

Repo: https://github.com/krish2105/sqlguard · MIT licensed · only dependency is sqlglot.

It came out of [Nexus BI](https://github.com/krish2105/NexusBI), a read-only text-to-SQL
analyst — which now depends on the published package, so the rules you install are the
ones actually guarding the app. Feedback on the rule set very welcome, especially
evasions I haven't thought of.
```

---

## X / Twitter thread

```
1/ The scariest bug in text-to-SQL isn't a wrong answer. It's a destructive one:
DROP TABLE, a DELETE hidden in a CTE, pg_read_file('/etc/passwd').

So I built sqlguard: make destructive LLM-generated SQL impossible *before* you run it.
pip install sqlguard 🧵

2/ It parses SQL to an AST (via sqlglot) and reasons over the tree — not regex on text.
So dRoP tAbLe, ;-chaining, and a write buried 3 CTEs deep all get caught. Case tricks
are normalized by the parser before any rule runs.

3/ A query passes only if ALL hold:
• single read-only statement
• no write node anywhere
• no dangerous funcs / system catalogs
• (optional) schema allow-list — also catches hallucinated columns
• enforced LIMIT

    guard.check("DROP TABLE orders").allowed  # False

4/ Honest bit: a read-only DB role covers most of this for free, and you should use one.
sqlguard adds what a role can't: rejects *before* execution (clean error + repair loop),
catches hallucinated schema, enforces row limits, and blocks the same query identically
across Postgres/MySQL/SQLite/BigQuery.

5/ It can't rot silently: a cross-dialect golden regression suite snapshots the verdict
AND the transpiled SQL, so a sqlglot bump can't quietly change what it accepts. 100% of a
29-case red-team set blocked, in CI on 3.10–3.13.

6/ Only dependency is sqlglot. MIT. Ships a CLI (sqlguard check "…", exit 0/1 for
pipelines). Extracted from a text-to-SQL analyst that now depends on the published
package — same rules in the app and in your pip install.

github.com/krish2105/sqlguard
```

---

## Reddit (r/Python, r/dataengineering)

**Title:** `sqlguard: make LLM-generated SQL provably read-only before you execute it (MIT, sqlglot-only)`

```
Built this out of frustration with text-to-SQL demos that optimize accuracy while
ignoring the failure that actually matters: a destructive query. DROP TABLE, a DELETE
in a CTE, pg_read_file() reading the host.

sqlguard parses SQL to a sqlglot AST and only accepts a single read-only statement with
no write node anywhere, no dangerous functions/system catalogs, an optional schema
allow-list (catches hallucinated columns too), and an enforced LIMIT — then transpiles
the validated query to your dialect. Deterministic, no LLM, every rejection names the
rule that fired.

Honest framing: a read-only role covers most of this and you should use one. sqlguard
adds pre-execution rejection (+ repair-loop-friendly errors), hallucinated-schema
catching, row limits, and dialect portability. Complementary, not a replacement.

Only dep is sqlglot; MIT; CLI included; 100% of a 29-case adversarial set blocked in CI
on 3.10–3.13; cross-dialect golden regression suite so a sqlglot upgrade can't silently
change behavior.

    pip install sqlguard

https://github.com/krish2105/sqlguard — feedback on the rule set welcome, especially
evasions I've missed.
```
