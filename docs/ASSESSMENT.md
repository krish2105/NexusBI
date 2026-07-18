# Nexus BI — C-Level Assessment & Master Plan

*A C-level panel (CEO · CTO · CFO · COO · Senior Frontend · Senior Backend) audited the
live repository — web-grounded on the competitive landscape and current free-tier
limits — then a board synthesis and an outside-operator skeptic calibrated the result.
This is the calibrated output. It is deliberately honest: neither inflated nor trashed.*

> **Rescored 2026-07-18** after the P0 remediation wave. Every claim below was
> **re-verified empirically** (full test suite, live eval rerun, dependency pins,
> PyPI status, in-browser checks against the deployed stack) rather than trusted
> from the previous edit's checkmarks. Methodology caveat: the original was a
> 6-persona panel; the rescore is a single rigorous audit holding the same
> weights and the same refusal to credit unverified work.
> **Live:** [app](https://nexus-bi-iota.vercel.app) · [api](https://nexus-bi-backend.onrender.com/health)

---

## Final calibrated scorecard

| Lens | Original | **Now** | What moved it |
|---|---:|---:|---|
| **As a real MVP** | 55 | **74** | Both stated reasons for the discount are gone: state is durable **and deployed** (a dashboard survived redeploy, verified in-browser), and the guard now has a 26-case × 4-dialect golden regression suite, closing the "SQLite-only tested" gap. |
| **As a free-tier SaaS a stranger would pay for** | 25 | **33** | Durable store closes one of four gaps. Still fails the literal test — no billing, no way to create an account, and Render/Vercel free tiers are non-commercial. |
| **Engineering craft / portfolio** | 78 | **90** | 4 of 5 cited judgment-misses closed and verified: IDOR fixed, monitors token-gated, **`sqlglot==30.12.0` pinned**, SQLite-only lock-in gone. Plus a shipped design system with first-class light/dark. |
| **⭐ OVERALL** | ≈48 | **≈ 63** | Same weights (MVP 35% · SaaS 30% · Craft 25% · Product/Market 10%). |

*Overall math: 74·.35 + 33·.30 + 90·.25 + 50·.10 = **63.3**.*

### Domain sub-scores

| Domain | Was | **Now** | Basis (re-verified) |
|---|---:|---:|---|
| Security | 80 | **87** | IDOR class closed, SSE replays instead of re-executing, monitors token-gated, sqlglot pinned. Still open: TOCTOU SSRF, plaintext PII in `queries.payload`. |
| Architecture | 74 | **80** | SQLite-only cap removed (dual-backend AppStore); join graph is FK-introspected, not Olist-hardcoded. Still capped: in-memory rate limiter/state, no horizontal scale. |
| Backend | 70 | **80** | Ephemeral persistence and SSE cost-amplification both fixed. Still open: O(n) PBKDF2 auth, no target-DB pooling. |
| Frontend / UX | 63 | **84** | Mobile nav, error boundaries, retry states — all verified live. Now a token-driven design system with a **real light theme** (designed, not inverted), themed interactive charts, motion gated on `prefers-reduced-motion`, and cold-start states that explain themselves. Still open: no login/account shell, no a11y audit. |
| ML / Data-science | 62 | **66** | Olist-hardcoded join graph genuinely gone; Spider/BIRD now deterministic (**9/14 = 64% EX**, was a nondeterministic 7–9/14 spread). **But hard-query accuracy did not move** — reran the eval: still **49% overall, 8% on hard**. |
| Product / Market | 45 | **50** | Semantic/metrics layer shipped and live (9 certified definitions, safety-verified on write) — closes 1 of 4 cited gaps. Moat, ICP validation, market consolidation unchanged. |
| Finance / Unit-economics | 50 | **50** | No monetization work. Unchanged. |
| Ops / Compliance | 42 | **47** | Audit log is now durable (Postgres) as a side effect of the app-store migration. ToS/Privacy/DPA still absent; PII still plaintext at rest. |

### What was explicitly *not* credited

Discipline matters more than the number. These were checked and refused:

- **Hard-join accuracy** — reran `evals.run_evals` live: **49% / 8% hard**, unchanged. The join-graph fix improved BYO-schema *portability*, not the accuracy ceiling. Do not conflate the two.
- **`sqlguard` on PyPI** — `pypi.org/pypi/sqlguard/json` returns **404**. Release infra is built (token-free Trusted Publishing) but nothing is published.
- **Billing, ToS/Privacy/DPA, PII encryption, login shell** — confirmed still absent.

**Test suite:** 189 tests — 183 passed, 6 skipped, 0 failed (was 158).

---

## The one thing everyone over-rates

**The "5-layer safety guard."** It is the crown jewel *and* the entire go-to-market thesis.
Two of the three original criticisms are now fixed: ~~mostly tested against SQLite~~ (a
26-case × 4-dialect golden regression suite freezes verdicts across dialects) and
~~unpinned `sqlglot`~~ (`sqlglot==30.12.0`, pin documented as load-bearing).

**The third criticism stands, and it is the important one:** it is a **copyable moat** — a
read replica plus a read-only `GRANT` gives a DBA ~90% of the same guarantee for free.
People read "5-layer" and hear "enterprise-safe." What it actually is now: a genuinely
well-built, well-tested, dependency-pinned guard — defending a moat two lines of SQL can
dig. Engineering fixed what engineering could. The remaining problem is a *market*
problem, and no amount of further hardening solves it.

---

## Three uncomfortable truths

1. **The core trust sell may be structurally unwinnable solo.** The entire pitch is "trust my
   guard enough to point it at your production data." No design partners, no SOC2, one author,
   non-SQLite paths untested. Realistic ceiling is *read-replica only* — and even then the
   customer will use their own read-only role, which collapses the differentiation.
2. **The accuracy ceiling and the margin story are the same fact.** ~49% execution-accuracy on
   hard joins is a coin-flip on the queries that matter, on an Olist-hardcoded join graph that
   won't generalize. The only fix (a frontier LLM) reintroduces the uncapped variable COGS that
   the "$0 deterministic" advantage was built on. And that 49% comes from a benchmark that is
   admittedly nondeterministic.
3. **No distribution engine, in a closing market, against a 20k-star incumbent (Vanna).** A
   better guard with zero distribution loses to a worse guard with a community. "No GTM" is a
   *now* problem, not a P3 one.

---

## The decision that gates everything

> **Is "provable safety" actually a top-3 buying criterion?**
> Honest prior: probably not — it's a checkbox a read-only role already ticks.
> **Writing billing code before validating this is the single most expensive mistake on the
> roadmap.**

---

## Top-5 blockers → highest-leverage moves

**The 5 things most holding back the score**

1. ~~**Ephemeral persistence (cited by 5 of 6 reviewers).**~~ ✅ **FIXED.** `AppStore` now has a
   Postgres backend (dialect shim: `?`→`%s`, `INSERT OR REPLACE`→`ON CONFLICT`, `DOUBLE PRECISION`
   timestamps, `information_schema` migration); set `APP_DB_URL` to a free Supabase/Neon Postgres
   and all state survives redeploys. Verified: the full 146-test backend suite passes against a
   real Postgres, plus a persistence-across-restart round-trip. `render.yaml` + `docs/DEPLOY.md`
   updated. *(Original finding: asserted `sqlite:///` only; Render mounts no disk.)*
2. **No monetization or metering surface at all.** Cannot charge today; true COGS (ML CPU +
   BYO-CSV storage) is uncapped.
3. ~~**Broken access control / multi-tenancy.**~~ ✅ **FIXED.** Closed the whole GET-by-id IDOR
   class — `query`, `conversations`, `dashboards`, and `monitors`/`alerts` now enforce
   `authorize_connection`/`authorize_owner` (per-connection tenant isolation; the demo stays
   public). The SSE stream is rate-limited and **replays a completed query from its stored result
   instead of re-running the pipeline** (kills the DoS/cost-amplification vector); `run-all` is
   gated by a service token (`MONITOR_RUN_TOKEN`) and hardened to isolate per-monitor failures.
   Verified by a multi-tenant test suite (tenant B blocked from A's resources; 158 tests pass).
4. **No legal / compliance surface.** No ToS/Privacy/DPA; query payloads cache PII as plaintext
   JSON at rest — a hard B2B blocker. *(Audit-log durability: ✅ fixed — now Postgres-backed.)*
5. ~~**Stranger-facing credibility gaps.**~~ ✅ **Largely fixed.** Mobile nav, route-level
   `error.tsx`/`loading.tsx`/`not-found.tsx`, skeletons + visible error/retry, a token-driven
   design system with a real light theme, themed interactive charts, and cold-start states that
   explain the free-tier wake-up instead of looking frozen — all verified in-browser on the live
   deployment. Still open: no login/account shell; **~49% accuracy on hard joins (unchanged)**;
   no design partners.

> **The top-5 list is now front-loaded with problems engineering cannot solve.** #1, #3 and #5
> are done; #2 and #4 are business/legal decisions, not code. That is the real story of this
> rescore: the build quality is no longer the bottleneck.

**The 5 highest-leverage moves**

1. Postgres app-store adapter + Alembic migrations + object-storage uploads + remove the
   sqlite-only assert. *(L — the keystone; unlocks durability, scale, backups.)*
2. Stripe billing + per-workspace usage metering + a BYO-LLM-key Pro tier. *(L)*
3. Close the access-control gaps and protect the SSE stream (cache-replay, not re-execute). *(M)*
4. Reposition to "the safety + governance layer for text-to-SQL" and land 3–5 design partners
   to validate the riskiest assumption. *(M–L)*
5. Fix the product shell — mobile nav, account/login, `error.tsx`/`loading.tsx`/`not-found.tsx`,
   visible error + retry states. *(S–M)*

---

## Master implementation plan

### P0 — Make it real & live ✅ **COMPLETE (2026-07-18)**
Durable, live, safe-to-connect single-tenant product. **All four tracks shipped and
verified against the live deployment.** Backend on Render + Neon Postgres, frontend on
Vercel, every route pulling real data. Remaining work starts at P1 — see
[`ROADMAP.md`](./ROADMAP.md) for the phased plan.

| Track | Workstreams |
|---|---|
| Backend | Postgres app-store adapter behind `AppStore`; Alembic migrations; remove sqlite assert; uploads → object storage. **Pin all deps + lockfile + a sqlglot-pinned safety regression suite.** |
| Security | `authorize_connection` on `GET`/`stream`; SSE replays the cached result (no re-exec); service token on `run-all`; `user_id` on monitors. |
| Frontend | Mobile hamburger nav; route-level `error.tsx`/`not-found.tsx`/`loading.tsx` + error boundary; replace silent `.catch(()=>{})` with visible error + retry. |
| Ops | Deploy live to a non-sleeping instance; automated daily Postgres backup. |

**Free-tier reality:** fits ~$0 **except** the keystone — Render free's filesystem is ephemeral,
so durability needs a free managed Postgres (Supabase / Neon free tier) as the app store. That's
the one place $0 forces a choice, not a payment.

### P1 — First paying customer (realistically 2–3 months, not 2–6 weeks)
A stranger can sign up, connect a DB, and pay.

| Track | Workstreams |
|---|---|
| Product | Reposition to a safety/governance control plane; name ONE ICP (mid-market Postgres/MySQL data teams); land 3–5 design partners off the live demo. |
| Backend | Indexed key-id auth + single hash verify; real target-DB connection pooling; Redis-backed rate limiter + allow-list cache invalidation. |
| Frontend | Account shell (login/logout/settings, connection switcher); skeleton loaders; a11y (skip-link, `aria-live` for streaming). |
| Ops | ToS + Privacy Policy + DPA + sub-processor list; encrypt `queries.payload` or make caching opt-in with TTL/purge; Sentry + uptime check + status page; X-Forwarded-For-aware rate limiting. |
| Finance | Stripe Free/Pro/Team plan-gating; per-workspace metering; **BYO-LLM-key Pro tier from the first paid tier**; convert design partners at **$29–49/mo**. |

**Cost reality:** Vercel Hobby is non-commercial → **Vercel Pro ($20/mo)** at monetization.
Redis + managed Postgres + non-sleeping instance ≈ **$30–60/mo fixed before the first dollar**;
net-negative until ~5–10 seats. **This breaks the "free-tier SaaS" framing** — it is
paid-from-day-one or a portfolio piece, not a freemium play.

### P2 — Real SaaS (6–12 weeks)
Multi-tenant, operable, self-serve.

| Track | Workstreams |
|---|---|
| Product | Lightweight semantic/metrics layer (certified metric defs + synonyms) so answers hit governed numbers; publish honest accuracy-by-difficulty delta. *(Gated behind validating the safety-buying-criterion question.)* |
| Backend | Org/user/role model with row-level scoping across connections/queries/dashboards/monitors/alerts; background worker + scheduler (RQ/Arq/Celery + Redis) for monitors/briefing; move CPU-bound ML off the request path. |
| Frontend | Org/connection switcher in global nav; first-run onboarding; multiline query bar; Playwright e2e for ask → stream → result. |
| Ops | Incident-response + support runbooks; starter SLA; key-rotation procedure; SSRF DNS-rebinding hardening; live Postgres/BigQuery integration tests. |
| Finance | Enforce per-tier caps (queries/day, upload rows/MB, concurrent forecasts); break-even seat pricing; usage-based overage. |

**Cost reality:** ≈ **$80–200/mo**; needs ~10–20 paying seats to reach infra break-even. Margin
is defensible only once metering caps the ML/storage COGS tail.

### P3 — Scale / moat (3–6 months; pull OSS distribution forward to P0)
Durable advantage beyond a copyable safety wedge.

| Track | Workstreams |
|---|---|
| Product | ✅ **Open-sourced the safety guard** as a standalone MIT-licensed library — [`github.com/krish2105/sqlguard`](https://github.com/krish2105/sqlguard), its own repo + CI (4-way Python 3.10–3.13 matrix, all green), `pip install`-able, 35 tests incl. the 100%-adversarial eval + a cross-dialect golden regression suite. ✅ **Semantic/metrics layer shipped** — governed, certified metric definitions + synonyms (`/metrics`), safety-verified on write, badge on answers. Still open: distribution/adoption (stars, PyPI publish — needs your token), deepen metrics into a real certified-numbers moat. |
| Backend | ✅ **Join graph generalized** — introspected FKs (Postgres/MySQL/SQLite) + name-based inference for FK-less/BYO schemas, replacing the Olist-hardcoded map (curated Olist edges now used only as a last-resort fallback for the demo). Still open: horizontal scale (stateless instances, externalized shared state); SSO. |
| Frontend | Full account lifecycle; embed/self-host SDK surface; chart data-table a11y toggle. |
| Ops | SOC2 path (durable exportable audit log underpins it); SLO/error-budget instrumentation; multi-region. |
| Finance | BYO-key margin optimization; embed/self-host pricing tier; seat + usage hybrid. |

---

## What this actually is, and the two rational moves

A **top-of-portfolio solo engineering sample** — a genuinely clever, honestly-evaluated
read-only text-to-SQL engine with a well-built, well-tested, dependency-pinned safety guard —
that is now **live, durable and demonstrable**, but still **not a business**: no way to charge,
no tenancy, no login, a ~49%-on-hard-joins accuracy ceiling on the buyers' key axis, and a
central "trust my guard on your prod DB" thesis that remains **unvalidated with real buyers**.
Read it as a **~90-quality hiring artifact** that has earned the right to be shown to people —
and a business that still hasn't earned the right to exist.

There are two rational moves:

- **Move A — Freeze near a polished P0 and use it to get hired.** ✅ **Essentially done.**
  Durable Postgres app-store, mobile nav + error states, IDOR/SSE holes closed, deps pinned,
  premium themed frontend, **and it is live**. Remaining: write the case study, publish
  `sqlguard` to PyPI, record a demo. Highest ROI, genuinely ~$0.
- **Move B — Validate the safety-as-buying-criterion bet before building the SaaS stack.**
  ✅ The OSS-guard move is done — [`sqlguard`](https://github.com/krish2105/sqlguard) is live, its
  own repo + CI, MIT licensed. Not yet done: take the demo to 5 named mid-market Postgres teams;
  try to get one to connect a **read replica** (never prod) and pay $29–49/mo. If 3 of 5 say "a
  read-only role already does this," the wedge is a checkbox → pivot to the semantic/metrics layer
  (already partially built — see P3) or stop.

Everything between them — writing Stripe/tenancy code now — is burning solo time on a business
that hasn't earned the right to exist yet.

---

## Strategic open questions (founder only)

1. **Portfolio or startup?** Craft ~78 vs SaaS ~25 — very different roadmaps.
2. **Is "provable safety" a top-3 buying criterion?** The single riskiest assumption. Validate
   with 3–5 design partners *before* building further.
3. **Which named ICP pays, and for what?** Panel's lean: mid-market Postgres/MySQL data teams,
   sold on governance/audit — not non-technical SMBs.
4. **Semantic/metrics layer — build it, or stay a pure text-to-SQL tool?** Enterprise BI budget
   flows to certified governed metrics.

---

*Method: 6 persona audits (grounded in the live repo + web research) → board synthesis →
outside-operator skeptic calibration. Scores are the calibrated (post-skeptic) figures.*
