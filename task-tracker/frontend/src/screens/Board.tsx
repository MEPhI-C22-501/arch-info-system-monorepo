import { useState } from 'react';
import { date, hours, json, request, typeName } from '../api';
import type { Item, Iteration, Page } from '../api';
import { can, selectName } from '../context';
import type { Context } from '../context';
import { Badge } from '../components/Badge';
import { Empty } from '../components/Empty';
import { ErrorBanner } from '../components/ErrorBanner';
import { useApiResource } from '../hooks/useApiResource';

const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');

export function Board({ context, revision, open, refresh }:
  { context: Context; revision: number; open: (id: string) => void; refresh: () => void }) {
  const [filters, setFilters] = useState({ assigneeId: '', priorityId: '', iterationId: '' });
  const [moveError, setMoveError] = useState('');

  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString();
  const { data: page, error } = useApiResource<Page<Item>>(`/work-items?pageSize=500&${query}`, revision);
  const { data: iterations } = useApiResource<Iteration[]>('/iterations', revision);
  const items = (page?.items ?? []).filter(item => ['TASK', 'BUG', 'SUBTASK'].includes(item.type));

  const move = async (id: string, statusId: string) => {
    if (!can(context, 'item.status')) return;
    try { const item = items.find(row => row.id === id); await request(`/work-items/${id}`, json('PATCH', { statusId, version: item?.version })); refresh(); }
    catch (e) { setMoveError(getError(e)); refresh(); }
  };
  const columns = context.statuses.filter(status => status.active && status.boardVisible).sort((a, b) => a.boardOrder - b.boardOrder);

  return <section className="screen-content">
    <div className="section-heading"><div><h2>Поток работы</h2><p>Перемещайте карточки между колонками</p></div></div>
    <ErrorBanner message={error || moveError} clear={() => setMoveError('')} />
    <div className="filters compact">
      <select value={filters.assigneeId} onChange={e => setFilters(v => ({ ...v, assigneeId: e.target.value }))}>
        <option value="">Все исполнители</option>{context.users.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
      </select>
      <select value={filters.priorityId} onChange={e => setFilters(v => ({ ...v, priorityId: e.target.value }))}>
        <option value="">Все приоритеты</option>{context.priorities.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select value={filters.iterationId} onChange={e => setFilters(v => ({ ...v, iterationId: e.target.value }))}>
        <option value="">Все итерации</option>{(iterations ?? []).map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
      </select>
    </div>
    {columns.length ? <div className="board">
      {columns.map((status, index) => <div className="board-column" key={status.id}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); const id = e.dataTransfer.getData('text/plain'); if (id) void move(id, status.id); }}>
        <div className="column-head"><strong>{status.name}</strong><span>{items.filter(item => item.statusId === status.id).length}</span></div>
        {items.filter(item => item.statusId === status.id).map(item => <div key={item.id} className="board-card"
          draggable={can(context, 'item.status') && can(context, 'item.update')}
          onDragStart={e => e.dataTransfer.setData('text/plain', item.id)}
          tabIndex={0}
          onKeyDown={e => { if (e.key === 'Enter') open(item.id); if (e.key === 'ArrowRight' && columns[index + 1]) void move(item.id, columns[index + 1].id); if (e.key === 'ArrowLeft' && columns[index - 1]) void move(item.id, columns[index - 1].id); }}
          onClick={() => open(item.id)}>
          <div className="card-top"><small>{typeName(item.type)} · {item.id.slice(0, 8)}</small><span>⋮</span></div>
          <strong>{item.title}</strong>
          <div className="card-bottom"><span>{selectName(context.users, item.assigneeId)}</span><Badge>{selectName(context.priorities, item.priorityId)}</Badge></div>
          <div className="card-bottom"><small>{item.dueDate ? date(item.dueDate) : 'Без срока'}</small><small className={item.remainingHours < 0 ? 'negative' : ''}>{hours(item.remainingHours)}</small></div>
        </div>)}
      </div>)}
    </div> : <Empty text="Активных колонок пока нет" />}
  </section>;
}
