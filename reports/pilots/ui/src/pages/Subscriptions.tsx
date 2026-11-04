import { useState, type FormEvent } from 'react';
import { useLocation } from 'react-router-dom';
import { api, errorMessage } from '../api';
import { Empty, Failure, Loading, Notice } from '../components/State';
import { SLICE_TITLES, dateTime, today, weekStart } from '../format';
import { useSession } from '../session';
import type { Delivery, Page, ReportDefinition, ReportQuery, SavedView, Subscription } from '../types';
import { useLoad } from '../useLoad';

const DAYS = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
const STATUS = { ACTIVE: 'Активна', PAUSED: 'Приостановлена', COMPLETED: 'Завершена' } as const;

/** Readable form of the cron schedules the form creates; anything else is shown as is. */
export function describeSchedule(cron: string): string {
  const [minute = '', hour = '', dom, month, dow] = cron.split(' ');
  // Plain wording only for one fixed time of day; anything else (e.g. */5) stays as cron.
  if (!/^\d+$/.test(minute) || !/^\d+$/.test(hour)) return 'Расписание cron: ' + cron;
  const time = ` в ${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
  if (dom === '*' && month === '*' && dow === '*') return 'Ежедневно' + time;
  if (dom === '*' && month === '*' && /^[0-6]$/.test(dow)) return `Еженедельно, ${DAYS[Number(dow)].toLowerCase()}` + time;
  if (/^\d+$/.test(dom) && month === '*' && dow === '*') return `Ежемесячно, ${dom}-го числа` + time;
  return 'Расписание cron: ' + cron;
}

// SCR-09.
export function Subscriptions() {
  const session = useSession();
  const prefill = (useLocation().state ?? null) as { reportId: string; query: ReportQuery } | null;
  const list = useLoad(() => api<Page<Subscription>>(session.token, 'subscriptions'), [session.token]);
  const catalog = useLoad(() => api<Page<ReportDefinition>>(session.token, 'reports'), [session.token]);
  const views = useLoad(() => api<Page<SavedView>>(session.token, 'views'), [session.token]);
  const [error, setError] = useState('');
  const [opened, setOpened] = useState<{ id: string; items: Delivery[] } | null>(null);

  const act = async (action: () => Promise<unknown>) => {
    setError('');
    try { await action(); list.reload(); } catch (e) { setError(errorMessage(e)); }
  };
  const setStatus = (s: Subscription, status: Subscription['status']) =>
    act(() => api(session.token, 'subscriptions/' + s.subscriptionId, 'PATCH', { status }, { 'If-Match': `"${s.version}"` }));
  const finish = (s: Subscription) => {
    if (window.confirm(`Завершить подписку на ${s.reportId}? Её нельзя будет возобновить.`)) act(() => api(session.token, 'subscriptions/' + s.subscriptionId, 'DELETE'));
  };
  const deliveries = (s: Subscription) => act(async () => {
    const page = await api<Page<Delivery>>(session.token, `subscriptions/${s.subscriptionId}/deliveries`);
    setOpened({ id: s.subscriptionId, items: page.items });
  });

  return (
    <>
      <h1>Подписки</h1>
      {catalog.data && <SubscriptionForm reports={catalog.data.items} views={views.data?.items ?? []} prefill={prefill} onCreated={list.reload} />}
      <h2>Мои подписки</h2>
      {error && <Failure message={error} />}
      {list.loading && !list.data ? <Loading /> : list.error ? <Failure message={errorMessage(list.error)} onRetry={list.reload} /> :
        !list.data?.items.length ? <Empty>Подписок пока нет.</Empty> : (
          <ul className="list">
            {list.data.items.map((s) => (
              <li key={s.subscriptionId}>
                <span>
                  <strong>{s.reportId}</strong> · {describeSchedule(s.schedule)} · {s.format.toUpperCase()} · {STATUS[s.status]}
                  {s.status === 'ACTIVE' && <> · следующая отправка {dateTime(s.nextRunAt)}</>}
                </span>
                <span className="button-row">
                  {s.status === 'ACTIVE' && <button type="button" className="secondary" onClick={() => setStatus(s, 'PAUSED')}>Приостановить</button>}
                  {s.status === 'PAUSED' && <button type="button" className="secondary" onClick={() => setStatus(s, 'ACTIVE')}>Возобновить</button>}
                  <button type="button" className="secondary" onClick={() => deliveries(s)}>Доставки</button>
                  {s.status !== 'COMPLETED' && <button type="button" className="danger" onClick={() => finish(s)}>Завершить</button>}
                </span>
                {opened?.id === s.subscriptionId && (
                  <div className="deliveries">
                    {!opened.items.length ? <p className="muted">Доставок ещё не было.</p> : (
                      <ul>
                        {opened.items.map((d, i) => (
                          <li key={i}>
                            {dateTime(typeof d.runAt === 'string' ? d.runAt : null)}: доставлено {d.delivered?.length ?? 0}
                            {d.skipped?.length ? `, пропущено ${d.skipped.length} (нет доступа)` : ''}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
    </>
  );
}

function SubscriptionForm({ reports, views, prefill, onCreated }: { reports: ReportDefinition[]; views: SavedView[]; prefill: { reportId: string; query: ReportQuery } | null; onCreated: () => void }) {
  const session = useSession();
  const [reportId, setReportId] = useState(prefill?.reportId ?? reports[0]?.reportId ?? '');
  // Parameters: 'page' — taken from the report page, 'week' — the current week, otherwise a saved view id.
  const [source, setSource] = useState(prefill ? 'page' : 'week');
  const [kind, setKind] = useState<'daily' | 'weekly' | 'monthly' | 'cron'>('weekly');
  const [time, setTime] = useState('09:00');
  const [day, setDay] = useState('1');
  const [cron, setCron] = useState('0 9 * * 1');
  const [format, setFormat] = useState<'csv' | 'xlsx'>('xlsx');
  const [recipients, setRecipients] = useState(session.subject);
  const [validUntil, setValidUntil] = useState('');
  const [message, setMessage] = useState<{ tone: 'success' | 'warning'; text: string } | null>(null);
  const [hour, minute] = time.split(':').map(Number);
  const schedule = kind === 'daily' ? `${minute} ${hour} * * *` : kind === 'weekly' ? `${minute} ${hour} * * ${day}`
    : kind === 'monthly' ? `${minute} ${hour} ${day} * *` : cron.trim();
  const report = reports.find((r) => r.reportId === reportId);
  const ownViews = views.filter((v) => v.reportId === reportId);
  const fromPage = source === 'page' && prefill?.reportId === reportId;
  const view = ownViews.find((v) => v.viewId === source);
  const query: ReportQuery = fromPage ? prefill!.query : view ? view.query
    : { params: { periodFrom: weekStart(), periodTo: today() }, slice: [report?.slices[0] ?? 'project'] };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    const body: Record<string, unknown> = { reportId, query, schedule, format, recipients: recipients.split(',').map((s) => s.trim()).filter(Boolean) };
    if (validUntil) body.validUntil = validUntil;
    try {
      await api(session.token, 'subscriptions', 'POST', body);
      setMessage({ tone: 'success', text: 'Подписка создана.' });
      onCreated();
    } catch (e) {
      setMessage({ tone: 'warning', text: errorMessage(e) });
    }
  };

  return (
    <form className="panel" onSubmit={submit} aria-labelledby="new-subscription">
      <h2 id="new-subscription">Новая подписка</h2>
      <label>Отчёт
        <select value={reportId} onChange={(e) => { setReportId(e.target.value); setSource(prefill?.reportId === e.target.value ? 'page' : 'week'); }}>
          {reports.map((r) => <option key={r.reportId} value={r.reportId}>{r.reportId} — {r.name}</option>)}
        </select>
      </label>
      <label>Параметры
        <select value={fromPage || view ? source : 'week'} onChange={(e) => setSource(e.target.value)}>
          {prefill?.reportId === reportId && <option value="page">Со страницы отчёта</option>}
          <option value="week">Текущая неделя</option>
          {ownViews.map((v) => <option key={v.viewId} value={v.viewId}>Представление «{v.name}»</option>)}
        </select>
      </label>
      <p className="muted">
        Период {query.params.periodFrom} — {query.params.periodTo}, разрез «{SLICE_TITLES[query.slice[0]] ?? query.slice[0]}».
        {' '}Другие параметры задаются на странице отчёта кнопкой «Подписаться» или сохранённым представлением.
      </p>
      <fieldset>
        <legend>Расписание (время московское)</legend>
        <label>Периодичность
          <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
            <option value="daily">Ежедневно</option><option value="weekly">Еженедельно</option>
            <option value="monthly">Ежемесячно</option><option value="cron">Выражение cron</option>
          </select>
        </label>
        {kind !== 'cron' && <label>Время<input type="time" required value={time} onChange={(e) => setTime(e.target.value)} /></label>}
        {kind === 'weekly' && (
          <label>День недели
            <select value={day} onChange={(e) => setDay(e.target.value)}>{DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}</select>
          </label>
        )}
        {kind === 'monthly' && <label>Число месяца<input type="number" min={1} max={28} required value={day} onChange={(e) => setDay(e.target.value)} /></label>}
        {kind === 'cron' && <label>Cron<input required value={cron} onChange={(e) => setCron(e.target.value)} /></label>}
        <p className="muted">{describeSchedule(schedule)}</p>
      </fieldset>
      <label>Формат
        <select value={format} onChange={(e) => setFormat(e.target.value as 'csv' | 'xlsx')}><option value="xlsx">XLSX</option><option value="csv">CSV</option></select>
      </label>
      <label>Получатели (ID пользователей через запятую)
        <input required value={recipients} onChange={(e) => setRecipients(e.target.value)} aria-describedby="recipients-hint" />
      </label>
      <p id="recipients-hint" className="muted">Каждый получатель получит файл только в пределах своих прав; без доступа он будет пропущен.</p>
      <label>Действует до (необязательно)<input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} /></label>
      <button type="submit">Создать подписку</button>
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
    </form>
  );
}
