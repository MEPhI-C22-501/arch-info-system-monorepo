import { useEffect, useState } from 'react';
import { ApiError, api, errorMessage } from '../api';
import { Empty, Failure, Loading, Notice } from '../components/State';
import { dateTime, duration, formatCell, sourceName } from '../format';
import { abilities, useSession } from '../session';
import type { Batch, Freshness as Stream, LoadRequest, Page, Reconciliation } from '../types';
import { useLoad } from '../useLoad';

const STATE = { FRESH: ['Актуально', 'status-completed'], STALE: ['Устарело', 'status-failed'], UNKNOWN: ['Нет данных', 'status-queued'] } as const;
const BATCH = { LOADED: ['Загружен', 'status-completed'], REJECTED: ['Отклонён', 'status-failed'], EXTRACTING: ['Загружается', 'status-queued'] } as const;
const REASONS: Record<string, string> = { MANUAL_LOAD: 'вручную', RECONCILIATION_DRIFT: 'расхождение сверки' };
const SIZE = 20;

// SCR-10: the stream table for everyone; the batch and reconciliation journal for RL-05 and RL-06; manual load for RL-06.
export function Freshness() {
  const session = useSession();
  const can = abilities(session);
  const streams = useLoad(() => api<Page<Stream>>(session.token, 'freshness'), [session.token]);
  const latest = useLoad(() => (can.etlJournal ? api<Page<Batch>>(session.token, 'etl/batches?pageSize=100') : Promise.resolve(null)), [session.token, can.etlJournal]);
  const checks = useLoad(() => (can.etlJournal ? api<Page<Reconciliation>>(session.token, 'etl/reconciliations?pageSize=100') : Promise.resolve(null)), [session.token, can.etlJournal]);
  const requests = useLoad(() => (can.etlJournal ? api<{ items: LoadRequest[] }>(session.token, 'etl/loads') : Promise.resolve(null)), [session.token, can.etlJournal]);
  const [message, setMessage] = useState<{ tone: 'success' | 'warning'; text: string } | null>(null);

  // While a request waits, the page follows it: the request, the stream and the journal refresh every 5 s.
  const waiting = (requests.data?.items ?? []).some((r) => r.status === 'PENDING');
  useEffect(() => {
    if (!waiting) return;
    const timer = setTimeout(() => { requests.reload(); streams.reload(); latest.reload(); checks.reload(); }, 5000);
    return () => clearTimeout(timer);
  }, [waiting, requests, streams, latest, checks]);

  const load = async (source: string) => {
    setMessage(null);
    try {
      await api(session.token, 'etl/loads', 'POST', { source });
      setMessage({ tone: 'success', text: `Заявка на загрузку «${sourceName(source)}» принята. Её выполнит ближайший цикл загрузки этого источника.` });
      requests.reload();
    } catch (e) {
      setMessage({ tone: 'warning', text: e instanceof ApiError && e.status === 409 ? `Заявка на загрузку «${sourceName(source)}» уже ждёт выполнения.` : errorMessage(e) });
    }
  };
  const first = <T extends { source: string }>(items: T[] | undefined, source: string) => items?.find((i) => i.source === source);

  return (
    <>
      <h1>Актуальность данных</h1>
      <p className="muted">Отчёт помечается как устаревший, если данные источника старше порога.</p>
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
      {streams.loading && !streams.data ? <Loading /> : streams.error ? <Failure message={errorMessage(streams.error)} onRetry={streams.reload} /> : (
        <div className="table-scroll" tabIndex={0}>
          <table>
            <caption>Потоки данных</caption>
            <thead>
              <tr>
                <th scope="col">Источник</th><th scope="col">Поток</th><th scope="col">Данные на</th><th scope="col">Лаг</th><th scope="col">Порог</th><th scope="col">Состояние</th>
                {can.etlJournal && <><th scope="col">Последний пакет</th><th scope="col">Последняя сверка</th></>}
                {can.etlLoad && <th scope="col">Действие</th>}
              </tr>
            </thead>
            <tbody>
              {streams.data!.items.map((s) => {
                const batch = first(latest.data?.items, s.source);
                const check = first(checks.data?.items, s.source);
                const pending = (requests.data?.items ?? []).some((r) => r.source === s.source && r.status === 'PENDING');
                return (
                  <tr key={s.source + s.stream}>
                    <td>{sourceName(s.source)}</td>
                    <td>{s.stream}</td>
                    <td>{dateTime(s.dataAsOf)}</td>
                    <td>{duration(s.lagSeconds)}</td>
                    <td>{duration(s.thresholdSeconds)}</td>
                    <td className={'status ' + STATE[s.state][1]}>{STATE[s.state][0]}</td>
                    {can.etlJournal && (
                      <>
                        <td>{batch ? <span className={'status ' + BATCH[batch.status][1]}>{BATCH[batch.status][0]}, {dateTime(batch.finishedAt ?? batch.startedAt)}</span> : '—'}</td>
                        <td>{check ? <span className={check.result === 'MATCH' ? 'status status-completed' : 'status status-failed'}>{check.result === 'MATCH' ? 'Совпадает' : 'Расхождение'}, {dateTime(check.checkedAt)}</span> : '—'}</td>
                      </>
                    )}
                    {can.etlLoad && (
                      <td>
                        <button type="button" className="secondary" disabled={pending} onClick={() => load(s.source)}
                          aria-label={`Загрузить сейчас: ${sourceName(s.source)}`}>{pending ? 'Ждёт загрузки…' : 'Загрузить сейчас'}</button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {can.etlJournal && (
        <>
          <LoadRequests requests={requests} />
          <BatchJournal />
          <Reconciliations checks={checks} />
        </>
      )}
    </>
  );
}

function LoadRequests({ requests }: { requests: ReturnType<typeof useLoad<{ items: LoadRequest[] } | null>> }) {
  const items = requests.data?.items ?? [];
  if (requests.error) return <Failure message={errorMessage(requests.error)} onRetry={requests.reload} />;
  if (!items.length) return null;
  return (
    <>
      <h2>Заявки на загрузку</h2>
      <ul className="list">
        {items.map((r) => (
          <li key={r.source + r.requestedAt}>
            <span>{sourceName(r.source)} · {REASONS[r.reason] ?? r.reason} · {dateTime(r.requestedAt)}</span>
            <span className={r.status === 'PENDING' ? 'status status-queued' : 'status status-completed'}>{r.status === 'PENDING' ? 'Ждёт загрузки' : 'Выполнена'}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

function BatchJournal() {
  const { token } = useSession();
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [page, setPage] = useState(1);
  const query = new URLSearchParams({ page: String(page), pageSize: String(SIZE), ...(status ? { status } : {}), ...(source ? { source } : {}) });
  const batches = useLoad(() => api<Page<Batch>>(token, 'etl/batches?' + query), [token, query.toString()]);
  const total = batches.data?.total ?? 0;
  return (
    <section aria-labelledby="batches-title">
      <h2 id="batches-title">Журнал пакетов</h2>
      <form className="dashboard-filters" aria-label="Фильтр журнала пакетов" onSubmit={(e) => e.preventDefault()}>
        <label>Источник
          <select value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }}>
            <option value="">Все</option>
            {['task-tracker', 'planning-system', 'reference-manager', 'qa-system'].map((s) => <option key={s} value={s}>{sourceName(s)}</option>)}
          </select>
        </label>
        <label>Статус
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Все</option>
            {Object.entries(BATCH).map(([key, [name]]) => <option key={key} value={key}>{name}</option>)}
          </select>
        </label>
      </form>
      {batches.loading && !batches.data ? <Loading /> : batches.error ? <Failure message={errorMessage(batches.error)} onRetry={batches.reload} /> :
        !batches.data?.items.length ? <Empty>Пакетов с такими условиями нет.</Empty> : (
          <>
            <div className="table-scroll" tabIndex={0}>
              <table>
                <caption>Пакеты загрузки, страница {page} из {Math.max(1, Math.ceil(total / SIZE))}</caption>
                <thead><tr><th scope="col">Источник</th><th scope="col">Статус</th><th scope="col">Начало</th><th scope="col">Окончание</th><th scope="col" className="num">Записей</th><th scope="col">Ошибка</th></tr></thead>
                <tbody>
                  {batches.data.items.map((b) => (
                    <tr key={b.batchId}>
                      <td>{sourceName(b.source)}</td>
                      <td className={'status ' + BATCH[b.status][1]}>{BATCH[b.status][0]}</td>
                      <td>{dateTime(b.startedAt)}</td>
                      <td>{b.finishedAt ? dateTime(b.finishedAt) : '—'}</td>
                      <td className="num">{b.rows === null ? '—' : formatCell(b.rows)}</td>
                      <td className="mono">{b.error ?? '—'}</td>
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
    </section>
  );
}

function Reconciliations({ checks }: { checks: ReturnType<typeof useLoad<Page<Reconciliation> | null>> }) {
  if (checks.loading && !checks.data) return <Loading />;
  if (checks.error) return <Failure message={errorMessage(checks.error)} onRetry={checks.reload} />;
  const items = (checks.data?.items ?? []).slice(0, SIZE);
  return (
    <section aria-labelledby="checks-title">
      <h2 id="checks-title">Последние сверки</h2>
      <p className="muted">При загрузке сверяется ответ источника с хранилищем; ночью — хранилище с оперативной витриной. Расхождение ставит заявку на загрузку всего источника.</p>
      {!items.length ? <Empty>Сверок ещё не было.</Empty> : (
        <div className="table-scroll" tabIndex={0}>
          <table>
            <caption>Сверки, последние {items.length}</caption>
            <thead><tr><th scope="col">Источник</th><th scope="col">Сущность</th><th scope="col" className="num">В источнике</th><th scope="col" className="num">В хранилище</th><th scope="col" className="num">Нет в хранилище</th><th scope="col" className="num">Лишние</th><th scope="col">Вид</th><th scope="col">Результат</th><th scope="col">Время</th></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.reconciliationId}>
                  <td>{sourceName(c.source)}</td><td className="mono">{c.entity}</td>
                  <td className="num">{c.sourceCount}</td><td className="num">{c.dwhCount}</td><td className="num">{c.missing}</td><td className="num">{c.extra}</td>
                  <td>{c.mode === 'SOURCE' ? 'с источником' : 'с витриной'}</td>
                  <td className={c.result === 'MATCH' ? 'status status-completed' : 'status status-failed'}>{c.result === 'MATCH' ? 'Совпадает' : 'Расхождение'}</td>
                  <td>{dateTime(c.checkedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
