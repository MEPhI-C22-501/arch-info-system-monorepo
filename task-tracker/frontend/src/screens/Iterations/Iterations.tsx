import { useState } from 'react';
import type React from 'react';
import { date, hours, json, request, typeName } from '../../api';
import type { Iteration } from '../../api';
import { can, selectName } from '../../context';
import type { Context } from '../../context';
import { Badge } from '../../components/Badge';
import { Empty } from '../../components/Empty';
import { ErrorBanner } from '../../components/ErrorBanner';
import { WorkItemPicker } from '../../components/WorkItemPicker';
import { useApiResource } from '../../hooks/useApiResource';
import { PlanFact } from './PlanFact';

const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');

export function Iterations({ context, revision, open, refresh }:
  { context: Context; revision: number; open: (id: string) => void; refresh: () => void }) {
  const [selected, setSelected] = useState('');
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState(''); const [start, setStart] = useState(''); const [end, setEnd] = useState('');
  const [newItemId, setNewItemId] = useState('');
  const [capacityUser, setCapacityUser] = useState(''); const [capacityHours, setCapacityHours] = useState('');
  const [actionError, setActionError] = useState('');
  const [localRevision, setLocalRevision] = useState(0);
  const combinedRevision = `${revision}:${localRevision}`;

  const { data: list, error: listError } = useApiResource<Iteration[]>('/iterations', combinedRevision);
  const effectiveSelected = selected || list?.[0]?.id || '';
  const { data: iteration, error: detailError } = useApiResource<Iteration>(effectiveSelected ? `/iterations/${effectiveSelected}` : null, combinedRevision);

  const action = async (path: string, init: RequestInit) => {
    try { await request(path, init); setLocalRevision(v => v + 1); refresh(); }
    catch (e) { setActionError(getError(e)); }
  };
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const row = await request<Iteration>('/iterations', json('POST', { name, startDate: start, endDate: end, description: '' }));
      setCreating(false); setSelected(row.id); setLocalRevision(v => v + 1); refresh();
    } catch (e) { setActionError(getError(e)); }
  };
  const canEdit = can(context, 'iteration.write') && iteration?.state !== 'COMPLETED';
  const baseline = iteration?.baseline || {}; const result = iteration?.result || {};

  return <section className="screen-content">
    <div className="section-heading">
      <div><h2>Планирование итераций</h2><p>Ёмкость команды, состав и план-факт</p></div>
      {can(context, 'iteration.write') && <button className="button primary" onClick={() => setCreating(true)}>＋ Новая итерация</button>}
    </div>
    <ErrorBanner message={listError || detailError || actionError} clear={() => setActionError('')} />
    <div className="iteration-layout">
      <div className="panel iteration-list"><h3>Итерации</h3>
        {list?.length ? list.map(row => <button key={row.id} className={`iteration-link ${effectiveSelected === row.id ? 'active' : ''}`} onClick={() => setSelected(row.id)}>
          <strong>{row.name}</strong><small>{date(row.startDate)} — {date(row.endDate)}</small><Badge tone={row.state === 'COMPLETED' ? 'green' : ''}>{row.state}</Badge>
        </button>) : <Empty text="Итераций пока нет" />}
      </div>
      <div className="iteration-detail">{iteration ? <>
        <div className="panel iteration-hero">
          <div className="section-heading">
            <div><span className="eyebrow">{iteration.state}</span><h2>{iteration.name}</h2><p>{date(iteration.startDate)} — {date(iteration.endDate)}</p></div>
            {can(context, 'iteration.write') && <div className="actions">
              {iteration.state === 'PLANNED' && <button className="button primary" onClick={() => void action(`/iterations/${iteration.id}/activate`, { method: 'POST' })}>Запустить</button>}
              {iteration.state === 'ACTIVE' && <button className="button primary" onClick={() => void action(`/iterations/${iteration.id}/complete`, { method: 'POST' })}>Завершить</button>}
            </div>}
          </div>
          <div className="metric-grid">
            <div><small>План</small><strong>{hours(iteration.plannedHours)}</strong></div>
            <div><small>Факт</small><strong>{hours(iteration.actualHours)}</strong></div>
            <div><small>Остаток</small><strong className={iteration.remainingHours < 0 ? 'negative' : ''}>{hours(iteration.remainingHours)}</strong></div>
            <div><small>Готово</small><strong>{Math.round(iteration.completionFraction * 100)}%</strong></div>
          </div>
        </div>
        {iteration.warnings.length > 0 && <div className="warning-panel"><strong>Обратите внимание перед запуском</strong>{iteration.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</div>}
        <div className="panel">
          <div className="mini-head"><h3>Загрузка участников</h3><span>Резерв команды: <strong className={iteration.teamReserveHours < 0 ? 'negative' : ''}>{hours(iteration.teamReserveHours)}</strong></span></div>
          {iteration.capacity.length ? <div className="capacity-list">{iteration.capacity.map(entry => <div key={entry.userId} className="capacity-row">
            <strong>{selectName(context.users, entry.userId)}</strong>
            <div className="capacity-track"><span style={{ width: `${Math.min(100, entry.availableHours ? entry.plannedHours / entry.availableHours * 100 : 100)}%` }} className={entry.overloaded ? 'overload' : ''} /></div>
            <small className={entry.overloaded ? 'negative' : ''}>{hours(entry.plannedHours)} / {hours(entry.availableHours)} · резерв {hours(entry.reserveHours)}</small>
          </div>)}</div> : <Empty text="Ёмкость пока не задана" />}
          {canEdit && <div className="composer row">
            <select aria-label="Участник" value={capacityUser} onChange={e => setCapacityUser(e.target.value)}>
              <option value="">Участник</option>{context.users.filter(u => u.active).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
            <input aria-label="Доступные часы" type="number" min="0" step="0.01" placeholder="Доступные часы" value={capacityHours} onChange={e => setCapacityHours(e.target.value)} />
            <button className="button secondary" onClick={() => { if (capacityUser) void action(`/iterations/${iteration.id}/capacity`, json('PUT', { userId: capacityUser, availableHours: capacityHours })); }}>Сохранить ёмкость</button>
          </div>}
        </div>
        <div className="panel">
          <div className="mini-head"><h3>Состав итерации</h3><span>{iteration.items.length} элементов</span></div>
          {iteration.items.length ? <div className="stack">{iteration.items.map(item => <div className="file-row" key={item.id}>
            <button className="text-button" onClick={() => open(item.id)}>{item.title} <small>· {typeName(item.type)}</small></button>
            <div className="inline-actions"><span>{hours(item.plannedHours)}</span>{canEdit && <button onClick={() => void action(`/iterations/${iteration.id}/items/${item.id}`, { method: 'DELETE' })}>Исключить</button>}</div>
          </div>)}</div> : <Empty text="Добавьте элементы из бэклога" />}
          {canEdit && <div className="composer row">
            <WorkItemPicker value={newItemId} onChange={setNewItemId} placeholder="Начните вводить название элемента…" />
            <button className="button secondary" onClick={() => { if (newItemId) void action(`/iterations/${iteration.id}/items/${newItemId}`, { method: 'PUT' }); setNewItemId(''); }}>Добавить</button>
          </div>}
        </div>
        <div className="panel"><h3>Распределение по статусам</h3><div className="status-summary">{Object.entries(iteration.statusCounts).map(([status, count]) => <span key={status}><Badge>{status}</Badge> {count}</span>)}</div></div>
        {iteration.state === 'COMPLETED' && <PlanFact baseline={baseline} result={result} context={context} />}
      </> : <Empty text="Выберите итерацию" />}</div>
    </div>
    {creating && <div className="overlay" onMouseDown={() => setCreating(false)}>
      <div className="small-dialog" onMouseDown={e => e.stopPropagation()}>
        <div className="dialog-title"><h2>Новая итерация</h2><button onClick={() => setCreating(false)}>×</button></div>
        <form className="form-grid" onSubmit={e => void create(e)}>
          <label className="span-2">Название<input required value={name} onChange={e => setName(e.target.value)} /></label>
          <label>Начало<input required type="date" value={start} onChange={e => setStart(e.target.value)} /></label>
          <label>Окончание<input required type="date" value={end} onChange={e => setEnd(e.target.value)} /></label>
          <div className="dialog-actions span-2"><button className="button primary">Создать</button></div>
        </form>
      </div>
    </div>}
  </section>;
}
