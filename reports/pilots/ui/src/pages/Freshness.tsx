import { api, errorMessage } from '../api';
import { Failure, Loading } from '../components/State';
import { dateTime, duration, sourceName } from '../format';
import { useSession } from '../session';
import type { Freshness as Stream, Page } from '../types';
import { useLoad } from '../useLoad';

const STATE = { FRESH: ['Актуально', 'status-completed'], STALE: ['Устарело', 'status-failed'], UNKNOWN: ['Нет данных', 'status-queued'] } as const;

// SCR-10: stream table for everyone; the batch log and manual load come with the ETL API (UI-2).
export function Freshness() {
  const { token } = useSession();
  const streams = useLoad(() => api<Page<Stream>>(token, 'freshness'), [token]);
  return (
    <>
      <h1>Актуальность данных</h1>
      <p className="muted">Отчёт помечается как устаревший, если данные источника старше порога.</p>
      {streams.loading ? <Loading /> : streams.error ? <Failure message={errorMessage(streams.error)} onRetry={streams.reload} /> : (
        <div className="table-scroll" tabIndex={0}>
          <table>
            <caption>Потоки данных</caption>
            <thead><tr><th scope="col">Источник</th><th scope="col">Поток</th><th scope="col">Данные на</th><th scope="col">Лаг</th><th scope="col">Порог</th><th scope="col">Состояние</th></tr></thead>
            <tbody>
              {streams.data!.items.map((s) => (
                <tr key={s.source + s.stream}>
                  <td>{sourceName(s.source)}</td>
                  <td>{s.stream}</td>
                  <td>{dateTime(s.dataAsOf)}</td>
                  <td>{duration(s.lagSeconds)}</td>
                  <td>{duration(s.thresholdSeconds)}</td>
                  <td className={'status ' + STATE[s.state][1]}>{STATE[s.state][0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
