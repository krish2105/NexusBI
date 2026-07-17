"use client";
import { useEffect, useRef, useState } from "react";
import { Database, Loader2, Upload } from "lucide-react";
import { getConnections, uploadCsv } from "@/lib/api";

export default function ConnectionPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  const [conns, setConns] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = () =>
    getConnections()
      .then(setConns)
      .catch(() => {});
  useEffect(() => {
    refresh();
  }, []);

  const onFiles = async (files: FileList | null) => {
    if (!files || !files.length) return;
    setBusy(true);
    setErr(null);
    try {
      const name = files[0].name.replace(/\.[^.]+$/, "");
      const res = await uploadCsv(files, name);
      await refresh();
      onChange(res.connection_id);
    } catch (e: any) {
      setErr(e.message || "upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div className="glass flex flex-1 items-center gap-2 rounded-xl px-3 py-2">
          <Database className="h-4 w-4 shrink-0 text-indigo" />
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="focus-ring w-full cursor-pointer bg-transparent text-sm text-ink focus:outline-none"
            aria-label="Choose dataset"
          >
            {conns.map((c) => (
              <option key={c.id} value={c.id} className="bg-surface">
                {c.name}
                {c.bundled ? " · demo" : ""}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="focus-ring flex items-center gap-1.5 rounded-xl border border-line bg-surface/60 px-3 py-2 text-sm text-ink-dim hover:border-indigo/40 hover:text-ink disabled:opacity-50"
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Upload className="h-4 w-4" />
          )}
          {busy ? "Uploading…" : "Upload CSV"}
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
      {err && <p className="text-xs text-neg">{err}</p>}
    </div>
  );
}
