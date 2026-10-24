import { useEffect, useState } from 'react';
import { request, typeName } from '../api';
import type { Item } from '../api';

/**
 * Search-by-title picker — replaces the raw-UUID text inputs that used to sit on "Родительский
 * ID" / "add item to iteration". Falls back to showing the bare id if the item can't be loaded
 * (e.g. a stale/typo'd value) so it never silently hides what's actually stored.
 */
export function WorkItemPicker({ value, onChange, placeholder, excludeId }:
  { value: string; onChange: (id: string) => void; placeholder?: string; excludeId?: string }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<Item[]>([]);
  const [selectedTitle, setSelectedTitle] = useState('');

  useEffect(() => {
    // no setState for the "!value" case — the render below only shows selectedTitle when value
    // is truthy, so a stale title left over from a previous value is never actually displayed.
    if (!value) return;
    let active = true;
    request<Item>(`/work-items/${value}`)
      .then(item => { if (active) setSelectedTitle(item.title); })
      .catch(() => { if (active) setSelectedTitle(''); });
    return () => { active = false; };
  }, [value]);

  useEffect(() => {
    // same idea: "too short to search" is handled by visibleOptions below, not by clearing state here.
    if (!open || query.trim().length < 2) return;
    let active = true;
    const handle = setTimeout(() => {
      request<{ items: Item[] }>(`/work-items?search=${encodeURIComponent(query)}&pageSize=8`)
        .then(page => { if (active) setOptions(page.items.filter(item => item.id !== excludeId)); })
        .catch(() => { if (active) setOptions([]); });
    }, 250);
    return () => { active = false; clearTimeout(handle); };
  }, [query, open, excludeId]);
  const visibleOptions = query.trim().length >= 2 ? options : [];

  const pick = (item: Item) => { onChange(item.id); setSelectedTitle(item.title); setQuery(''); setOpen(false); };
  const clear = () => { onChange(''); setSelectedTitle(''); setQuery(''); };

  return <div className="picker">
    {value && !open
      ? <div className="picker-selected" onClick={() => setOpen(true)}>
          <span>{selectedTitle || `${value.slice(0, 8)}…`}</span>
          <button type="button" aria-label="Очистить" onClick={e => { e.stopPropagation(); clear(); }}>×</button>
        </div>
      : <input placeholder={placeholder} value={query} onFocus={() => setOpen(true)}
          onChange={e => setQuery(e.target.value)} onBlur={() => setTimeout(() => setOpen(false), 150)} />}
    {open && visibleOptions.length > 0 && <ul className="picker-options">
      {visibleOptions.map(item => <li key={item.id}>
        <button type="button" onMouseDown={() => pick(item)}>{typeName(item.type)} · {item.title}</button>
      </li>)}
    </ul>}
  </div>;
}
