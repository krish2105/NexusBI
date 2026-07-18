# Design-partner outreach + conversation script

*Phase 2 of [ROADMAP.md](../ROADMAP.md). Five conversations to answer one question:
is provable safety a **top-3 buying criterion**, or a checkbox a read-only role already
ticks? The [ASSESSMENT](../ASSESSMENT.md) prior is "probably the checkbox." Your job is
to disprove or confirm it with real buyers before writing a line of billing code.*

The discipline here is [The Mom Test](http://momtestbook.com/): **ask about their life,
not your idea.** People lie to be nice about your idea; they can't lie about what they
did last week. Never ask "would you use this?" or "do you like it?" — both are
worthless. Ask what they do today, what it costs them, and what they've already paid to
fix it.

---

## Outreach templates

Keep it short. You're asking for 20–30 minutes of their expertise, **not** a demo, and
**not** a sale. Lead with their problem, not your product.

### Cold email

> **Subject:** how do you handle ad-hoc data requests?
>
> Hi {name} — I saw you lead data at {company}. I'm researching how mid-market data
> teams handle the flood of ad-hoc "quick question" data requests without giving out
> database access.
>
> I'm not selling anything — I've built a read-only text-to-SQL tool and I'm trying to
> figure out if the problem I think it solves is a problem *you* actually have. Could I
> get 20 minutes to hear how your team handles this today? Happy to share what I've
> learned from other teams in return.
>
> {your name}

### LinkedIn DM (shorter)

> Hi {name} — you lead data at {company}, so you probably live the "can you just pull
> this number for me" firehose. I'm researching how teams handle ad-hoc requests
> without handing out DB access. Not a pitch — 20 min to hear how you do it today? I'll
> trade you what I've learned from other data leads.

### Warm intro ask (to your network)

> Quick favor: do you know any Head of Data / analytics eng at a 50–500-person company
> on Postgres or MySQL? I'm doing 5 research calls on how teams handle ad-hoc data
> requests + DB access. Not selling — just learning. A one-line intro would be gold.

---

## The 30-minute conversation script

**Frame it (30 sec):** "This is research, not a pitch. I want to understand how you
handle data requests today. I'll show you a thing at the end only if it's relevant, and
I genuinely want to know where it's wrong."

### Part 1 — Their world today (10 min, no product talk)

The goal is facts about the past, not opinions about the future.

1. "Walk me through the last time someone outside the data team needed a number. What happened?"
2. "How often does that happen? Who asks?"
3. "What's the actual cost — your time, the wait, the context-switch?"
4. "Why don't you just give them read access to the database?" *(listen hard here — this is the thesis)*
5. "Have you tried to solve this? What did you try? What did it cost / why did you stop?"
6. "Who else touches this decision — security, compliance, your manager?"

**Listen for:** whether *access + audit* comes up unprompted, or whether they only care
about the analyst being fast/accurate. If governance never comes up on its own, that's
a signal the wedge is weaker than the thesis assumes.

### Part 2 — Show the live demo (8 min)

Only now. Open [the live app](https://nexus-bi-iota.vercel.app/app) and:
1. Ask a real question → SQL + chart + narration.
2. Type `delete all orders` → watch it get blocked before a model sees it.
3. Show `/trust` (audit log, block rate) and `/metrics` (governed definitions).

Then stop talking and watch their face. **Do not explain why it's great.** Ask:
- "What's your honest first reaction?"
- "Where does this break for your data?"
- "What would your security person say about pointing this at a read replica?"

### Part 3 — The questions that actually matter (10 min)

These separate polite interest from real demand. **Ask what they'd pay, not whether
they'd use it.**

1. "If this existed and worked on your data, what would you *stop* doing?"
2. "Would you connect a **read replica** to try it? What would have to be true first?" *(the single strongest signal — a yes here is worth more than any compliment)*
3. "Who would need to approve that, and what would block it?"
4. "What do you pay today for tools in this area?" → then: "If a team plan were $29–49/seat/month, is that a no-brainer, a maybe, or a no?"
5. "Is 'provably read-only + fully audited' a top-3 reason you'd adopt — or does your read-only role already cover that?" *(ask it straight; the honest answer is the whole point)*
6. "Who else should I talk to?" *(referral = they took it seriously)*

### Close (1 min)

"This was incredibly helpful. Can I come back to you when I've addressed {the thing
they raised}? And — would you want to be one of 5 design partners I work with directly?"

A yes to *design partner* + *connect a replica* + *a price that isn't "no"* is the
result you're hunting. Log it immediately after the call in
[`VALIDATION_VERDICT.md`](./VALIDATION_VERDICT.md) while it's fresh.

---

## Anti-patterns (how these calls go wrong)

- **Pitching instead of listening.** If you're talking >40% of Part 1, you're selling, not learning.
- **Fishing for compliments.** "Cool, right?" gets a "yeah, cool" that means nothing.
- **Accepting "I'd definitely use that."** It's the most common lie. Counter with "great — would you connect a replica this week?" Future-tense enthusiasm is free; a calendar commitment is data.
- **Explaining away objections.** When they say "my read-only role already does this," don't argue. Write it down. That sentence, said 3 of 5 times, is your answer.
- **Talking to the wrong person.** An IC analyst who loves it can't sign off on connecting a database. Get to the person who owns that decision.
