import { useState } from 'react';
import { auth } from './api';
export function SavedViews({ userId, filters, apply }: { userId: string; filters: Record<string,string>; apply: (filters: Record<string,string>) => void }) {
  const key = `views:v1:${auth.settings.authority}:${userId}`;
  const [views,setViews] = useState<Record<string,Record<string,string>>>(() => {
    try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch { return {}; }
  });
  const [name,setName] = useState('');
  const [original,setOriginal] = useState('');
  const [error,setError] = useState('');
  const save = (next: typeof views) => { try { localStorage.setItem(key, JSON.stringify(next)); setViews(next); setError(''); } catch { setError('Не удалось сохранить представление'); } };
  return <div className="filters">
    <label>Представление<select value="" onChange={e => { apply(views[e.target.value]); setName(e.target.value); setOriginal(e.target.value); }}><option value="">Выбрать…</option>{Object.keys(views).map(n => <option key={n}>{n}</option>)}</select></label>
    <input aria-label="Название представления" value={name} maxLength={100} onChange={e => setName(e.target.value)} />
    <button disabled={!name.trim()} onClick={() => save({...views,[name.trim()]:filters})}>Сохранить</button>
    <button disabled={!original || !name.trim()} onClick={()=>{const next={...views};delete next[original];next[name.trim()]=filters;save(next);setOriginal(name.trim());}}>Переименовать</button>
    <button disabled={!views[name]} onClick={() => { const next={...views}; delete next[name]; save(next); }}>Удалить</button>
    {error && <p role="alert">{error}</p>}
  </div>;
}
