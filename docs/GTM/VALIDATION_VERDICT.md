# Validation verdict — the decision that gates everything

*Phase 2 of [ROADMAP.md](../ROADMAP.md). This file is the deliverable. Fill it in as
you run the 5 conversations ([OUTREACH.md](./OUTREACH.md)), then commit the verdict.
Writing it down is the point — it forces an honest call instead of a hopeful drift into
building billing code.*

> **The question under test:** Is "provably read-only + audited" a **top-3 buying
> criterion** for the [ICP](./ICP.md) — or a checkbox a read-only DB role already ticks?
>
> **Honest prior (from [ASSESSMENT.md](./ASSESSMENT.md)):** probably the checkbox.
> Disprove it or confirm it. Don't defend it.

---

## Status

- [ ] ICP named and committed ([ICP.md](./ICP.md)) — **done**
- [ ] Live demo ready to show — **done** ([app](https://nexus-bi-iota.vercel.app))
- [ ] Conversation 1 logged
- [ ] Conversation 2 logged
- [ ] Conversation 3 logged
- [ ] Conversation 4 logged
- [ ] Conversation 5 logged
- [ ] At least one read replica connected (or a documented reason none would)
- [ ] **Verdict written and committed**

---

## Conversation log

*Copy this block per call. Fill it in within an hour, while memory is fresh. Quote them
verbatim where you can — their words are the data.*

### Conversation N — {name}, {title} @ {company} ({date})

- **Company profile:** {size} · {Postgres/MySQL} · {industry}
- **How they handle ad-hoc requests today:** {facts, not opinions}
- **Why they don't just grant read access:** {verbatim if possible}
- **What they've already tried / paid for:** {tool, cost, why they stopped}
- **Reaction to the live demo:** {first words, where it broke for them}
- **Would they connect a read replica?**  ☐ Yes, this week  ☐ Yes, if {condition}  ☐ No — because {reason}
- **Price reaction ($29–49/seat/mo):**  ☐ No-brainer  ☐ Maybe  ☐ No
- **THE question — is provable-safety top-3, or does their read-only role cover it?**
  ☐ Top-3 buying criterion  ☐ Nice-to-have  ☐ "My read-only role already does this"
- **Referrals given:** {names}
- **One-line takeaway:** {the single most important thing you learned}

---

## Tally

Fill after all 5. This is the scoreboard the decision runs on.

| Signal | Count (/5) |
|---|---|
| Said provable-safety is a **top-3** criterion | |
| Said **"a read-only role already does this"** | |
| Willing to **connect a read replica** (yes or yes-if) | |
| Price reaction was **not** "no" | |
| Volunteered **governance/audit** as a pain *before* seeing the demo | |

---

## Decision gate

Apply the rule the roadmap committed to in advance, so the outcome isn't rationalized
after the fact:

- **≥3 of 5 say "a read-only role already does this"** → the wedge is a **checkbox**.
  The safety story is not the business. **Stop, or pivot** to the semantic/metrics layer
  (already half-built, [`/metrics`](../../README.md)) as the primary product — sell
  *certified governed numbers*, not *safe access*. Do **not** proceed to Phase 3.

- **≥2 want to connect a replica and discuss price** → the wedge has a pulse.
  Proceed to **Phase 3** (first paying customer) with those 2 as design partners. Expect
  the ~$30–60/mo fixed infra cost the roadmap names; this is now paid-from-day-one, not
  a freemium play.

- **Mixed / unclear (the likely real outcome)** → you learned the *shape* of the demand
  even if not the magnitude. Write what the strongest 2 conversations actually wanted —
  it's usually narrower and more specific than the original thesis — and let that
  redefine the ICP or the wedge before spending another month of build.

---

## VERDICT

> _Write the answer here after the 5th conversation. One paragraph. Then commit this
> file. If the honest answer is "the wedge is a checkbox," that is a **successful**
> validation — it saved you 2–3 months of building the wrong thing, and the project
> stays a top-of-portfolio hiring artifact, which was always the higher-probability
> payoff._

**Answer:** _(pending — run the conversations first)_

**Decision:** _(Stop / Pivot to semantic layer / Proceed to Phase 3)_

**Date:** _____________
