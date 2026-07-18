# Legal

The canonical legal text renders on the site at **`/legal`**
([app/legal](../../frontend/app/legal/page.tsx)) — Terms of Service, Privacy
Policy, a Data Processing Addendum summary, and the sub-processor list, on one
page with anchors (`/legal#terms`, `/legal#privacy`, `/legal#dpa`,
`/legal#subprocessors`). The signup form links to Terms + Privacy as a consent gate.

> **Starter documents.** These are written to be honest and specific to how Nexus
> actually works (read-only execution, encryption at rest for DSNs and result
> payloads, no training on your data) — not boilerplate. They are a starting
> point, **not legal advice**; have counsel review before any commercial launch.

## Sub-processors (quick reference)

| Sub-processor | Purpose | Data |
|---|---|---|
| Render | Backend hosting | All application data |
| Vercel | Frontend / CDN | Static assets; no DB contents |
| Neon / Supabase | App metadata DB | Accounts, **encrypted** connections + history |
| Stripe *(optional)* | Payments | Billing email + card (held by Stripe) |
| Groq *(optional)* | LLM generation/narration | Question + schema names (not row data) |
| Sentry *(optional)* | Error tracking | Scrubbed context (no auth/bodies/DSNs) |
| Upstash *(optional)* | Rate-limit + cache | Counters + hashed schema cache (no DSNs) |

## Where the privacy claims are enforced in code

The privacy/DPA claims aren't marketing — they map to real code:

- **Encryption at rest** — `app/core/crypto.py` (Fernet). DSNs encrypted in
  `create_connection`; **query result payloads encrypted** in `app_store.save_query`
  and decrypted on read (`_load_payload`).
- **Read-only execution** — `app/db/target_pool.py` (Layer 0) + the five-layer guard.
- **Tenant isolation** — `app/api/deps.py` (`authorize_connection` / `authorize_owner`).
- **Append-only audit log** — `app_store` exposes only insert + read for `audit_log`.
- **Sentry scrubbing** — `app/core/monitoring.py` `before_send` strips auth headers,
  cookies, and request bodies before an event is sent.
