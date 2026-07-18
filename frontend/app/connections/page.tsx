"use client";
import { useRef, useState } from "react";
import { motion } from "motion/react";
import Link from "next/link";
import {
  Database,
  Table2,
  BookOpen,
  ShieldCheck,
  Gauge,
  Upload,
  Loader2,
  ArrowRight,
  Plug,
} from "lucide-react";
import { getSchema, getEvals, uploadCsv, connectDatabase } from "@/lib/api";
import { useResource } from "@/lib/useResource";
import { CardSkeleton, ErrorState } from "@/components/States";

export default function Connections() {
  const {
    data: meta,
    loading: schemaLoading,
    error: schemaError,
    reload: reloadSchema,
  } = useResource<{ schema: any; evals: any }>(async () => {
    const [schema, evals] = await Promise.all([getSchema(), getEvals()]);
    return { schema, evals };
  });
  const schema = meta?.schema;
  const evals = meta?.evals;
  const [open, setOpen] = useState<string | null>("orders");
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState<any>(null);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dsn, setDsn] = useState("");
  const [connName, setConnName] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connResult, setConnResult] = useState<any>(null);
  const [connErr, setConnErr] = useState<string | null>(null);

  const connect = async () => {
    if (!dsn.trim() || connecting) return;
    setConnecting(true);
    setConnErr(null);
    setConnResult(null);
    try {
      const res = await connectDatabase(connName.trim() || "External database", dsn.trim());
      setConnResult(res);
    } catch (e: any) {
      setConnErr(e.message || "connection failed");
    } finally {
      setConnecting(false);
    }
  };

  const onFiles = async (files: FileList | null) => {
    if (!files || !files.length) return;
    setUploading(true);
    setUploadErr(null);
    setUploaded(null);
    try {
      const name = files[0].name.replace(/\.[^.]+$/, "");
      const res = await uploadCsv(files, name);
      setUploaded(res);
    } catch (e: any) {
      setUploadErr(e.message || "upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const safety = evals?.sql_safety;
  const t2s = evals?.text2sql;
  const fc = evals?.forecast;

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-28">
      <h1 className="text-3xl font-semibold tracking-tight">Connections & Catalog</h1>
      <p className="mt-2 text-ink-dim">
        The bundled read-only demo — the real Olist e-commerce warehouse (99,441 orders).
      </p>

      <div className="mt-6 flex items-center gap-3 rounded-xl border border-pos/25 bg-pos/5 px-4 py-3 text-sm">
        <ShieldCheck className="h-5 w-5 text-pos" />
        <span>
          <b>Demo — Olist e-commerce</b> · SQLite · connected read-only ·{" "}
          <span className="text-pos">writes rejected by construction</span>
        </span>
      </div>

      {/* Bring your own data */}
      <div className="mt-4 card gradient-border relative p-5">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-medium">
              <Upload className="h-5 w-5 text-indigo" /> Bring your own data
            </h2>
            <p className="mt-1 text-sm text-ink-dim">
              Upload a CSV → Nexus builds an instant read-only warehouse and you
              can ask it questions with the same safety guard. Nothing leaves your
              machine in local mode.
            </p>
          </div>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="focus-ring flex shrink-0 items-center gap-2 rounded-xl bg-ai-gradient px-4 py-2.5 text-sm font-medium text-white shadow-glow disabled:opacity-50"
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {uploading ? "Uploading…" : "Upload CSV"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.tsv,.txt"
            multiple
            className="hidden"
            onChange={(e) => onFiles(e.target.files)}
          />
        </div>
        {uploadErr && <p className="mt-3 text-sm text-neg">{uploadErr}</p>}
        {uploaded && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 rounded-xl border border-pos/25 bg-pos/5 p-4"
          >
            <p className="text-sm">
              <b>{uploaded.name}</b> is ready ·{" "}
              {uploaded.tables
                .map((t: any) => `${t.table} (${t.rows} rows)`)
                .join(", ")}
            </p>
            <Link
              href={`/app`}
              className="mt-3 inline-flex items-center gap-1.5 text-sm text-cyan hover:underline"
            >
              Ask questions about it in the workspace
              <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
        )}
      </div>

      {/* Connect an external database */}
      <div className="mt-4 card p-5">
        <h2 className="flex items-center gap-2 text-lg font-medium">
          <Plug className="h-5 w-5 text-indigo" /> Connect a database
        </h2>
        <p className="mt-1 text-sm text-ink-dim">
          Point Nexus at a <b>read-only</b> Postgres, MySQL, or BigQuery connection.
          The DSN is SSRF-screened, verified read-only, and encrypted at rest — then
          questions run against it with the same five-layer safety guard.
        </p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <input
            value={connName}
            onChange={(e) => setConnName(e.target.value)}
            placeholder="Name (e.g. Prod warehouse)"
            className="focus-ring rounded-lg border border-line bg-surface/60 px-3 py-2 text-sm sm:w-56"
          />
          <input
            value={dsn}
            onChange={(e) => setDsn(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && connect()}
            placeholder="postgresql://ro_user:••••@host:5432/db  ·  mysql://…  ·  bigquery://project/dataset"
            className="focus-ring flex-1 rounded-lg border border-line bg-surface/60 px-3 py-2 font-mono text-xs"
          />
          <button
            onClick={connect}
            disabled={connecting}
            className="focus-ring flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-ai-gradient px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {connecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}
            {connecting ? "Verifying…" : "Connect"}
          </button>
        </div>
        {connErr && <p className="mt-3 text-sm text-neg">Rejected: {connErr}</p>}
        {connResult && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 rounded-xl border border-pos/25 bg-pos/5 p-4 text-sm"
          >
            <p>
              <b>{connResult.name}</b> connected · {connResult.db_kind} ·{" "}
              <span className="text-pos">{connResult.verification}</span>
            </p>
            <p className="mt-1 text-xs text-ink-faint">
              Select it in the workspace connection picker to start asking questions.
            </p>
          </motion.div>
        )}
      </div>

      {/* Accuracy report */}
      {evals && (
        <section className="mt-8">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
            <Gauge className="h-5 w-5 text-indigo" /> How accurate is Nexus?
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Adversarial blocked" value={safety ? `${Math.round(safety.block_rate * 100)}%` : "—"} sub={safety ? `${safety.adversarial_blocked}/${safety.adversarial_total} cases` : ""} good />
            <Stat label="Data integrity" value={t2s ? `${Math.round(t2s.data_integrity_rate * 100)}%` : "—"} sub={t2s ? `${t2s.data_integrity_pass}/${t2s.total} evals` : ""} good />
            <Stat label="Generator accuracy" value={t2s ? `${Math.round(t2s.nexus_generator_execution_accuracy * 100)}%` : "—"} sub="zero-key engine" />
            <Stat label="Forecast MAPE" value={fc ? `${fc.MAPE_pct}%` : "—"} sub={fc?.method || ""} />
          </div>
        </section>
      )}

      {/* Schema explorer */}
      {schemaLoading && (
        <div className="mt-8 grid gap-3">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}
      {!schemaLoading && schemaError && (
        <div className="mt-8">
          <ErrorState message={schemaError.message} onRetry={reloadSchema} />
        </div>
      )}
      {schema && (
        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_360px]">
          <section>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
              <Table2 className="h-5 w-5 text-indigo" /> Tables ({schema.tables.length})
            </h2>
            <div className="flex flex-col gap-2">
              {schema.tables.map((t: any) => (
                <div key={t.name} className="card overflow-hidden">
                  <button
                    onClick={() => setOpen(open === t.name ? null : t.name)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left"
                  >
                    <span className="flex items-center gap-2 font-mono text-sm">
                      <Database className="h-4 w-4 text-ink-faint" />
                      {t.name}
                    </span>
                    <span className="text-xs text-ink-faint">{t.columns.length} cols</span>
                  </button>
                  {open === t.name && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      className="border-t border-line px-4 py-3"
                    >
                      <p className="mb-2 text-xs italic text-ink-faint">{t.grain}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {t.columns.map((c: any) => (
                          <span
                            key={c.name}
                            title={c.definition}
                            className="rounded-md border border-line bg-surface/60 px-2 py-0.5 font-mono text-[11px] text-ink-dim"
                          >
                            {c.name}
                            <span className="text-ink-faint"> :{c.type.toLowerCase()}</span>
                          </span>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
              <BookOpen className="h-5 w-5 text-indigo" /> Business glossary
            </h2>
            <div className="flex flex-col gap-2">
              {schema.glossary.map((g: any) => (
                <div key={g.term} className="card p-3">
                  <p className="text-sm font-medium">{g.term}</p>
                  <p className="mt-0.5 text-xs text-ink-dim">{g.definition}</p>
                  <code className="mt-1 block overflow-x-auto rounded bg-[#0E1117] px-2 py-1 font-mono text-[11px] text-cyan">
                    {g.canonical_sql}
                  </code>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function Stat({ label, value, sub, good }: { label: string; value: string; sub: string; good?: boolean }) {
  return (
    <div className="card p-4">
      <p className={`font-mono text-2xl font-semibold ${good ? "text-pos" : "gradient-text"}`}>{value}</p>
      <p className="mt-1 text-sm">{label}</p>
      <p className="text-xs text-ink-faint">{sub}</p>
    </div>
  );
}
