import { dateTime, request } from '../api';
import type { Json } from '../api';
import { Empty } from '../components/Empty';
import { ErrorBanner } from '../components/ErrorBanner';
import { useApiResource } from '../hooks/useApiResource';

const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');

export function Notifications({ open, revision, refresh }: { open: (id: string) => void; revision: number; refresh: () => void }) {
  const { data, error, setError } = useApiResource<Array<Json>>('/notifications', revision);
  const rows = data ?? [];
  const unread = rows.filter(row => !row.readAt);

  const mark = async (row: Json) => {
    try { await request(`/notifications/${row.id}`, { method: 'PATCH' }); refresh(); }
    catch (e) { setError(getError(e)); }
  };
  const markAll = async () => {
    try { await Promise.all(unread.map(row => request(`/notifications/${row.id}`, { method: 'PATCH' }))); refresh(); }
    catch (e) { setError(getError(e)); }
  };

  return <section className="screen-content">
    <div className="section-heading">
      <div><h2>Последние изменения</h2><p>Уведомления о назначениях и событиях ваших задач</p></div>
      {unread.length > 0 && <button className="button secondary" onClick={() => void markAll()}>Отметить все прочитанными ({unread.length})</button>}
    </div>
    <ErrorBanner message={error} clear={() => setError('')} />
    <div className="panel notification-list">
      {rows.length ? rows.map(row => <div className={`notification ${row.readAt ? '' : 'unread'}`} key={String(row.id)}>
        <span className="notification-dot" />
        <div>
          <strong>{String(row.message)}</strong>
          <p>{String(row.workItemTitle)} · {dateTime(row.createdAt)} · {String(row.actor)}</p>
          <div className="inline-actions">
            {Boolean(row.workItemId) && <button onClick={() => open(String(row.workItemId))}>Открыть карточку</button>}
            {!row.readAt && <button onClick={() => void mark(row)}>Отметить прочитанным</button>}
          </div>
        </div>
      </div>) : <Empty text="Уведомлений пока нет" />}
    </div>
  </section>;
}
