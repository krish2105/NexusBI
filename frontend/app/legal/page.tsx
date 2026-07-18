import type { Metadata } from "next";

export const metadata: Metadata = { title: "Legal — Nexus BI" };

const UPDATED = "18 July 2026";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-28">
      <h2 className="mb-3 mt-10 border-t border-line pt-8 text-2xl font-semibold tracking-tight">
        {title}
      </h2>
      <div className="space-y-3 text-[15px] leading-relaxed text-ink-dim [&_b]:text-ink [&_strong]:text-ink">
        {children}
      </div>
    </section>
  );
}

export default function LegalPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 pb-24 pt-28">
      <h1 className="text-3xl font-semibold tracking-tight">Legal</h1>
      <p className="mt-2 text-sm text-ink-faint">Last updated {UPDATED}.</p>

      <div className="mt-4 rounded-xl border border-amber/30 bg-amber/10 px-4 py-3 text-sm text-ink-dim">
        <b className="text-amber">Starter documents.</b> These are written to be honest and
        specific to how Nexus BI actually works — not boilerplate — but they are a starting
        point, not legal advice. Have counsel review them before any commercial launch.
      </div>

      <nav className="mt-6 flex flex-wrap gap-2 text-sm">
        {[
          ["terms", "Terms of Service"],
          ["privacy", "Privacy Policy"],
          ["dpa", "Data Processing"],
          ["subprocessors", "Sub-processors"],
        ].map(([id, label]) => (
          <a key={id} href={`#${id}`} className="rounded-lg border border-line px-3 py-1.5 text-ink-dim hover:text-ink">
            {label}
          </a>
        ))}
      </nav>

      <Section id="terms" title="Terms of Service">
        <p>By creating an account or using Nexus BI (the &quot;Service&quot;), you agree to these terms.</p>
        <p><b>What the Service does.</b> Nexus turns natural-language questions into read-only SQL, runs it against a database you connect, and returns charts, forecasts, and narrated insights. It is an analysis tool, not a system of record.</p>
        <p><b>Read-only by design.</b> Every generated query passes a five-layer safety guard and executes over a read-only connection. We make a strong engineering effort that the Service cannot modify your data, but you are responsible for connecting Nexus with least privilege — ideally a read replica and a read-only role. Never connect a primary/production database with write credentials.</p>
        <p><b>Your data and connections.</b> You represent that you have the right to connect any database or upload any file, and that doing so doesn&apos;t violate a third party&apos;s rights or law. You are responsible for what you ask and what you connect.</p>
        <p><b>Acceptable use.</b> Don&apos;t use the Service to break the law, infringe rights, attempt to defeat the safety guard, probe others&apos; data, or overload the infrastructure.</p>
        <p><b>Accounts.</b> Keep your password and API key secret; you&apos;re responsible for activity under your account. Tell us promptly about any unauthorized use.</p>
        <p><b>Availability &amp; disclaimers.</b> The Service is provided &quot;as is,&quot; without warranties. Generated SQL and AI-written narratives can be wrong; verify anything you rely on. We are not liable for indirect or consequential damages, and our total liability is limited to the amount you paid in the prior 12 months (or, on the free tier, USD 0).</p>
        <p><b>Termination.</b> You may stop using the Service and delete your account at any time. We may suspend accounts that violate these terms.</p>
        <p><b>Changes.</b> We may update these terms; material changes will be posted here with a new &quot;last updated&quot; date.</p>
      </Section>

      <Section id="privacy" title="Privacy Policy">
        <p><b>What we collect.</b></p>
        <ul className="list-inside list-disc space-y-1">
          <li><b>Account:</b> your email and a password hash (we never store the password itself).</li>
          <li><b>Connections:</b> a name and the database connection string, which is <b>encrypted at rest</b> before it touches our database.</li>
          <li><b>Query history:</b> your questions, the generated SQL, and the results — the result payload (which may contain data from your database) is <b>encrypted at rest</b>.</li>
          <li><b>Usage &amp; audit:</b> timestamps, query counts (for plan limits), and an append-only audit log of what ran and what was blocked.</li>
        </ul>
        <p><b>How we use it.</b> To run the Service, enforce plan limits, keep an audit trail, secure the platform, and — if you contact us — support you. We do <b>not</b> sell your data or use your database contents to train models.</p>
        <p><b>Sharing.</b> Only with the sub-processors listed below, as needed to run the Service, and when required by law.</p>
        <p><b>Retention.</b> Account data lives until you delete your account. Query history is retained so you can revisit it; you can delete individual queries or your whole account, which removes the associated history.</p>
        <p><b>Security.</b> Connection strings and result payloads are encrypted at rest; all execution against your database is read-only and least-privilege; every query is logged. No security is perfect, but the architecture is built so the worst-case failure is a rejected query, not a destructive one.</p>
        <p><b>Your rights.</b> Access, export, correct, or delete your data by using the account controls or contacting us. If you&apos;re in a region with data-protection laws (e.g. GDPR/CCPA), those rights apply.</p>
        <p><b>Cookies.</b> We use a single session token stored in your browser to keep you signed in. No third-party advertising or tracking cookies.</p>
      </Section>

      <Section id="dpa" title="Data Processing Addendum (summary)">
        <p>When you connect your own database, you are the <b>data controller</b> and Nexus is a <b>data processor</b> acting on your instructions.</p>
        <ul className="list-inside list-disc space-y-1">
          <li><b>Scope:</b> we process the data returned by the read-only queries you run, plus the metadata above, only to provide the Service.</li>
          <li><b>Sub-processors:</b> the vendors listed below; we&apos;ll give notice of material changes.</li>
          <li><b>Security measures:</b> encryption at rest for secrets and result payloads, read-only least-privilege execution, tenant isolation, an append-only audit log.</li>
          <li><b>Data-subject requests:</b> we&apos;ll assist you in responding to access/deletion requests for data processed through the Service.</li>
          <li><b>Breach notification:</b> we&apos;ll notify you without undue delay after becoming aware of a personal-data breach affecting your data.</li>
          <li><b>Deletion:</b> on account termination we delete your connections, history, and account data.</li>
          <li><b>International transfers:</b> our sub-processors may process data in the US/EU; standard contractual clauses apply where required.</li>
        </ul>
        <p>A full signable DPA is available on request for customers who need one.</p>
      </Section>

      <Section id="subprocessors" title="Sub-processors">
        <p>Nexus relies on these vendors to run the Service. Ones marked <i>optional</i> are only engaged if the corresponding feature is enabled for your deployment.</p>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink-faint">
                <th className="py-2 pr-4 font-medium">Sub-processor</th>
                <th className="py-2 pr-4 font-medium">Purpose</th>
                <th className="py-2 font-medium">Data</th>
              </tr>
            </thead>
            <tbody className="text-ink-dim">
              {[
                ["Render", "Backend hosting", "All application data in transit/at rest"],
                ["Vercel", "Frontend hosting / CDN", "Static assets; no database contents"],
                ["Neon / Supabase", "Application metadata database", "Accounts, encrypted connections, encrypted history"],
                ["Stripe (optional)", "Payment processing", "Billing email + card details (held by Stripe, never by us)"],
                ["Groq (optional)", "LLM for SQL generation / narration", "Your question + schema names (not row data) — only if a key is set"],
                ["Sentry (optional)", "Error tracking", "Scrubbed error context (no auth, bodies, or DSNs)"],
                ["Upstash (optional)", "Rate-limit + cache", "Rate-limit counters + hashed schema cache (no DSNs)"],
              ].map((r) => (
                <tr key={r[0]} className="border-b border-line/60">
                  <td className="py-2 pr-4 font-medium text-ink">{r[0]}</td>
                  <td className="py-2 pr-4">{r[1]}</td>
                  <td className="py-2">{r[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </main>
  );
}
