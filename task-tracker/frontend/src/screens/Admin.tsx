import { useEffect, useState } from 'react';
import { dateTime, json, request, typeName } from '../api';
import type { Json } from '../api';
import { can } from '../context';
import type { Context } from '../context';
import { Badge } from '../components/Badge';
import { Empty } from '../components/Empty';
import { ErrorBanner } from '../components/ErrorBanner';

const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');
type Section = 'statuses' | 'priorities' | 'types' | 'access' | 'directory';
const SECTION_PERMISSION: Record<Section, string> = { statuses: 'status.admin', priorities: 'priority.admin', types: 'type.admin', access: 'access.admin', directory: 'directory.admin' };
const ALL_SECTIONS = Object.keys(SECTION_PERMISSION) as Section[];

export function Admin({ context, refreshAll }: { context: Context; refreshAll: () => void }) {
  const [requestedSection, setRequestedSection] = useState<Section>('statuses');
  // derived, not synced via an effect: a permission revoked at runtime falls back to the first
  // section the current role can still see, without a setState-in-effect round-trip.
  const section = can(context, SECTION_PERMISSION[requestedSection]) ? requestedSection : (ALL_SECTIONS.find(key => can(context, SECTION_PERMISSION[key])) ?? requestedSection);

  const [accessRows, setAccessRows] = useState<Array<Json>>([]);
  const [permissions, setPermissions] = useState<Array<Json>>([]);
  const [directory, setDirectory] = useState<Json>({});
  const [error, setError] = useState('');
  const [newStatusName, setNewStatusName] = useState<string | null>(null);
  const [newPriorityName, setNewPriorityName] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      can(context, 'access.admin') ? request<Array<Json>>('/admin/access') : Promise.resolve([]),
      can(context, 'access.admin') ? request<Array<Json>>('/admin/permissions') : Promise.resolve([]),
      can(context, 'directory.admin') ? request<Json>('/admin/directory') : Promise.resolve({}),
    ]).then(([a, p, d]) => { if (active) { setAccessRows(a); setPermissions(p); setDirectory(d); } })
      .catch(e => { if (active) setError(getError(e)); });
    return () => { active = false; };
  }, [context, reloadToken]);

  const action = async (path: string, init: RequestInit) => {
    try { await request(path, init); setReloadToken(v => v + 1); refreshAll(); }
    catch (e) { setError(getError(e)); }
  };

  return <section className="screen-content">
    <div className="section-heading"><div><h2>Настройки процесса</h2><p>Статусы, приоритеты, доступ и справочник организации</p></div></div>
    <ErrorBanner message={error} clear={() => setError('')} />
    <div className="tabs admin-tabs">
      {ALL_SECTIONS.filter(key => can(context, SECTION_PERMISSION[key])).map(key =>
        <button key={key} className={section === key ? 'active' : ''} onClick={() => setRequestedSection(key)}>
          {{ statuses: 'Статусы', priorities: 'Приоритеты', types: 'Типы', access: 'Права', directory: 'Справочник' }[key]}
        </button>)}
    </div>

    {section === 'statuses' && <div className="panel">
      <div className="mini-head"><h3>Колонки доски</h3><button className="button secondary" onClick={() => setNewStatusName('')}>＋ Статус</button></div>
      <div className="settings-list">{context.statuses.map(row => <div className="setting-row" key={row.id}>
        <input aria-label="Название" defaultValue={row.name} onBlur={e => { if (e.target.value !== row.name) void action(`/admin/statuses/${row.id}`, json('PATCH', { name: e.target.value })); }} />
        <input aria-label="Порядок" type="number" className="small-input" defaultValue={row.boardOrder} onBlur={e => { if (Number(e.target.value) !== row.boardOrder) void action(`/admin/statuses/${row.id}`, json('PATCH', { boardOrder: Number(e.target.value) })); }} />
        <select aria-label="Категория" value={row.category} onChange={e => void action(`/admin/statuses/${row.id}`, json('PATCH', { category: e.target.value }))}>
          <option value="OPEN">В работе</option><option value="COMPLETED">Завершение</option><option value="ARCHIVED">Архив</option>
        </select>
        <label><input type="checkbox" checked={row.boardVisible} onChange={e => void action(`/admin/statuses/${row.id}`, json('PATCH', { boardVisible: e.target.checked }))} /> На доске</label>
        <label><input type="checkbox" checked={row.active} onChange={e => void action(`/admin/statuses/${row.id}`, json('PATCH', { active: e.target.checked }))} /> Активен</label>
      </div>)}</div>
    </div>}

    {section === 'priorities' && <div className="panel">
      <div className="mini-head"><h3>Приоритеты</h3><button className="button secondary" onClick={() => setNewPriorityName('')}>＋ Приоритет</button></div>
      <div className="settings-list">{context.priorities.map(row => <div className="setting-row" key={row.id}>
        <input aria-label="Название" defaultValue={row.name} onBlur={e => { if (e.target.value !== row.name) void action(`/admin/priorities/${row.id}`, json('PATCH', { name: e.target.value })); }} />
        <input aria-label="Порядок" className="small-input" type="number" defaultValue={row.sortOrder} onBlur={e => { if (Number(e.target.value) !== row.sortOrder) void action(`/admin/priorities/${row.id}`, json('PATCH', { sortOrder: Number(e.target.value) })); }} />
        <Badge>{row.code || 'Пользовательский'}</Badge>
        <label><input type="checkbox" checked={row.active} onChange={e => void action(`/admin/priorities/${row.id}`, json('PATCH', { active: e.target.checked }))} /> Активен</label>
      </div>)}</div>
    </div>}

    {section === 'types' && <div className="panel"><h3>Доступность типов</h3><div className="settings-list">
      {context.types.map(row => <div className="setting-row" key={row.type}>
        <strong>{typeName(row.type)}</strong>
        <label><input type="checkbox" checked={row.enabled} onChange={e => void action(`/admin/types/${row.type}`, json('PATCH', { enabled: e.target.checked }))} /> Доступен для создания</label>
      </div>)}
    </div></div>}

    {section === 'access' && <div className="panel">
      <h3>Локальный допуск</h3>
      <div className="settings-list">{context.users.map(user => {
        const row = accessRows.find(entry => entry.userId === user.id);
        return <div className="setting-row" key={user.id}>
          <strong>{user.name}</strong>
          <select aria-label={`Роль ${user.name}`} value={String(row?.role || 'MEMBER')} onChange={e => void action(`/admin/access/${user.id}`, json('PUT', { role: e.target.value, allowed: row?.allowed ?? true }))}>
            <option value="MEMBER">Участник</option><option value="LEAD">Руководитель</option><option value="ADMIN">Администратор</option>
          </select>
          <label><input type="checkbox" checked={Boolean(row?.allowed)} onChange={e => void action(`/admin/access/${user.id}`, json('PUT', { role: row?.role || 'MEMBER', allowed: e.target.checked }))} /> Допущен</label>
        </div>;
      })}</div>
      <h3>Разрешения ролей</h3>
      <div className="permission-grid">{permissions.map(row => <label key={`${row.role}:${row.permission}`}>
        <input type="checkbox" checked={Boolean(row.allowed)} onChange={e => void action(`/admin/permissions/${row.role}/${row.permission}`, json('PUT', { allowed: e.target.checked }))} />
        <span>{String(row.role)} · {String(row.permission)}</span>
      </label>)}</div>
    </div>}

    {section === 'directory' && <div className="panel">
      <div className="mini-head">
        <div><h3>Синхронизация справочника</h3><p>Последний успех: {dateTime(directory.lastSuccessAt)}</p><p>Версия: {String(directory.version || '—')}</p></div>
        <button className="button primary" onClick={() => void action('/admin/directory/sync', { method: 'POST' })}>Синхронизировать</button>
      </div>
      <h4>Журнал</h4>
      <div className="stack">{Array.isArray(directory.logs) && directory.logs.length
        ? (directory.logs as Array<Json>).map(row => <div className="activity" key={String(row.id)}>
            <Badge tone={row.success ? 'green' : 'red'}>{row.success ? 'Успех' : 'Ошибка'}</Badge> {dateTime(row.occurredAt)} · {String(row.message)} · {String(row.durationMs)} мс
          </div>)
        : <Empty text="Запусков синхронизации пока нет" />}</div>
    </div>}

    {newStatusName !== null && <NamePrompt title="Новый статус" value={newStatusName} onChange={setNewStatusName}
      onCancel={() => setNewStatusName(null)}
      onSubmit={name => { setNewStatusName(null); void action('/admin/statuses', json('POST', { name, boardOrder: context.statuses.length + 1, category: 'OPEN', boardVisible: true })); }} />}
    {newPriorityName !== null && <NamePrompt title="Новый приоритет" value={newPriorityName} onChange={setNewPriorityName}
      onCancel={() => setNewPriorityName(null)}
      onSubmit={name => { setNewPriorityName(null); void action('/admin/priorities', json('POST', { name, sortOrder: context.priorities.length + 1 })); }} />}
  </section>;
}

/** Replaces the old `prompt()` calls — same single text field, but in the dialog style the rest of the app uses. */
function NamePrompt({ title, value, onChange, onCancel, onSubmit }:
  { title: string; value: string; onChange: (value: string) => void; onCancel: () => void; onSubmit: (value: string) => void }) {
  return <div className="overlay" onMouseDown={onCancel}>
    <div className="small-dialog" role="dialog" aria-modal="true" aria-label={title} onMouseDown={e => e.stopPropagation()}>
      <div className="dialog-title"><h2>{title}</h2><button onClick={onCancel} aria-label="Закрыть">×</button></div>
      <form onSubmit={e => { e.preventDefault(); if (value.trim()) onSubmit(value.trim()); }} className="form-grid">
        <label className="span-2">Название<input autoFocus required value={value} onChange={e => onChange(e.target.value)} /></label>
        <div className="dialog-actions span-2">
          <button type="button" className="button secondary" onClick={onCancel}>Отмена</button>
          <button className="button primary" type="submit">Создать</button>
        </div>
      </form>
    </div>
  </div>;
}
