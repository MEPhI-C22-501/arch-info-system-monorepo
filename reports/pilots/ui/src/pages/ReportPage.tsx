import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ApiError, api, errorMessage } from '../api';
import { BarChart } from '../components/BarChart';
import { ResultTable, Totals } from '../components/ResultTable';
import { Empty, Failure, Loading, Notice } from '../components/State';
import { dateTime, formatCell, label, noteText, sourceName, staleSources, today, weekStart } from '../format';
import { abilities, useSession } from '../session';
import type { ReportDefinition, ReportQuery, ReportResult, SavedView } from '../types';
import { useLoad } from '../useLoad';

const SLICE_TITLES: Record<string, string> = {
  project: 'Проект', unit: 'Подразделение', role: 'Проектная роль', employee: 'Сотрудник', iteration: 'Итерация',
  epic: 'Эпик', week: 'Неделя', month: 'Месяц', record: 'Запись', grade: 'Грейд', status: 'Статус', type: 'Вид задачи', severity: 'Серьёзность',
};

const list = (value: string | null) => (value ?? '').split(',').map((s) => s.trim()).filter(Boolean);

/** Query from the address bar: the link with parameters can be shared; access is checked again on open (110, section 5). */
export function queryFromSearch(search: URLSearchParams, definition: ReportDefinition): ReportQuery {
  const params: ReportQuery['params'] & { iterationIds?: string[] } = {
    periodFrom: search.get('from') ?? weekStart(), periodTo: search.get('to') ?? today(),
  };
  for (const [key, name] of [['projectIds', 'projects'], ['iterationIds', 'iterations'], ['employeeIds', 'employees']] as const) {
    const values = list(search.get(name));
    if (values.length) params[key] = values;
  }
  const slice = definition.slices.includes(search.get('slice') ?? '') ? search.get('slice')! : definition.slices[0];
  return { params, slice: [slice], compareWithPrevious: search.get('compare') === '1' };
}

function searchFromQuery(query: ReportQuery): URLSearchParams {
  const params = query.params as ReportQuery['params'] & { iterationIds?: string[] };
  const search = new URLSearchParams({ from: params.periodFrom, to: params.periodTo, slice: query.slice[0] });
  if (params.projectIds?.length) search.set('projects', params.projectIds.join(','));
  if (params.iterationIds?.length) search.set('iterations', params.iterationIds.join(','));
  if (params.employeeIds?.length) search.set('employees', params.employeeIds.join(','));
  if (query.compareWithPrevious) search.set('compare', '1');
  return search;
}

const remembered = (reportId: string) => 'reports.params.' + reportId;

export function ReportPage() {
  const { reportId = '' } = useParams();
  const { token } = useSession();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const definition = useLoad(() => api<ReportDefinition>(token, 'reports/' + reportId), [token, reportId]);

  // Opening without parameters: a saved view, the last parameters of this tab, or the current week.
  useEffect(() => {
    if (!definition.data || search.get('from')) return;
    const viewId = search.get('view');
    if (viewId) {
      api<SavedView>(token, 'views/' + viewId).then((view) => setSearch(searchFromQuery(view.query), { replace: true }), () => setSearch({ ...Object.fromEntries(search), from: weekStart(), to: today() }, { replace: true }));
      return;
    }
    const last = sessionStorage.getItem(remembered(reportId));
    setSearch(last ? new URLSearchParams(last) : searchFromQuery(queryFromSearch(new URLSearchParams(), definition.data)), { replace: true });
  }, [definition.data, search, setSearch, reportId, token]);

  const query = useMemo(() => (definition.data && search.get('from') ? queryFromSearch(search, definition.data) : null), [definition.data, search]);
  const result = useLoad<ReportResult | null>(
    () => (query ? api<ReportResult>(token, `reports/${reportId}/query`, 'POST', query) : Promise.resolve(null)),
    [token, reportId, JSON.stringify(query)],
  );
  useEffect(() => {
    if (query) sessionStorage.setItem(remembered(reportId), searchFromQuery(query).toString());
  }, [query, reportId]);

  if (definition.loading) return <Loading />;
  if (definition.error) {
    const missing = definition.error instanceof ApiError && definition.error.status === 404;
    return <Failure message={missing ? 'Отчёт не найден.' : errorMessage(definition.error)} onRetry={missing ? undefined : definition.reload} />;
  }
  const report = definition.data!;
  return (
    <>
      <nav aria-label="Путь" className="breadcrumbs"><Link to="/">Каталог</Link> › {report.reportId}</nav>
      <h1>{report.reportId} — {report.name}</h1>
      <p className="muted">{report.question}</p>
      <div className="report-layout">
        {query && <Parameters key={JSON.stringify(query)} report={report} query={query} onApply={(next) => setSearch(searchFromQuery(next))} />}
        <section className="report-result" aria-labelledby="result-title" aria-busy={result.loading}>
          <h2 id="result-title">Результат</h2>
          {query && <Actions report={report} query={query} onSubscribe={() => navigate('/subscriptions', { state: { reportId, query } })} />}
          {query && <ResultView result={result} report={report} query={query} />}
        </section>
      </div>
    </>
  );
}

