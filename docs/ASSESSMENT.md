# Nexus BI — C-Level Assessment & Master Plan

*A C-level panel (CEO · CTO · CFO · COO · Senior Frontend · Senior Backend) audited the
live repository — web-grounded on the competitive landscape and current free-tier
limits — then a board synthesis and an outside-operator skeptic calibrated the result.
This is the calibrated output. It is deliberately honest: neither inflated nor trashed.*

---

## Final calibrated scorecard

| Lens | Board | **Calibrated** | Why the discount |
|---|---|---|---|
| **As a real MVP** | 70 | **55** | Ephemeral state (loses everything on redeploy) + the safety core is largely **untested on the non-SQLite databases it exists to protect**. |
| **As a free-tier SaaS a stranger would pay for** | 34 | **25** | Literal test ≈ near-zero: no billing, no tenancy, no durable store, no login, non-commercial hosting tiers. |
| **Engineering craft / portfolio** | 88 | **78** | Brilliant core, but IDOR on `GET /query/{id}` + `/stream`, unauthenticated monitors, plaintext PII at rest, **unpinned `sqlglot`** (the safety layer floats on a live dependency), and sqlite-only lock-in are real judgment misses. |
| **⭐ OVERALL** | 61 | **≈ 48** | Same weighting (MVP 35% · SaaS 30% · Craft 25% · Product/Market 10%). The board's 61 was inflated ~10–13 pts by craft/MVP absorbing the ephemerality and untested-safety-path problems without penalty. |

### Domain sub-scores

| Domain | Score | Basis |
|---|---:|---|
| Security | **80** | Legitimately senior threat model (5-layer guard, SSRF screen, read-only verify, Fernet DSNs, audit log); dinged by IDOR + unauth monitors, TOCTOU SSRF, unpinned sqlglot. |
| Architecture | **74** | Clean layered design, deterministic agent graph, elegant multi-dialect abstraction; capped by SQLite-only app store and single-instance state. |
| Backend | **70** | Production-grade safety core, cleanly typed; undercut by ephemeral persistence, unthrottled SSE re-exec, O(n) PBKDF2 auth, no real pooling. |
| Frontend / UX | **63** | Tasteful design system, excellent SSE streaming + agent-pipeline viz; broken mobile nav, no auth/account shell, silent error swallowing, no error boundaries. |
| ML / Data-science | **62** | Honest evals (rolling-origin backtest, band coverage, Spider/BIRD harness); ~49% exec-acc on hard joins and an Olist-hardcoded join graph limit BYO-schema accuracy. |
| Product / Market | **45** | Sharp, clearly-articulated safety wedge; but narrow/copyable moat, no semantic layer, unvalidated ICP, consolidating market. (Board 58 → skeptic 45.) |
| Finance / Unit-economics | **50** | Deterministic default = $0 LLM COGS is a real win; but zero monetization surface and uncapped ML/CPU + BYO-CSV storage COGS. |
| Ops / Compliance | **42** | Strong runbook and CI gate; but non-durable audit log, no ToS/Privacy/DPA, plaintext PII at rest, no monitoring/incident response. |

*Overall math (same weights, Product/Market marked 58→45):
55·.35 + 25·.30 + 78·.25 + 45·.10 = **≈ 48–51**.*

---

## The one thing everyone over-rates

**The "5-layer safety guard."** It is the crown jewel *and* the entire go-to-market thesis —
but it is (a) mostly tested against **SQLite**, not the Postgres/MySQL/BigQuery targets it is
meant to protect; (b) built on an **unpinned `sqlglot`**, so a transitive parser bump can
silently change what SQL it accepts or rejects; and (c) a **copyable moat** — a read replica
plus a read-only `GRANT` gives a DBA ~90% of the same guarantee for free. People read
"5-layer" and hear "enterprise-safe." What it actually is: a well-designed guard, tested on
the wrong database, on a floating dependency, defending a moat two lines of SQL can dig.

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

1. **Ephemeral persistence (cited by 5 of 6 reviewers).** `AppStore` asserts `sqlite:///` only;
   no Postgres adapter; `render.yaml` mounts no disk. Every redeploy wipes users, encrypted
   DSNs, audit log, monitors, uploads. Nothing else matters until this is fixed — and it
   contradicts what the docs claim.
2. **No monetization or metering surface at all.** Cannot charge today; true COGS (ML CPU +
   BYO-CSV storage) is uncapped.
3. **Broken access control / multi-tenancy.** Monitors unauthenticated + unscoped;
   `GET /query/{id}` and `/stream` skip `authorize_connection` (IDOR); the SSE stream re-runs
   the full pipeline unthrottled (DoS + cost amplification).
4. **No legal / compliance surface.** No ToS/Privacy/DPA; query payloads cache PII as plaintext
   JSON at rest; audit log non-durable — a hard B2B blocker.
5. **Stranger-facing credibility gaps.** Mobile nav completely broken (6 of 8 routes unreachable
   on phones); no login/account shell; ~49% accuracy on hard joins; no design partners.

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

### P0 — Make it real & live (~3–5 focused solo weeks; board said 2)
Durable, live, safe-to-connect single-tenant product.

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
| Product | **Open-source the safety guard as a standalone "read-only text-to-SQL guardrail" library** (Vanna-adjacent) to seed developer adoption; deepen the semantic layer into a certified-metrics moat. |
| Backend | Horizontal scale (stateless instances, externalized shared state); generalize the deterministic generator's join graph via introspected FKs for BYO schemas; SSO. |
| Frontend | Full account lifecycle; embed/self-host SDK surface; chart data-table a11y toggle. |
| Ops | SOC2 path (durable exportable audit log underpins it); SLO/error-budget instrumentation; multi-region. |
| Finance | BYO-key margin optimization; embed/self-host pricing tier; seat + usage hybrid. |

---

## What this actually is, and the two rational moves

A **top-of-portfolio solo engineering sample** — a genuinely clever, honestly-evaluated
read-only text-to-SQL engine with a well-designed safety guard — that is **not yet a product**:
it loses all state on redeploy, has no way to charge, no tenancy, no login, a ~50%-on-hard-joins
accuracy ceiling on the buyers' key axis, and a central "trust my guard on your prod DB" thesis
that is unproven and mostly SQLite-tested. Read it as an **~78-quality hiring artifact wearing a
business costume**.

There are two rational moves:

- **Move A — Freeze near a polished P0 and use it to get hired.** The craft score already clears
  the bar. Deploy live (free tier + free managed Postgres for durability), fix mobile nav + error
  states + the IDOR/SSE holes, pin deps, write the case study. Highest ROI, genuinely ~$0.
- **Move B — Validate the safety-as-buying-criterion bet before building the SaaS stack.** Pull
  the P3 OSS-guard move to P0 (cheapest distribution + validation instrument) and take the demo
  to 5 named mid-market Postgres teams; try to get one to connect a **read replica** (never prod)
  and pay $29–49/mo. If 3 of 5 say "a read-only role already does this," the wedge is a checkbox →
  pivot to the semantic/metrics layer or stop.

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
