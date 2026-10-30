import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router';

// Фильтры и страница списка живут в адресе: «назад» из карточки возвращает тот же список.
export function useListParams() {
  const [params, setParams] = useSearchParams();
  const values = useMemo(() => Object.fromEntries(params.entries()), [params]);
  const page = Number(params.get('page')) || 1;

  const setFilter = useCallback((name: string, value: string) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(name, value);
      else next.delete(name);
      next.delete('page');
      return next;
    }, { replace: true });
  }, [setParams]);

  const setPage = useCallback((value: number) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set('page', String(value));
      return next;
    }, { replace: true });
  }, [setParams]);

  const reset = useCallback(() => setParams(new URLSearchParams(), { replace: true }), [setParams]);
  return { values, page, setFilter, setPage, reset };
}