function Parameters({ report, query, onApply }: { report: ReportDefinition; query: ReportQuery; onApply: (query: ReportQuery) => void }) {
  const params = query.params as ReportQuery['params'] & { iterationIds?: string[] };
  const [from, setFrom] = useState(params.periodFrom);
  const [to, setTo] = useState(params.periodTo);
  const [slice, setSlice] = useState(query.slice[0]);
  const [projects, setProjects] = useState((params.projectIds ?? []).join(', '));
  const [iterations, setIterations] = useState((params.iterationIds ?? []).join(', '));
  const [employees, setEmployees] = useState((params.employeeIds ?? []).join(', '));
  const [compare, setCompare] = useState(Boolean(query.compareWithPrevious));
  const invalidPeriod = from > to;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (invalidPeriod) return;
    const next: ReportQuery['params'] & { iterationIds?: string[] } = { periodFrom: from, periodTo: to };
    if (list(projects).length) next.projectIds = list(projects);
    if (list(iterations).length) next.iterationIds = list(iterations);
    if (list(employees).length) next.employeeIds = list(employees);
    onApply({ params: next, slice: [slice], compareWithPrevious: compare });
  };
  return (
    <form className="parameters" onSubmit={submit} aria-label="Параметры отчёта">
      <label>С<input type="date" required value={from} onChange={(e) => setFrom(e.target.value)} aria-invalid={invalidPeriod} aria-describedby={invalidPeriod ? 'period-error' : undefined} /></label>
      <label>По<input type="date" required value={to} onChange={(e) => setTo(e.target.value)} aria-invalid={invalidPeriod} /></label>
      {invalidPeriod && <p id="period-error" className="field-error">Начало периода позже конца.</p>}
      <label>Разрез
        <select value={slice} onChange={(e) => setSlice(e.target.value)}>
          {report.slices.map((s) => <option key={s} value={s}>{SLICE_TITLES[s] ?? s}</option>)}
        </select>
      </label>
      <label className="checkbox"><input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />Сравнить с предыдущим периодом</label>
      <details>
        <summary>Фильтры</summary>
        <label>Проекты (ID через запятую)<input value={projects} onChange={(e) => setProjects(e.target.value)} /></label>
        <label>Итерации (ID через запятую)<input value={iterations} onChange={(e) => setIterations(e.target.value)} /></label>
        <label>Сотрудники (ID через запятую)<input value={employees} onChange={(e) => setEmployees(e.target.value)} /></label>
      </details>
      <button type="submit">Сформировать</button>
    </form>
  );
}

function Actions({ report, query, onSubscribe }: { report: ReportDefinition; query: ReportQuery; onSubscribe: () => void }) {
  const session = useSession();
  const [message, setMessage] = useState<{ tone: 'success' | 'warning'; text: string } | null>(null);
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState('');
  const run = async (action: () => Promise<void>) => {
    try { await action(); } catch (error) { setMessage({ tone: 'warning', text: errorMessage(error) }); }
  };
  const print = () => run(async () => {
    const blob = await api<Blob>(session.token, `reports/${report.reportId}/print`, 'POST', query);
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  });
  const save = (event: FormEvent) => {
    event.preventDefault();
    run(async () => {
      await api(session.token, 'views', 'POST', { reportId: report.reportId, name: name.trim(), query });
      setNaming(false); setName('');
      setMessage({ tone: 'success', text: 'Представление сохранено, оно доступно в каталоге.' });
    });
  };
  return (
    <div className="actions">
      <div className="button-row">
        <ExportButtons report={report} query={query} />
        <button type="button" className="secondary" onClick={print}>Версия для печати</button>
        <button type="button" className="secondary" aria-expanded={naming} onClick={() => setNaming(!naming)}>Сохранить представление</button>
        {abilities(session).subscriptions && <button type="button" className="secondary" onClick={onSubscribe}>Подписаться</button>}
      </div>
      {naming && (
        <form className="inline-form" onSubmit={save}>
          <label>Название представления<input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} /></label>
          <button type="submit">Сохранить</button>
        </form>
      )}
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
    </div>
  );
}

