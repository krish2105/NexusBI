"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export interface Resource<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  /** True once a request has been pending longer than SLOW_MS — the free-tier
   *  backend spins down on inactivity and can take ~30-50s to wake. */
  slow: boolean;
  reload: () => void;
}

const SLOW_MS = 4000;
// Comfortably above Render's documented free-tier cold-start ceiling (~50s),
// so this only fires on a genuinely stuck request, not a normal wake-up.
const TIMEOUT_MS = 70_000;

function timeout(ms: number): Promise<never> {
  return new Promise((_, reject) =>
    setTimeout(
      () => reject(new Error("Request timed out — the backend may be unreachable.")),
      ms,
    ),
  );
}

/**
 * Fetch-on-mount with proper loading / error / retry / slow-request state.
 *
 * Replaces the app's `getX().then(setState).catch(() => {})` pattern, which
 * swallowed failures into a permanent empty (or stuck "Loading…") screen. Here a
 * failed request surfaces `error` so the UI can show a retry affordance,
 * `reload()` re-runs the fetcher (e.g. after a free-tier backend cold start),
 * and `slow` lets the UI explain a long wait instead of looking frozen.
 */
export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [nonce, setNonce] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setSlow(false);

    const slowTimer = setTimeout(() => alive && setSlow(true), SLOW_MS);

    Promise.race([fetcherRef.current(), timeout(TIMEOUT_MS)])
      .then((d) => alive && setData(d as T))
      .catch(
        (e) =>
          alive &&
          setError(e instanceof Error ? e : new Error(String(e ?? "request failed"))),
      )
      .finally(() => {
        clearTimeout(slowTimer);
        if (alive) {
          setLoading(false);
          setSlow(false);
        }
      });
    return () => {
      alive = false;
      clearTimeout(slowTimer);
    };
    // fetcher is an inline closure (new each render); key off the caller's deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, error, loading, slow, reload };
}
