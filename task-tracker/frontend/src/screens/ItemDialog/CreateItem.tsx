import React, { useState } from 'react';
import { json, request, typeName } from '../../api';
import type { Item } from '../../api';
import { ErrorBanner } from '../../components/ErrorBanner';
import { WorkItemPicker } from '../../components/WorkItemPicker';
import type { Context } from '../../context';

const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');

export function CreateItem({ context, close, created, parentId, suggestedType }:
  { context: Context; close: () => void; created: (id: string) => void; parentId?: string; suggestedType?: string }) {
  const [form, setForm] = useState({
    type: suggestedType || 'TASK', title: '', description: '',
    priorityId: context.priorities.find(p => p.active && p.code === 'medium')?.id || '',
    assigneeId: '', startDate: '', dueDate: '', plannedHours: '', parentId: parentId || '',
  });
  const [error, setError] = useState('');
  const set = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const body = { ...form, assigneeId: form.assigneeId || null, parentId: form.parentId || null,
        plannedHours: form.plannedHours || null, startDate: form.startDate || null, dueDate: form.dueDate || null };
      const item = await request<Item>('/work-items', json('POST', body));
      created(item.id);
    } catch (e) { setError(getError(e)); }
  };
  return <div className="overlay" onMouseDown={close}>
    <div className="small-dialog" role="dialog" aria-modal="true" aria-label="Новый рабочий элемент" onMouseDown={e => e.stopPropagation()}>
      <div className="dialog-title"><h2>Новый рабочий элемент</h2><button onClick={close} aria-label="Закрыть">×</button></div>
      <form onSubmit={e => void save(e)} className="form-grid">
        <ErrorBanner message={error} />
        <label>Тип<select value={form.type} onChange={e => set('type', e.target.value)} disabled={Boolean(parentId && suggestedType)}>
          {context.types.filter(row => row.enabled).map(row => <option key={row.type} value={row.type}>{typeName(row.type)}</option>)}
        </select></label>
        <label>Название<input required value={form.title} onChange={e => set('title', e.target.value)} /></label>
        <label className="span-2">Описание<textarea rows={3} value={form.description} onChange={e => set('description', e.target.value)} /></label>
        <label>Приоритет<select value={form.priorityId} onChange={e => set('priorityId', e.target.value)}>
          {context.priorities.filter(row => row.active).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select></label>
        <label>Исполнитель<select value={form.assigneeId} onChange={e => set('assigneeId', e.target.value)}>
          <option value="">Не назначен</option>
          {context.users.filter(row => row.active).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select></label>
        <label>Начало<input type="date" value={form.startDate} onChange={e => set('startDate', e.target.value)} /></label>
        <label>Срок<input type="date" value={form.dueDate} onChange={e => set('dueDate', e.target.value)} /></label>
        <label>План, ч<input type="number" min="0" step="0.01" value={form.plannedHours} onChange={e => set('plannedHours', e.target.value)} /></label>
        <label>Родительский элемент
          <WorkItemPicker value={form.parentId} onChange={id => set('parentId', id)} placeholder="Начните вводить название…" />
        </label>
        <div className="dialog-actions span-2">
          <button type="button" className="button secondary" onClick={close}>Отмена</button>
          <button className="button primary" type="submit">Создать</button>
        </div>
      </form>
    </div>
  </div>;
}
