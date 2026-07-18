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

| # | Task | Why | Owner / status |
|---|---|---|---|
| 0.1 | Set `CORS_ORIGIN_REGEX` in the Render dashboard | Code + `render.yaml` are pushed, but Render isn't syncing blueprint env vars — preview/branch Vercel URLs still fail every fetch | 🎯 **You** (dashboard) |
| 0.2 | Publish `sqlguard` 0.1.0 to PyPI | Release workflow is built and wheel-verified; needs the one-time "pending publisher" step | 🎯 **You** (pypi.org) |
| 0.3 | Swap NexusBI off the git pin → `sqlguard==0.1.0`; drop `git` from the Dockerfile | Smaller image, honest dependency | 📝 **Staged** — exact steps in [`packages/sqlguard/PUBLISHING.md`](../packages/sqlguard/PUBLISHING.md); a one-line flip after 0.2 |
| 0.4 | Regenerate README screenshots against the new themed UI | Current images predate the light/dark redesign | ✅ **Done** (dark + light) |
| 0.5 | Add a `?theme=light` capture pass to the screenshot script | Show both themes in the README | ✅ **Done** — `THEME=light npm run screenshots` |

**Exit:** every Vercel URL works, `pip install sqlguard` works, README reflects reality.

---

## Phase 1 — The hiring artifact (≈1–2 days) 🟢 highest ROI, ~$0

Assumes **Move A**. Makes the work *legible to a human evaluator* — which is the actual
bottleneck now that the build quality is high.

| # | Task | Status |
|---|---|---|
| 1.1 | **Case study** ([`docs/CASE_STUDY.md`](./CASE_STUDY.md)) — 5-layer guard threat model; deterministic-ML + LLM-narrates-only; the Spider/BIRD determinism bug hunt; the Postgres migration. | ✅ **Done** |
| 1.2 | **90-second demo video** — ask → SQL → chart → narration, then a destructive query blocked. | ⏸️ Deferred (needs a screen recording) |
| 1.3 | **README top-fold rewrite** — live "Try it live" link + case-study link above the fold. | ✅ **Done** |
| 1.4 | **Honest accuracy section** — 49% overall / 90-56-8% by difficulty, with methodology, in the README + case study. | ✅ **Done** |
| 1.5 | **`sqlguard` README polish + launch post** ([`packages/sqlguard/LAUNCH.md`](../packages/sqlguard/LAUNCH.md) — HN / dev.to / X / Reddit). | ✅ **Done** |

**Exit:** a stranger understands the project in 90 seconds and can verify every claim.

---

## Phase 2 — Validate the bet ⚠️ **SKIPPED BY DECISION (2026-07-18)**

Assumes **Move B**. This phase was designed as **conversations, not commits** — the one
question that determines whether Phase 3+ is worth building at all.

> **Is "provable safety" a top-3 buying criterion — or a checkbox a read-only role already ticks?**
> Honest prior: probably the latter. **This was never tested.**

| # | Task | Status |
|---|---|---|
| 2.1 | Name **one** ICP | ✅ Done — [`GTM/ICP.md`](./GTM/ICP.md) |
| 2.2 | 5 design-partner conversations | ❌ **Not run** |
| 2.3 | Try to get **one** read replica connected | ❌ **Not attempted** |
| 2.4 | Write down the verdict | ⚠️ **No verdict — [`GTM/VALIDATION_VERDICT.md`](./GTM/VALIDATION_VERDICT.md) is still blank.** Phase 3 was authorized without it, by explicit founder decision, not by evidence. |

**What this means going forward:** Phase 3 shipped on a **prior, not a signal.** The kit in
[`docs/GTM/`](./GTM/) still works — running it *retroactively*, even against a live
paid-tier product, is strictly higher-signal than running it never. Recommended before
spending real ad/outbound budget: run 2.2–2.4 anyway, now with a working checkout to point
people at. The gate that was skipped is still a gap in evidence, not a solved question.

---

## Phase 3 — First paying customer ✅ **SHIPPED (2026-07-18), unverified in production**

| Track | Work | Status |
|---|---|---|
| Auth | Login/signup shell, JWT sessions, indexed key-id auth (kills the O(n) PBKDF2 scan) | ✅ Built, tested (`test_auth.py`) |
| Billing | Stripe Free/Pro tiers, per-workspace metering, **BYO-LLM-key from the first paid tier** | ✅ Built, tested (`test_billing.py`). **Dark in production** — no `STRIPE_SECRET_KEY` set anywhere, so nothing can charge until you deliberately configure it |
| Legal | ToS + Privacy + DPA + sub-processor list; `queries.payload` encrypted at rest | ✅ Built, tested (`test_payload_encryption.py`) |
| Ops | Sentry, uptime `/status`, XFF-aware rate limiting | ✅ Built, tested (`test_ops.py`) |
| Perf | Target-DB connection pooling; Redis-backed rate limiter + allow-list cache | ✅ Built, tested (`test_perf_scaling.py`) |

**Local verification (2026-07-19):** full backend suite 209 passed / 6 skipped / 0 failed;
frontend production build clean across all routes including the 6 new pages.

**🔴 Known live gap:** Vercel has deployed the new frontend pages (`/pricing`, `/login`,
`/signup`, `/status`), but the Render backend has **not** redeployed past commit `3fe7cc1`
— `/status` and `/auth/login` both 404 in production as of this writing. Frontend degrades
gracefully (no crash — `AuthProvider` no-ops without a stored token, `/pricing` renders
statically), but checkout/login/status are non-functional live until the backend deploy is
sorted. Needs a check of Render's Deploys tab for a build failure.

**Cost reality:** Vercel Hobby is non-commercial → **Vercel Pro ($20/mo)** at monetization.
Plus Redis + managed Postgres + a non-sleeping instance ≈ **$30–60/mo before the first dollar**
— once billing is actually turned on. This breaks the "free-tier SaaS" framing: it's
paid-from-day-one or it's a portfolio piece.

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
Phase 0 ──> Phase 1 (hiring artifact) ──────────────> DONE, shipped
         └─X Phase 2 (validate) ──[gate, skipped]──> Phase 3 ──> Phase 4
                                                          │
                                              (built without evidence)
```

Original design: Phase 1 and Phase 2 run in parallel, Phase 3 waits for Phase 2's verdict.
**Actual: Phase 2's gate was bypassed by founder decision on 2026-07-18** — Phase 3 shipped
on zero customer conversations. The `docs/GTM/` kit still exists and still works; running
it now, against a live paid product, remains the way to find out if Phase 4's ~$80–200/mo
commitment is worth making.

---

## What I'd actually do from here

The gate is already crossed, so the highest-leverage next move isn't re-litigating that —
it's **closing the loop the shortcut created**: get the Render deploy green so the live
site matches what's in git, then run the Phase 2 conversations retroactively (you now have
a stronger opener: a working demo *and* a checkout link, not just a promise). If those
conversations come back "checkbox," Phase 4's spend is still avoidable — the code doesn't
force the money to follow.
