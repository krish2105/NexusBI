# Nexus BI — Security & Threat Model

Nexus connects an LLM to a database, so its threat model is taken seriously. This
complements [`SQL_SAFETY.md`](SQL_SAFETY.md) (the five-layer query guard) with the
platform-level controls.

## Assets
- The **target database** (read integrity — never mutated; no exfiltration).
- **Connection credentials** (DSNs, which may embed passwords).
- **Tenant boundary** — one account's data must not reach another's.

## Threats & controls

| Threat | Control | Where |
|---|---|---|
| Destructive / exfiltrating SQL | 5-layer guard (read-only role, AST allow-list, LIMIT, NL screen, dry-run) — **100% adversarial blocked in eval** | `app/sqlsafety/`, `docs/SQL_SAFETY.md` |
| Prompt injection via the question | Deterministic NL intent/injection screen **before** the LLM; structural prompt delimiting | `app/sqlsafety/sanitizer.py` |
| **SSRF** via a connection string | DSN host is screened; loopback / private / link-local / `169.254.169.254` metadata hosts are blocked unless `ALLOW_LOCAL_TARGETS` (dev) | `app/core/connguard.py` |
| A "read-only" DB that actually isn't | Connect-time **read-only verification**: SQLite is enforced read-only by the pool (`mode=ro`); a Postgres role is probed with a side-effect-free write and rejected if it can write | `app/core/connguard.py` |
| Credential theft from the app DB | Target **DSNs are encrypted at rest** (Fernet, key from `ENCRYPTION_KEY`); never stored or logged in plaintext | `app/core/crypto.py` |
| Cross-tenant data access | Non-demo connections are **scoped to their owner**; queries authorize the connection against the caller | `app/api/deps.py` (`authorize_connection`) |
| Unauthenticated abuse | Optional `REQUIRE_AUTH` gates connection-create & custom queries (API key / JWT); the bundled demo stays open | `app/api/deps.py`, `app/api/auth.py` |
| Query flooding / DoS | Per-client **rate limiting** on `/query`; statement timeout + row cap on execution | `app/core/ratelimit.py`, `app/db/target_pool.py` |
| Tampering / repudiation | Append-only **audit log** of every generated SQL, verdict, and executed query | `app/db/app_store.py` |
| Info leak via errors | Global exception handler returns generic errors; raw SQL/DB errors never reach untrusted callers | `app/main.py` |

## Secrets
No secrets are committed. Configure via env (`.env`, not tracked): `JWT_SECRET`,
`ENCRYPTION_KEY`, optional `GROQ_API_KEY`. All LLM keys are optional — Nexus runs
fully with none.

## Production checklist
- [ ] Set strong `JWT_SECRET` + `ENCRYPTION_KEY`; set `REQUIRE_AUTH=true`.
- [ ] Keep `ALLOW_LOCAL_TARGETS=false`.
- [ ] Point the target at a **least-privilege read-only role** (`data/olist/read_only_role.sql`).
- [ ] Restrict `CORS_ORIGINS` to your frontend domain.
- [ ] CI safety gate (`evals.run_evals --gate`) must stay green on every deploy.

## Reporting
This is a portfolio project; open a GitHub issue for any concern.
