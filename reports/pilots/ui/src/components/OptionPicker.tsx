import { useId, useState } from 'react';
import { api, errorMessage } from '../api';
import { useSession } from '../session';
import type { DimensionOption } from '../types';
import { useLoad } from '../useLoad';

/** Filter by names: the values the user's scope holds for the period (POST options); ids from a link stay selectable. */
export function OptionPicker({ reportId, slice, title, periodFrom, periodTo, selected, onChange }: {
  reportId: string; slice: string; title: string; periodFrom: string; periodTo: string;
  selected: string[]; onChange: (ids: string[]) => void;
}) {
  const { token } = useSession();
  const [search, setSearch] = useState('');
  const searchId = useId();
  const validPeriod = Boolean(periodFrom && periodTo && periodFrom <= periodTo);
  const options = useLoad(
    () => (validPeriod
      ? api<{ items: DimensionOption[] }>(token, `reports/${reportId}/options`, 'POST', { params: { periodFrom, periodTo }, slice: [slice] })
      : Promise.resolve({ items: [] })),
    [token, reportId, slice, periodFrom, periodTo, validPeriod],
  );
  const known = options.data?.items ?? [];
  const extra = selected.filter((id) => !known.some((o) => o.id === id)).map((id) => ({ id, label: id }));
  const all = [...known, ...extra];
  const needle = search.trim().toLowerCase();
  const shown = needle ? all.filter((o) => o.label.toLowerCase().includes(needle) || selected.includes(o.id)) : all;
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);

  return (
    <fieldset className="options">
      <legend>{title}{selected.length ? ` (выбрано: ${selected.length})` : ''}</legend>
      {options.loading && !options.data ? <p className="muted">Загружаем список…</p>
        : options.error ? <p className="field-error">Список недоступен: {errorMessage(options.error)}</p>
        : !all.length ? <p className="muted">За период значений нет.</p>
        : (
          <>
            {all.length > 8 && (
              <label htmlFor={searchId} className="options-search">Найти
                <input id={searchId} type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
              </label>
            )}
            <ul className="options-list">
              {shown.map((o) => (
                <li key={o.id}>
                  <label className="checkbox"><input type="checkbox" checked={selected.includes(o.id)} onChange={() => toggle(o.id)} />{o.label}</label>
                </li>
              ))}
            </ul>
          </>
        )}
      {selected.length > 0 && <button type="button" className="link-button" onClick={() => onChange([])}>Сбросить</button>}
    </fieldset>
  );
}
