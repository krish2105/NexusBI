# ICP — one page, one customer

*Phase 2 of [ROADMAP.md](../ROADMAP.md). The goal of naming an ICP isn't to exclude
customers — it's to make the 5 validation conversations specific enough to give a real
answer. A tool "for anyone with a database" gets vague reactions; a tool for **one**
named buyer with **one** named pain gets a yes or a no.*

---

## The one ICP

> **Mid-market data teams (roughly 50–500 employees) running Postgres or MySQL, where a
> non-analyst — an operator, PM, or founder — needs numbers without waiting on the data
> team, and the data team won't hand out database access to make that happen.**

Not: non-technical SMBs (no database, no governance pain, won't pay). Not: enterprises
(they'll demand SOC2 + SSO + a procurement cycle a solo project can't clear). The
middle is where the pain is real and the buying process is short enough for a design
partner to say yes in a single call.

## The buyer vs. the user (they're different people)

| | **Champion / buyer** | **End user** |
|---|---|---|
| Who | Head of Data / Analytics Engineer / Data Lead | Ops manager, PM, founder, CS lead |
| Feels the pain of | "I'm the human WHERE-clause. Every 'quick question' is a context-switch, and I can't just give them read access." | "I wait a day for a number I need now, or I nag someone." |
| Says yes because | Self-serve answers **without** granting DB access, with an audit trail of every query run | They get the number in seconds, in English, with the chart |
| Kills the deal by | Not trusting the guard on real data | Not trusting the *answer* |

The champion is who you sell to. The end user is why the champion cares.

## The pain, in their words (what to listen for)

- "Half my week is answering ad-hoc data questions in Slack."
- "I *can't* give them read access — one bad query and prod is on fire, and I've got no record of who ran what."
- "The BI tool needs someone to build the dashboard first; nobody asks the questions we didn't predict."
- "I don't trust an AI to touch our database."  ← this is the thesis under test, not an objection to dodge.

## Why now

Every data team is being asked "can we put an LLM on our database?" by someone above
them this quarter. They *want* to say yes and are scared to. The wedge is: **a way to
say yes that is provably read-only and fully audited** — the two things that let a Head
of Data sign off without losing sleep.

## Positioning statement (say this in the first 30 seconds)

> "Nexus lets your operators ask your Postgres questions in plain English and get real
> answers — SQL, chart, and a written takeaway — **without you granting anyone database
> access.** Every query is provably read-only before it runs, and every one is logged.
> It's the governance layer that lets you say yes to self-serve analytics."

Note what this leads with: **not** "AI analyst" (commodity, scary). It leads with
*governed access* and *audit* — the champion's job, not the demo's flash.

## Where to find 5 of them (concrete)

- **Warm first.** Your own network: anyone who's ever been the "human WHERE-clause."
  One warm intro beats twenty cold emails.
- **dbt Community Slack**, **Locally Optimistic**, **r/dataengineering** — where Heads
  of Data actually hang out. Participate, don't pitch; then DM.
- **LinkedIn search:** title `Head of Data` OR `Analytics Engineer` OR `Data Lead`,
  company size 51–500, industry e-commerce / SaaS / fintech. Note who posts about
  "data requests" or "self-serve analytics."
- **The `sqlguard` launch** (see [../../packages/sqlguard/LAUNCH.md](../../packages/sqlguard/LAUNCH.md)) —
  the people who comment on an HN/Reddit post about SQL safety *are* the ICP,
  pre-qualified by the fact that they clicked.

## The one question this ICP exists to answer

> **Is "provably read-only + audited" a top-3 reason they'd adopt, or a checkbox their
> read-only role already ticks?**

If it's top-3, there's a business. If it's a checkbox, the wedge is copyable and the
honest move is to pivot to the semantic/metrics layer or stop. That's what the 5
conversations are for — see [`OUTREACH.md`](./OUTREACH.md) and record the answer in
[`VALIDATION_VERDICT.md`](./VALIDATION_VERDICT.md).
