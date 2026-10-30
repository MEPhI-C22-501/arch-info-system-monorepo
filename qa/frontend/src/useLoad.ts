import { useCallback, useEffect, useState } from 'react';

type State<T> = { key: string; data?: T; error: unknown; pending: boolean };

// Загрузка с защитой от гонки: ответ устаревшего запроса отбрасывается. При смене deps старые
// данные не показываются, при reload остаются на экране до нового ответа.
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const key = JSON.stringify(deps);
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<State<T>>({ key, error: null, pending: true });

  useEffect(() => {
    let stale = false;
    setState((previous) => ({ ...(previous.key === key ? previous : { key, data: undefined, error: null }), pending: true }));
    load().then(
      (data) => { if (!stale) setState({ key, data, error: null, pending: false }); },
      (error) => { if (!stale) setState((previous) => ({ key, data: previous.key === key ? previous.data : undefined, error, pending: false })); },
    );
    return () => { stale = true; };
    // load замыкает те же значения, что перечислены в deps.
  }, [key, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  const setData = useCallback((data: T) => setState({ key, data, error: null, pending: false }), [key]);
  const current = state.key === key;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : null,
    loading: !current || state.pending,
    reload,
    setData,
  };
}
