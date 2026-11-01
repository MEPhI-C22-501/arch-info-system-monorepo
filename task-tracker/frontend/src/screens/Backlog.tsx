import { useState } from 'react';
import { date, hours, json, request, typeName } from '../api';
import type { Item, Iteration, Json, Page } from '../api';
import { can, selectName } from '../context';
import type { Context } from '../context';
import { Badge } from '../components/Badge';
import { Empty } from '../components/Empty';
import { ErrorBanner } from '../components/ErrorBanner';
import { useApiResource } from '../hooks/useApiResource';
import { CreateItem } from './ItemDialog/CreateItem';

const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');
const emptyFilters = { search: '', type: '', statusId: '', priorityId: '', assigneeId: '', iterationId: '' };

export function Backlog({ context, revision, open, refresh }:
  { context: Context; revision: number; open: (id: string) => void; refresh: () => void }) {
  const [filters, setFilters] = useState({ ...emptyFilters, sort: 'dueDate' });
  const [creating, setCreating] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString();
  const { data: page, loading, error } = useApiResource<Page<Item>>(`/work-items?${query}`, revision);
  const { data: iterations } = useApiResource<Iteration[]>('/iterations', revision);

  const change = (key: keyof typeof filters, value: string) => setFilters(current => ({ ...current, [key]: value }));
  const activeFilterCount = Object.entries(emptyFilters).filter(([key]) => filters[key as keyof typeof emptyFilters]).length;

  const exportFile = async () => {
    try {
      const blob = await request<Blob>('/exports/work-items', json('POST', {}));
      const url = URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = 'task-tracker.xlsx'; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setUploadError(getError(e)); }
  };
  const importFile = async (file: File) => {
    try {
      const form = new FormData(); form.append('file', file);
      const result = await request<{ created: number; updated: number; rejected: number; errors: Json[] }>('/imports/work-items', { method: 'POST', body: form });
      alert(`Создано: ${result.created}, обновлено: ${result.updated}, отклонено: ${result.rejected}`);
      refresh();
    } catch (e) { setUploadError(getError(e)); }
  };

  return <section className="screen-content">
    <div className="section-heading">
      <div><h2>Все рабочие элементы</h2><p>Планируйте, назначайте и отслеживайте работу команды</p></div>
      <div className="actions">
        {can(context, 'excel.export') && <button className="button secondary" onClick={() => void exportFile()}>↓ Экспорт .xlsx</button>}
        {can(context, 'excel.import') && <label className="button secondary file-button">↑ Импорт .xlsx
          <input type="file" accept=".xlsx" onChange={e => { const file = e.target.files?.[0]; if (file) void importFile(file); e.target.value = ''; }} /></label>}
        {can(context, 'item.create') && <button className="button primary" onClick={() => setCreating(true)}>＋ Создать элемент</button>}
      </div>
    </div>
    <ErrorBanner message={error || uploadError} clear={() => setUploadError('')} />
    <div className="filters">
      <input aria-label="Поиск" placeholder="Поиск по названию" value={filters.search} onChange={e => change('search', e.target.value)} />
      <select aria-label="Тип" value={filters.type} onChange={e => change('type', e.target.value)}>
        <option value="">Все типы</option>{context.types.map(row => <option key={row.type} value={row.type}>{typeName(row.type)}</option>)}
      </select>
      <select aria-label="Статус" value={filters.statusId} onChange={e => change('statusId', e.target.value)}>
        <option value="">Все статусы</option>{context.statuses.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select>
      <select aria-label="Приоритет" value={filters.priorityId} onChange={e => change('priorityId', e.target.value)}>
        <option value="">Все приоритеты</option>{context.priorities.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select>
      <select aria-label="Исполнитель" value={filters.assigneeId} onChange={e => change('assigneeId', e.target.value)}>
        <option value="">Все исполнители</option>{context.users.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select>
      <select aria-label="Итерация" value={filters.iterationId} onChange={e => change('iterationId', e.target.value)}>
        <option value="">Все итерации</option>{(iterations ?? []).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select>
      <select aria-label="Сортировка" value={filters.sort} onChange={e => change('sort', e.target.value)}>
        <option value="dueDate">По сроку</option><option value="priority">По приоритету</option><option value="status">По статусу</option><option value="createdAt">Сначала новые</option>
      </select>
      {activeFilterCount > 0 && <button type="button" className="button secondary filter-reset" onClick={() => setFilters({ ...emptyFilters, sort: filters.sort })}>
        Сбросить фильтры ({activeFilterCount})
      </button>}
    </div>
    <div className="panel table-panel">
      {loading ? <p className="loading">Загрузка элементов…</p> : page?.items.length
        ? <div className="table-scroll"><table>
            <thead><tr><th>Элемент</th><th>Тип</th><th>Статус</th><th>Приоритет</th><th>Исполнитель</th><th>Срок</th><th>План / Факт / Остаток</th></tr></thead>
            <tbody>{page.items.map(item => <tr key={item.id} onClick={() => open(item.id)} tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') open(item.id); }}>
              <td><strong>{item.title}</strong><small>{item.id.slice(0, 8)}</small></td>
              <td>{typeName(item.type)}</td>
              <td><Badge tone={context.statuses.find(row => row.id === item.statusId)?.category === 'COMPLETED' ? 'green' : ''}>{selectName(context.statuses, item.statusId)}</Badge></td>
              <td>{selectName(context.priorities, item.priorityId)}</td>
              <td>{selectName(context.users, item.assigneeId)}</td>
              <td>{item.dueDate ? date(item.dueDate) : '—'}</td>
              <td className={item.remainingHours < 0 ? 'negative' : ''}>{hours(item.plannedHours)} / {hours(item.actualHours)} / {hours(item.remainingHours)}</td>
            </tr>)}</tbody>
          </table></div>
        : <Empty text="По выбранным фильтрам рабочих элементов нет" />}
    </div>
    {page && <p className="list-foot">Всего элементов: {page.total}</p>}
    {creating && <CreateItem context={context} close={() => setCreating(false)} created={id => { setCreating(false); refresh(); open(id); }} />}
  </section>;
}
