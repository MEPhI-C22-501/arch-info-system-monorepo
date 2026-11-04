import { Link } from 'react-router-dom';
import { Notice } from '../components/State';
import { formatCell } from '../format';
import type { DimensionValue, ReportQuery } from '../types';
import { Bars, Block, Choice, FreshnessLine, PeriodFields, Tile, num, useAutoRefresh, useDashboardParams, useReport } from './common';

// SCR-04 (US-TL-02): R-03 tasks by status, R-04 overdue tasks, R-10 completions by week, for one iteration.
export function IterationDashboard() {
  const { from, to, value: iteration, set, valid } = useDashboardParams('iteration');
  const query = (slice: string): ReportQuery | null =>
    iteration && valid ? { params: { periodFrom: from, periodTo: to, iterationIds: [iteration] }, slice: [slice] } : null;
  const statuses = useReport('R-03', query('status'));
  const overdue = useReport('R-04', query('record'));
  const flow = useReport('R-10', query('iteration'));
  useAutoRefresh([statuses, overdue, flow], Boolean(iteration));

  return (
    <>
      <nav aria-label="Путь" className="breadcrumbs"><Link to="/dashboards">Дашборды</Link> › Итерация</nav>
      <h1>Оперативный дашборд итерации</h1>
      <form className="dashboard-filters" aria-label="Параметры дашборда" onSubmit={(e) => e.preventDefault()}>
        <Choice reportId="R-03" slice="iteration" label="Итерация" from={from} to={to} value={iteration} onChange={(id) => set({ iteration: id })} />
        <PeriodFields from={from} to={to} onChange={set} />
      </form>
      {!iteration ? <Notice tone="info">Выберите итерацию: в списке итерации, по которым есть задачи за период в вашей области.</Notice> : (
        <>
          <FreshnessLine reports={[statuses, overdue, flow]} />
          <p className="muted">Обновляется автоматически раз в минуту.</p>
          <Block report={statuses}>{(data) => {
            const rows = data.rows.map((r) => ({ name: (r.status as DimensionValue).label, count: num(r.taskCount) ?? 0, done: num(r['M-06']) }));
            const completed = rows.filter((r) => r.done === 100).reduce((s, r) => s + r.count, 0);
            const open = rows.filter((r) => r.done === 0).reduce((s, r) => s + r.count, 0);
            return (
              <>
                <dl className="totals">
                  <Tile title="Задач всего" value={formatCell(data.totals.taskCount)} />
                  <Tile title="Не завершено" value={formatCell(open)} note="Статусы, не относящиеся к завершённым" />
                  <Tile title="Завершено" value={formatCell(completed)} note={`${formatCell(data.totals['M-06'])} %`} />
                  <Block report={overdue}>{(late) => <Tile title="Просрочено" value={formatCell(late.totals['M-05'])}
                    note={`дней просрочки: ${formatCell(late.totals.overdueDays)}; без срока: ${formatCell(late.totals.missingDueDates)}`} />}</Block>
                  <Tile title="Остаток, ч" value={formatCell(data.totals['M-03'])} />
                </dl>
                <h2>Доска по статусам</h2>
                <ul className="board">{rows.map((r) => <li key={r.name}><span>{r.name}</span><strong>{r.count}</strong></li>)}</ul>
              </>
            );
          }}</Block>
          <h2>Просроченные задачи</h2>
          <Block report={overdue}>{(data) => {
            const late = data.rows.filter((r) => (num(r['M-05']) ?? 0) > 0);
            return !late.length ? <p className="muted">Просроченных задач нет.</p> : (
              <ul className="list">{late.map((r, i) => <li key={i}><span>{(r.record as DimensionValue).label}</span><span>просрочка {formatCell(r.overdueDays)} дн.</span></li>)}</ul>
            );
          }}</Block>
          <h2>Завершено по неделям</h2>
          <Block report={flow}>{(data) => {
            const weeks = (data.totals['M-19'] as { throughput?: Record<string, number> } | null)?.throughput ?? {};
            return <Bars title="Завершённые задачи по ISO-неделям" points={Object.entries(weeks).sort().map(([label, value]) => ({ label, value }))} />;
          }}</Block>
        </>
      )}
    </>
  );
}
