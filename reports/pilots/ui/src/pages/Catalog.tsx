import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, errorMessage } from '../api';
import { Empty, Failure, Loading } from '../components/State';
import { dateTime, sourceName } from '../format';
import { useSession } from '../session';
import type { Freshness, Page, ReportDefinition, SavedView } from '../types';
import { useLoad } from '../useLoad';

// SCR-01: catalog grouped as in 110.
const GROUPS: [string, string[]][] = [
  ['Время и ресурсы', ['R-01', 'R-02', 'R-06']],
  ['Задачи и сроки', ['R-03', 'R-04', 'R-10', 'R-11']],
  ['Качество', ['R-05', 'R-07', 'R-08', 'R-09']],
];

export function Catalog() {
  const { token } = useSession();
  const [search, setSearch] = useState('');
  const catalog = useLoad(() => api<Page<ReportDefinition>>(token, 'reports'), [token]);
  const freshness = useLoad(() => api<Page<Freshness>>(token, 'freshness'), [token]);
  const views = useLoad(() => api<Page<SavedView>>(token, 'views'), [token]);
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [viewError, setViewError] = useState('');

  const bySource = useMemo(() => new Map((freshness.data?.items ?? []).map((f) => [f.source, f])), [freshness.data]);
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (catalog.data?.items ?? []).filter((r) => !needle || `${r.reportId} ${r.name} ${r.question}`.toLowerCase().includes(needle));
  }, [catalog.data, search]);

  const deleteView = async (view: SavedView) => {
    if (!window.confirm(`Удалить представление «${view.name}»?`)) return;
    try {
      await api(token, 'views/' + view.viewId, 'DELETE');
      setRemoved(new Set(removed).add(view.viewId));
    } catch (error) {
      setViewError(errorMessage(error));
    }
  };

  if (catalog.loading) {
    return (
      <>
        <h1>Каталог отчётов</h1>
        <Loading label="Загружаем каталог отчётов…" />
        <ul className="card-grid" aria-hidden="true">{[0, 1, 2].map((i) => <li key={i} className="card skeleton" />)}</ul>
      </>
    );
  }
  if (catalog.error) return <Failure message={'Каталог недоступен. ' + errorMessage(catalog.error)} onRetry={catalog.reload} />;
  if (!catalog.data?.items.length) return <Empty>Вам не назначены отчёты, обратитесь к администратору.</Empty>;

  const myViews = (views.data?.items ?? []).filter((v) => !removed.has(v.viewId));
  return (
    <>
      <h1>Каталог отчётов</h1>
      <label className="search">
        Поиск отчёта
        <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Например, дефекты" />
      </label>
      {GROUPS.map(([title, ids], index) => {
        const reports = visible.filter((r) => ids.includes(r.reportId));
        if (!reports.length) return null;
        return (
          <section key={title} aria-labelledby={'group-' + index}>
            <h2 id={'group-' + index}>{title}</h2>
            <ul className="card-grid">
              {reports.map((report) => (
                <li key={report.reportId} className="card">
                  <Link to={'/reports/' + report.reportId} className="card-title">{report.reportId} — {report.name}</Link>
                  <p className="muted">{report.question}</p>
                  <p className="tag">{report.contour === 'OPERATIONAL' ? 'Оперативный' : 'Аналитический'}</p>
                  <ul className="sources" aria-label="Актуальность источников">
                    {report.sources.map((source) => {
                      const f = bySource.get(source);
                      return (
                        <li key={source} className={f && f.state !== 'FRESH' ? 'stale' : undefined}>
                          {sourceName(source)}: {f ? (f.state === 'FRESH' ? 'актуально' : 'устарело') + ', ' + dateTime(f.dataAsOf) : 'нет данных'}
                        </li>
                      );
                    })}
                  </ul>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      {!visible.length && <Empty>По запросу «{search}» отчётов нет.</Empty>}
      <section aria-labelledby="my-views">
        <h2 id="my-views">Мои представления</h2>
        {viewError && <Failure message={viewError} />}
        {myViews.length ? (
          <ul className="list">
            {myViews.map((view) => (
              <li key={view.viewId}>
                <Link to={`/reports/${view.reportId}?view=${view.viewId}`}>{view.reportId} · {view.name}</Link>
                <button type="button" className="secondary" onClick={() => deleteView(view)}>Удалить</button>
              </li>
            ))}
          </ul>
        ) : <p className="muted">Сохранённых представлений нет. Сохраните параметры на странице отчёта.</p>}
      </section>
    </>
  );
}
