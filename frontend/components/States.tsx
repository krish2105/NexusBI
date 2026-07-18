"use client";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";

/** Shimmering placeholder block (uses the `shimmer` animation from tailwind.config). */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`relative overflow-hidden rounded-lg bg-surface-2 ${className}`}
      aria-hidden
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3 p-4">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-4/5" />
    </div>
  );
}

/** Full-page skeleton — header + a grid of cards. Used by route `loading.tsx`
 *  and page-level loading. */
export function PageLoading() {
  return (
    <main
      className="mx-auto max-w-6xl px-4 pb-20 pt-28"
      aria-busy="true"
      aria-label="Loading"
    >
      <Skeleton className="h-8 w-64" />
      <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    </main>
  );
}

/** Failure state with a retry affordance — the honest replacement for a silent
 *  empty screen. The default copy nods to free-tier cold starts. */
export function ErrorState({
  message,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="card flex flex-col items-center gap-3 p-8 text-center"
    >
      <div className="grid h-11 w-11 place-items-center rounded-full bg-neg/10">
        <AlertTriangle className="h-5 w-5 text-neg" />
      </div>
      <div>
        <p className="font-medium">Couldn&apos;t load this</p>
        <p className="mx-auto mt-1 max-w-sm text-sm text-ink-dim">
          {message ||
            "The request failed. The backend may be waking up (free-tier cold start can take ~30s) — give it a moment and retry."}
        </p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="focus-ring mt-1 inline-flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm text-ink-dim transition-colors hover:text-ink"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  hint,
  action,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line px-6 py-10 text-center">
      <Icon className="h-6 w-6 text-ink-faint" />
      <p className="text-sm font-medium text-ink-dim">{title}</p>
      {hint && <p className="max-w-sm text-xs text-ink-faint">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden />;
}
