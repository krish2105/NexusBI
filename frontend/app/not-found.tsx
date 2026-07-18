import Link from "next/link";
import { Compass, Home } from "lucide-react";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-center justify-center px-4 pt-28 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-surface-2">
        <Compass className="h-7 w-7 text-ink-dim" />
      </div>
      <p className="mt-5 font-mono text-sm text-ink-faint">404</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-2 text-ink-dim">
        That route doesn&apos;t exist. Try the workspace to ask your data a question.
      </p>
      <Link
        href="/app"
        className="focus-ring mt-6 inline-flex items-center gap-2 rounded-lg bg-ai-gradient px-4 py-2 text-sm font-medium text-white"
      >
        <Home className="h-4 w-4" /> Go to workspace
      </Link>
    </main>
  );
}
