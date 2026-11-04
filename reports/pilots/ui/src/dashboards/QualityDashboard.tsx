import { Link } from 'react-router-dom';
import { Notice } from '../components/State';
import { formatCell } from '../format';
import type { Cell, DimensionValue, ReportQuery, ReportResult } from '../types';
import { Bars, Block, Choice, FreshnessLine, PeriodFields, Tile, num, useDashboardParams, useReport } from './common';

type Defects = { opened?: number; closed?: number; remaining?: number } | null;

/** Difference of a measure to the previous period of the same length (comparison of the report API). */
function delta(data: ReportResult, key: string): number | null {
  const now = num(data.totals[key]);
  const before = num(data.comparison?.totals?.[key]);
  return now !== null && before !== null ? Math.round((now - before) * 100) / 100 : null;
}

// SCR-06 (US-QA-01, -02, -04, US-AN-04): R-07 test results, R-09 quality ratios, R-05 defect flow, R-08 severity × status.
export function QualityDashboard() {
  const { from, to, value: project, set, valid, param } = useDashboardParams('project');
  const iteration = param('iteration');
  const query = (slice: string[], compare = false): ReportQuery | null => project && valid
    ? { params: { periodFrom: from, periodTo: to, projectIds: [project], ...(iteration ? { iterationIds: [iteration] } : {}) }, slice, compareWithPrevious: compare }
    : null;
  const tests = useReport('R-07', query(['project'], true));
  const ratios = useReport('R-09', query(['project'], true));
  const flow = useReport('R-05', query(['week']));
  const matrix = useReport('R-08', query(['severity', 'status']));

  return (
    <>
      <nav aria-label="Путь" className="breadcrumbs"><Link to="/dashboards">Дашборды</Link> › Качество</nav>
      <h1>Дашборд качества</h1>
      <form className="dashboard-filters" aria-label="Параметры дашборда" onSubmit={(e) => e.preventDefault()}>
        <Choice reportId="R-07" slice="project" label="Проект" from={from} to={to} value={project} onChange={(id) => set({ project: id, iteration: '' })} />
        <Choice reportId="R-07" slice="iteration" label="Итерация" optional from={from} to={to} value={iteration} onChange={(id) => set({ iteration: id })} />
        <PeriodFields from={from} to={to} onChange={set} />
      </form>
      {!project ? <Notice tone="info">Выберите проект; итерация — по желанию.</Notice> : (
        <>
          <FreshnessLine reports={[tests, ratios, flow, matrix]} />
          <Block report={tests}>{(data) => !data.rows.length ? <Notice tone="info">Нет данных тестирования: у выбранного проекта или итерации нет тест-планов за период.</Notice> : (
            <>
              <dl className="totals">
                <Tile title="Pass rate, %" value={formatCell(data.totals['M-14'])} delta={delta(data, 'M-14')} />
                <Tile title="Выполнение плана, %" value={formatCell(data.totals['M-15'])} delta={delta(data, 'M-15')} />
                <Block report={ratios}>{(r) => (
                  <>
                    <Tile title="Плотность дефектов" value={r.totals['M-16'] === null ? 'не утверждена' : formatCell(r.totals['M-16'])}
                      note={r.totals['M-16'] === null ? `Методика Q-REP-12 не согласована; кандидат: ${formatCell(r.totals.candidateDefectDensity)}` : undefined}
                      delta={delta(r, 'M-16')} />
                    <Tile title="Reopened rate, %" value={formatCell(r.totals['M-17'])} delta={delta(r, 'M-17')} />
                  </>
                )}</Block>
              </dl>
              <h2>Результаты кейсов</h2>
              <Bars title="Результаты тест-кейсов" points={[['Успешно', 'passed'], ['С ошибкой', 'failed'], ['Заблокировано', 'blocked'], ['Пропущено', 'skipped']]
                .map(([name, key]) => ({ label: name, value: num(data.totals[key]) }))} />
            </>
          )}</Block>
          <h2>Динамика дефектов</h2>
          {iteration && <p className="muted">С фильтром по итерации учитываются только дефекты, связанные с итерацией через тест-план.</p>}
          <Block report={flow}>{(data) => (
            <Bars title="Остаток дефектов по ISO-неделям"
              points={data.rows.map((r) => ({ label: `${(r.week as DimensionValue).label}: +${formatCell((r['M-12'] as Defects)?.opened ?? 0)} / −${formatCell((r['M-12'] as Defects)?.closed ?? 0)}`, value: (r['M-12'] as Defects)?.remaining ?? null }))} />
          )}</Block>
          <h2>Серьёзность × статус</h2>
          <Block report={matrix}>{(data) => <Matrix data={data} />}</Block>
        </>
      )}
    </>
  );
}

function Matrix({ data }: { data: ReportResult }) {
  const cell = (r: Record<string, Cell>, key: string) => (r[key] as DimensionValue).label;
  const severities = [...new Set(data.rows.map((r) => cell(r, 'severity')))];
  const statuses = [...new Set(data.rows.map((r) => cell(r, 'status')))];
  if (!data.rows.length) return <p className="muted">Дефектов за период нет.</p>;
  const count = (s: string, t: string) => (data.rows.find((r) => cell(r, 'severity') === s && cell(r, 'status') === t)?.['M-12'] as Defects)?.opened ?? 0;
  return (
    <div className="table-scroll" tabIndex={0}>
      <table>
        <caption>Дефекты, созданные за период: серьёзность × текущий статус</caption>
        <thead><tr><th scope="col">Серьёзность</th>{statuses.map((t) => <th key={t} scope="col" className="num">{t}</th>)}</tr></thead>
        <tbody>{severities.map((s) => <tr key={s}><th scope="row">{s}</th>{statuses.map((t) => <td key={t} className="num">{count(s, t)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