/** Asynchronous export: the job goes to the queue, the file appears in SCR-08. */
function ExportButtons({ report, query }: { report: ReportDefinition; query: ReportQuery }) {
  const { token } = useSession();
  const [message, setMessage] = useState<{ tone: 'success' | 'warning'; text: string } | null>(null);
  const exportAs = async (format: 'csv' | 'xlsx') => {
    try {
      await api(token, 'exports', 'POST', { reportId: report.reportId, query, format });
      setMessage({ tone: 'success', text: `Выгрузка ${format.toUpperCase()} поставлена в очередь.` });
    } catch (error) {
      setMessage({ tone: 'warning', text: errorMessage(error) });
    }
  };
  return (
    <>
      <button type="button" onClick={() => exportAs('csv')}>Выгрузить CSV</button>
      <button type="button" onClick={() => exportAs('xlsx')}>Выгрузить XLSX</button>
      {message && (
        <Notice tone={message.tone}>
          {message.text} {message.tone === 'success' && <Link to="/exports">Открыть выгрузки</Link>}
        </Notice>
      )}
    </>
  );
}

/** The current parameters in words, for the empty result (SCR-02). */
export function describeQuery(query: ReportQuery): string {
  const params = query.params as ReportQuery['params'] & { iterationIds?: string[] };
  const filters = [['проекты', params.projectIds], ['итерации', params.iterationIds], ['сотрудники', params.employeeIds]] as const;
  return [`период ${params.periodFrom} — ${params.periodTo}`, `разрез «${SLICE_TITLES[query.slice[0]] ?? query.slice[0]}»`,
    ...filters.filter(([, ids]) => ids?.length).map(([name, ids]) => `${name}: ${ids!.join(', ')}`)].join(', ');
}

function ResultView({ result, report, query }: { result: ReturnType<typeof useLoad<ReportResult | null>>; report: ReportDefinition; query: ReportQuery }) {
  const [view, setView] = useState<'table' | 'chart'>('table');
  if (result.loading) return <Loading label="Формируем отчёт…" />;
  if (result.error) {
    if (result.error instanceof ApiError && result.error.code === 'RESULT_TOO_LARGE') {
      // The export buttons of the action bar above build the file asynchronously.
      return <Notice tone="warning">Результат слишком большой для экрана. Сузьте параметры или получите его файлом: «Выгрузить CSV» или «Выгрузить XLSX».</Notice>;
    }
    const forbidden = result.error instanceof ApiError && result.error.status === 403;
    return <Failure message={forbidden ? 'Нет доступа к выбранному проекту или отчёту для вашей роли.' : errorMessage(result.error)} onRetry={forbidden ? undefined : result.reload} />;
  }
  const data = result.data;
  if (!data) return null;
  const stale = staleSources(data.freshness);
  return (
    <>
      <p className="freshness">
        {data.freshness.map((f) => `${sourceName(f.source)}: ${f.state === 'FRESH' ? 'актуально' : 'устарело'} на ${dateTime(f.dataAsOf)}`).join(' · ')}
      </p>
      {stale.map((text) => <Notice key={text} tone="warning">{text}. Показано последнее загруженное состояние.</Notice>)}
      {data.notes.filter((n) => n !== 'NO_DATA').map((note) => <Notice key={note} tone="info">{noteText(note)}</Notice>)}
      {!data.rows.length ? (
        <Empty>По заданным параметрам данных нет: {describeQuery(query)}.</Empty>
      ) : (
        <>
          <Totals result={data} />
          <div className="toggle" role="group" aria-label="Вид результата">
            <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')}>Таблица</button>
            <button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')}>График</button>
          </div>
          {view === 'table' ? <ResultTable result={data} caption={`${report.reportId}: ${report.name}`} /> : <BarChart result={data} />}
        </>
      )}
      {data.comparison && (
        <p className="comparison">
          {data.comparison.delta
            ? 'Изменение к периоду ' + data.comparison.periodFrom + ' — ' + data.comparison.periodTo + ': ' +
              Object.entries(data.comparison.delta).map(([k, v]) => `${data.columns.find((c) => c.key === k)?.title ?? label(k)} ${v > 0 ? '+' : ''}${formatCell(v)}`).join('; ')
            : 'Нет данных для сравнения с предыдущим периодом.'}
        </p>
      )}
    </>
  );
}
