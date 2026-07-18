"use client";
import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

/** Route-level error boundary — replaces the white-screen a render error used to
 *  cause. `reset()` re-renders the segment; a link home is the escape hatch. */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surfaced in the browser console for debugging; not swallowed.
    console.error("Route error:", error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-center justify-center px-4 pt-28 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-neg/10">
        <AlertTriangle className="h-7 w-7 text-neg" />
      </div>
      <h1 className="mt-5 text-2xl font-semibold tracking-tight">
        Something went wrong
      </h1>
      <p className="mt-2 text-ink-dim">
        An unexpected error interrupted this page. You can retry, or head back to
        the workspace.
      </p>
      {error?.message && (
        <pre className="mt-4 max-w-full overflow-x-auto rounded-lg border border-line bg-surface/60 px-3 py-2 text-left text-xs text-ink-faint">
          {error.message}
        </pre>
      )}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <button
          onClick={reset}
          className="focus-ring inline-flex items-center gap-2 rounded-lg bg-ai-gradient px-4 py-2 text-sm font-medium text-white"
        >
          <RefreshCw className="h-4 w-4" /> Try again
        </button>
        <Link
          href="/app"
          className="focus-ring inline-flex items-center gap-2 rounded-lg border border-line px-4 py-2 text-sm text-ink-dim hover:text-ink"
        >
          <Home className="h-4 w-4" /> Workspace
        </Link>
      </div>
    </main>
  );
}
