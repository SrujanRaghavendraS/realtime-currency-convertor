import { useCallback, useEffect } from 'react';
import { getHistory } from '../services/api.js';
import { usePolling } from './usePolling.js';

export const HISTORY_POLL_MS = 60000;

// Sliding-window history for one pair. Data from a previously selected pair is hidden
// until the new pair's response arrives.
export function useHistory(pair) {
  const fetcher = useCallback(() => getHistory(pair), [pair]);
  const state = usePolling(fetcher, HISTORY_POLL_MS);
  const { refresh } = state;
  useEffect(() => {
    refresh(true);
  }, [pair, refresh]);
  const data = state.data && state.data.pair === pair ? state.data : null;
  return { ...state, data, loading: state.loading || (!data && !state.error) };
}
