import { Link } from 'react-router-dom';
import { ResultTable } from '../components/ResultTable';
import { Notice } from '../components/State';
import { formatCell } from '../format';
import type { DimensionValue, ReportQuery } from '../types';
import { Bars, Block, Choice, FreshnessLine, PeriodFields, Tile, num, useDashboardParams, useReport } from './common';

// SCR-05 (US-PM-01, US-AN-03): R-06 plan-fact and forecast, R-03 completion, R-01 hours by week and by employee, for one project.
export function PlanFactDashboard() {
  const { from, to, value: project, set, valid } = useDashboardParams('project');
  const query = (slice: string): ReportQuery | null =>
    project && valid ? { params: { periodFrom: from, periodTo: to, projectIds: [project] }, slice: [slice] } : null;
  const planFact = useReport('R-06', query('project'));
  const completion = useReport('R-03', query('project'));
  const weeks = useReport('R-01', query('week'));
  const people = useReport('R-01', query('employee'));

  return (
    <>
      <nav aria-label="Путь" className="breadcrumbs"><Link to="/dashboards">Дашборды</Link> › План-факт</nav>
      <h1>Дашборд план-факт</h1>
      <form className="dashboard-filters" aria-label="Параметры дашборда" onSubmit={(e) => e.preventDefault()}>
        <Choice reportId="R-06" slice="project" label="Проект" from={from} to={to} value={project} onChange={(id) => set({ project: id })} />
        <PeriodFields from={from} to={to} onChange={set} />
      </form>
      {!project ? <Notice tone="info">Выберите проект: в списке проекты вашей области.</Notice> : (
        <>
          <FreshnessLine reports={[planFact, completion, weeks]} />
          <Block report={planFact}>{(data) => {
            const t = data.totals;
            const money = data.columns.some((c) => c.key === 'M-09');
            const partial = t.quality === 'PARTIAL';
            const missing = Array.isArray(t.missingInputs) ? (t.missingInputs as string[]).map((v) => formatCell(v)).join(', ') : '';
            return (
              <dl className="totals">
                <Tile title="План, ч" value={formatCell(t['M-02'])} />
                <Tile title="Факт, ч" value={formatCell(t['M-01'])} />
                <Tile title="Остаток, ч" value={formatCell(t['M-03'])} />
                <Block report={completion}>{(c) => <Tile title="Выполнено, %" value={formatCell(c.totals['M-06'])} />}</Block>
                <Tile title="Прогноз Planning System" value={t['M-08'] === null ? 'нет прогноза' : formatCell(t['M-08'])}
                  note={partial ? `неполные входы: ${missing || 'не указаны'}` : t.quality ? 'полные входы' : undefined} />
                <Tile title="Сверочный прогноз" value={num(t['M-07']) ? formatCell(t.crossCheckFinish) : '—'}
                  note={num(t['M-07']) ? `темп ${formatCell(t['M-07'])} ч в неделю` : 'Темп 0: сверочный прогноз не рассчитывается'} />
                {money
                  ? <Tile title="Отклонение бюджета" value={formatCell(t['M-09'])} />
                  : <Tile title="Перерасход, ч" value={formatCell(t['M-04'])} note="Денежные поля недоступны для вашей роли — бюджет в часах" />}
              </dl>
            );
          }}</Block>
          <h2>Факт по неделям</h2>
          <Block report={weeks}>{(data) => (
            <Bars title="Факт, ч по ISO-неделям" unit=" ч"
              points={data.rows.map((r) => ({ label: (r.week as DimensionValue).label, value: num(r['M-01']) }))} />
          )}</Block>
          <h2>По сотрудникам</h2>
          <Block report={people}>{(data) => !data.rows.length ? <p className="muted">Списаний за период нет.</p>
            : <ResultTable result={data} caption="Факт по сотрудникам" />}</Block>
        </>
      )}
    </>
  );
}
