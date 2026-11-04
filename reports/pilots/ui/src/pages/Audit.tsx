import { useState } from 'react';
import { api, errorMessage } from '../api';
import { Empty, Failure, Loading } from '../components/State';
import { dateTime } from '../format';
import { useSession } from '../session';
import type { AuditEvent, Page } from '../types';
import { useLoad } from '../useLoad';

const SIZE = 50;

export function Audit() {
  const { token } = useSession();
  const [page, setPage] = useState(1);
  const events = useLoad(() => api<Page<AuditEvent>>(token, `audit?page=${page}&pageSize=${SIZE}`), [token, page]);
  const total = events.data?.total ?? 0;
  return (
    <>
      <h1>Аудит</h1>
      <p className="muted">Все обращения к отчётам, выгрузки и изменения подписок. Записи только добавляются.</p>
      {events.loading && !events.data ? <Loading /> : events.error ? <Failure message={errorMessage(events.error)} onRetry={events.reload} /> :
        !events.data?.items.length ? <Empty>Событий нет.</Empty> : (
          <>
            <div className="table-scroll" tabIndex={0}>
              <table>
                <caption>События, страница {page} из {Math.max(1, Math.ceil(total / SIZE))}</caption>
                <thead><tr><th scope="col">Время</th><th scope="col">Пользователь</th><th scope="col">Действие</th><th scope="col">Отчёт</th><th scope="col">Результат</th><th scope="col">Код обращения</th></tr></thead>
                <tbody>
                  {events.data.items.map((e) => (
                    <tr key={e.auditId}>
                      <td>{dateTime(e.at)}</td><td className="mono">{e.actor}</td><td>{e.action}</td>
                      <td>{e.reportId ?? '—'}</td><td>{e.result}</td><td className="mono">{e.correlationId}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="button-row">
              <button type="button" className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</button>
              <button type="button" className="secondary" disabled={page * SIZE >= total} onClick={() => setPage(page + 1)}>Дальше</button>
            </div>
          </>
        )}
    </>
  );
}
