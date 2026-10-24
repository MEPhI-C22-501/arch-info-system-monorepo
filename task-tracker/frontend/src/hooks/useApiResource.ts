import { useEffect, useState } from 'react';
import { request } from '../api';

const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');

/**
 * Fetches `path` whenever `path` or `revision` changes. `loading` is derived (`data === null`),
 * not a separate `setLoading(true)` call inside the effect — that's deliberate: it's what lets
 * this satisfy react-hooks/set-state-in-effect, and as a side effect it means a revision bump or
 * filter change keeps showing the previous page instead of flashing a loading state (stale data
 * stays visible until the new page arrives). Pass `path: null` to skip fetching entirely.
 */
export function useApiResource<T>(path: string | null, revision: string | number = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (path === null) return;
    let active = true;
    request<T>(path)
      .then(result => { if (active) { setData(result); setError(''); } })
      .catch(e => { if (active) setError(getError(e)); });
    return () => { active = false; };
  }, [path, revision]);

  return { data, loading: data === null && error === '', error, setError } as const;
}
