import { useCallback, useEffect, useState } from 'react';

export interface Loaded<T> { data: T | null; error: unknown; loading: boolean; reload: () => void }

/** Runs a request when its dependencies change; a newer request wins over an older one. */
export function useLoad<T>(request: () => Promise<T>, deps: unknown[]): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; error: unknown; loading: boolean }>({ data: null, error: null, loading: true });
  const [attempt, setAttempt] = useState(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(request, deps);
  useEffect(() => {
    let current = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    run().then(
      (data) => current && setState({ data, error: null, loading: false }),
      (error) => current && setState({ data: null, error, loading: false }),
    );
    return () => { current = false; };
  }, [run, attempt]);
  return { ...state, reload: () => setAttempt((n) => n + 1) };
}
