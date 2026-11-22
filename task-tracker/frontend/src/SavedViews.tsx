import { useState } from 'react';
import { auth } from './api';

type Filters = Record<string, string>;

export function SavedViews({ userId, filters, apply }: {
  userId: string;
  filters: Filters;
  apply: (filters: Filters) => void;
}) {
  const key = `views:v1:${auth.settings.authority}:${userId}`;
  const [views, setViews] = useState<Record<string, Filters>>(() => {
    try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch { return {}; }
  });
  const [name, setName] = useState('');
  const [original, setOriginal] = useState('');
  const [error, setError] = useState('');
  const title = name.trim();
  const saved = views[original];
  const applied = saved && Object.entries(filters).every(([field, value]) =>
    value === (saved[field] ?? (field === 'sort' ? 'dueDate' : '')));

  const save = (next: typeof views) => {
    try {
      localStorage.setItem(key, JSON.stringify(next));
      setViews(next);
      setError('');
      return true;
    } catch {
      setError('Не удалось сохранить представление');
      return false;
    }
  };
  const select = (selected: string) => {
    if (selected) apply(views[selected]);
    setName(selected);
    setOriginal(selected);
  };
  const rename = () => {
    const next = { ...views, [title]: saved };
    delete next[original];
    if (save(next)) {
      setOriginal(title);
      setName(title);
    }
  };
  const remove = () => {
    const next = { ...views };
    delete next[title];
    if (save(next)) {
      if (original === title) setOriginal('');
      setName('');
    }
  };

  return <div className="filters saved-views">
    <label className="saved-views-picker">Представление
      <select value={applied ? original : ''} onChange={e => select(e.target.value)}>
        <option value="">Выбрать…</option>
        {Object.keys(views).map(view => <option key={view}>{view}</option>)}
      </select>
    </label>
    <input aria-label="Название представления" value={name} maxLength={100} onChange={e => setName(e.target.value)} />
    <button className="button secondary" disabled={!title} onClick={() => {
      if (save({ ...views, [title]: filters })) {
        setOriginal(title);
        setName(title);
      }
    }}>Сохранить</button>
    <button className="button secondary" disabled={!saved || !title || title === original || Object.hasOwn(views, title)}
      onClick={rename}>Переименовать</button>
    <button className="button danger" disabled={!Object.hasOwn(views, title)} onClick={remove}>Удалить</button>
    {error && <p role="alert">{error}</p>}
  </div>;
}
