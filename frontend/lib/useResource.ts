"use client";
import { useCallback, useEffect, useState } from "react";

export interface Resource<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Fetch-on-mount with proper loading / error / retry state.
 *
 * Replaces the app's `getX().then(setState).catch(() => {})` pattern, which
 * swallowed failures into a permanent empty (or stuck "Loading…") screen. Here a
 * failed request surfaces `error` so the UI can show a retry affordance, and
 * `reload()` re-runs the fetcher (e.g. after a free-tier backend cold start).
 */
export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fetcher()
      .then((d) => alive && setData(d))
      .catch(
        (e) =>
          alive &&
          setError(e instanceof Error ? e : new Error(String(e ?? "request failed"))),
      )
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // fetcher is an inline closure (new each render); key off the caller's deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, error, loading, reload };
}
