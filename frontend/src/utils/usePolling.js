import { useCallback, useEffect, useRef, useState } from 'react';

// Polls `fetcher` every `intervalMs`. Keeps the last good data when a poll fails,
// so the UI can show stale values alongside an error instead of blanking out.
export function usePolling(fetcher, intervalMs) {
  const [state, setState] = useState({ data: null, error: null, loading: true, updatedAt: null });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const inFlight = useRef(false);
  const mounted = useRef(true);

  const seq = useRef(0);

  // `force` starts a new request even if one is in flight; only the newest response is applied.
  const refresh = useCallback(async (force = false) => {
    if (inFlight.current && force !== true) return;
    inFlight.current = true;
    const mine = ++seq.current;
    try {
      const data = await fetcherRef.current();
      if (mounted.current && mine === seq.current) {
        setState({ data, error: null, loading: false, updatedAt: Date.now() });
      }
    } catch (error) {
      if (mounted.current && mine === seq.current) setState((s) => ({ ...s, error, loading: false }));
    } finally {
      if (mine === seq.current) inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  // Inject a fresh payload (e.g. a POST response that has the same shape as the polled GET).
  const setData = useCallback((data) => {
    setState({ data, error: null, loading: false, updatedAt: Date.now() });
  }, []);

  return { ...state, refresh, setData };
}
