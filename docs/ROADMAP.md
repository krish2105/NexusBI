# Nexus BI — Remaining Plan (phased)

**Status: P0 complete. Score ≈63/100** ([ASSESSMENT.md](./ASSESSMENT.md)).
Live: [app](https://nexus-bi-iota.vercel.app) · [api](https://nexus-bi-backend.onrender.com/health)

This is the execution plan for what's left. It is ordered so that **the cheapest work that
changes a decision comes before the expensive work that assumes the decision**. Nothing here
is started — it's a plan to argue with, not a changelog.

The single most expensive mistake available right now is **building billing and tenancy before
knowing whether anyone buys the safety wedge.** Phase 1 and Phase 2 exist to prevent that.

---

## Phase 0 — Loose ends (≈1–2 hours) 🔴 do first regardless of direction

Small, already-unblocked, and two of them are *live-site correctness*.

| # | Task | Why | Owner |
|---|---|---|---|
| 0.1 | Set `CORS_ORIGIN_REGEX` in the Render dashboard | Code + `render.yaml` are pushed, but Render isn't syncing blueprint env vars — preview/branch Vercel URLs still fail every fetch | **You** (dashboard) |
| 0.2 | Publish `sqlguard` 0.1.0 to PyPI | Release workflow is built and wheel-verified; needs the one-time "pending publisher" step | **You** (pypi.org) |
| 0.3 | Swap NexusBI off the git pin → `sqlguard==0.1.0`; drop `git` from the Dockerfile | Smaller image, honest dependency | Me, after 0.2 |
| 0.4 | Regenerate README screenshots against the new themed UI | Current images predate the light/dark redesign | Me |
| 0.5 | Add a `?theme=light` capture pass to the screenshot script | Show both themes in the README | Me |

**Exit:** every Vercel URL works, `pip install sqlguard` works, README reflects reality.

---

## Phase 1 — The hiring artifact (≈1–2 days) 🟢 highest ROI, ~$0

Assumes **Move A**. Makes the work *legible to a human evaluator* — which is the actual
bottleneck now that the build quality is high.

| # | Task | Detail |
|---|---|---|
| 1.1 | **Case study** (`docs/CASE_STUDY.md`) | The 5-layer guard's threat model; why deterministic ML + LLM-narrates-only; the Spider/BIRD determinism bug hunt (a genuinely good story); the Postgres migration. Written for a hiring manager who will skim. |
| 1.2 | **90-second demo video** | Ask → SQL → chart → narration, then a destructive query getting blocked. The refusal is the money shot. |
| 1.3 | **README top-fold rewrite** | Live link + demo GIF above the fold. Nobody scrolls. |
| 1.4 | **Honest accuracy section** | Publish 49%/8%-hard *by difficulty* with the methodology. Volunteering your weakest number is a strong signal — and it pre-empts the reviewer finding it themselves. |
| 1.5 | **`sqlguard` README polish + launch post** | It's the most reusable artifact; give it its own audience. |

**Exit:** a stranger understands the project in 90 seconds and can verify every claim.

---

## Phase 2 — Validate the bet (≈1–2 weeks, mostly not coding) 🟡 gates everything after

Assumes **Move B**. This phase is **conversations, not commits.** It exists to answer the one
question that determines whether Phases 3–5 are worth writing at all.

> **Is "provable safety" a top-3 buying criterion — or a checkbox a read-only role already ticks?**
> Honest prior: probably the latter.

| # | Task | Detail |
|---|---|---|
| 2.1 | Name **one** ICP | Panel's lean: mid-market Postgres/MySQL data teams, sold on governance/audit. Not non-technical SMBs. |
| 2.2 | 5 design-partner conversations | Show the live demo. Ask what they'd pay, not whether they like it. |
| 2.3 | Try to get **one** read replica connected | Never prod. This is the real test of the thesis. |
| 2.4 | Write down the verdict | Literally commit the answer to the repo. |

**Decision gate:**
- **≥3 of 5 say "a read-only role already does this"** → the wedge is a checkbox. **Stop, or pivot** to the semantic/metrics layer (already half-built) as the primary product.
- **≥2 want to connect a replica and discuss price** → proceed to Phase 3.

---

## Phase 3 — First paying customer (≈2–3 months) 🔵 only after Phase 2 passes

| Track | Work |
|---|---|
| Auth | Login/signup shell, session handling, indexed key-id auth (kills the O(n) PBKDF2 scan) |
| Billing | Stripe Free/Pro tiers, per-workspace metering, **BYO-LLM-key from the first paid tier** |
| Legal | ToS + Privacy + DPA + sub-processor list; encrypt `queries.payload` or make caching opt-in with TTL |
| Ops | Sentry, uptime check, status page, XFF-aware rate limiting |
| Perf | Target-DB connection pooling; Redis-backed rate limiter + allow-list cache |

**Cost reality:** Vercel Hobby is non-commercial → **Vercel Pro ($20/mo)** at monetization.
Plus Redis + managed Postgres + a non-sleeping instance ≈ **$30–60/mo before the first dollar.**
This breaks the "free-tier SaaS" framing: it's paid-from-day-one or it's a portfolio piece.

---

## Phase 4 — Real SaaS (≈6–12 weeks) ⚪ only after paying customers exist

Org/user/role model with row-level scoping · background worker + scheduler (move CPU-bound
ML off the request path) · org/connection switcher + onboarding · incident-response runbook ·
per-tier caps · live Postgres/BigQuery integration tests.

**Cost:** ≈$80–200/mo; needs ~10–20 paying seats to break even on infra.

---

## Phase 5 — Accuracy & moat (ongoing) ⚪ the long pole

The one number that hasn't moved despite real effort: **8% execution accuracy on hard joins.**

| Option | Trade-off |
|---|---|
| Frontier LLM for generation | Fixes accuracy; reintroduces the uncapped variable COGS the "$0 deterministic" story was built on |
| Few-shot from the vetted-examples table | Cheap, deterministic-friendly, unproven at this schema complexity |
| Deepen the semantic layer | Sidesteps generation: if the metric is certified, don't synthesize it. **Probably the best answer** — and it doubles as the moat |
| Schema-aware fine-tune | Highest ceiling, highest effort, needs data you don't have |

**Recommendation:** treat the semantic layer as the accuracy strategy *and* the moat, rather
than chasing the generator. Certified numbers are what enterprise BI budget actually buys.

---

## Dependency graph

```
Phase 0 ──┬──> Phase 1 (hiring artifact)  ────> DONE, ship it
          └──> Phase 2 (validate)  ──[gate]──> Phase 3 ──> Phase 4
                                       │
                                       └──[fail]──> pivot to semantic layer (Phase 5)
```

Phase 1 and Phase 2 are **independent and can run in parallel** — one is writing, the other is
talking. Phases 3+ should not start until Phase 2 returns a verdict.

---

## What I'd actually do

Phase 0, then Phase 1, then Phase 2 — and **hold Phase 3 until Phase 2 answers.** Phase 1 has
guaranteed payoff (a job); Phase 3 has speculative payoff (a business) and a real monthly bill.
Doing Phase 1 first costs nothing and makes Phase 2's conversations easier, because you'll have
a demo link and a case study to open with.
