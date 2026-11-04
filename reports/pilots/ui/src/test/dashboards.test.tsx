import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Dashboards } from '../dashboards/Dashboards';
import { IterationDashboard } from '../dashboards/IterationDashboard';
import { PlanFactDashboard } from '../dashboards/PlanFactDashboard';
import { QualityDashboard } from '../dashboards/QualityDashboard';
import { mockApi, renderAt } from './helpers';

const fresh = { source: 'task-tracker', stream: 'reports', dataAsOf: '2026-10-31T09:00:00Z', lagSeconds: 30, thresholdSeconds: 3600, state: 'FRESH' };
const report = (reportId: string, rows: object[], totals: object, extra: object = {}) =>
  ({ reportId, columns: [], rows, totals, notes: [], freshness: [fresh], comparison: null, ...extra });
const tile = (title: string) => screen.getByText(title, { selector: 'dt' }).parentElement!;
const options = [200, { items: [{ id: 'x-1', label: 'Выбранное' }] }] as [number, unknown];
const period = '?from=2026-10-01&to=2026-10-31';
const posted = (fetch: ReturnType<typeof mockApi>, path: string) => fetch.mock.calls
  .filter(([url, init]) => String(url).endsWith(path) && init?.method === 'POST').map(([, init]) => JSON.parse(String(init?.body)));

describe('Dashboards', () => {
  it('lists the dashboards of the readable reports and Superset only for the analyst', async () => {
    mockApi({ reports: [200, { items: [{ reportId: 'R-03' }, { reportId: 'R-07' }] }] });
    renderAt(<Dashboards />, ['reports-qa-lead']);
    expect(await screen.findByRole('link', { name: 'Оперативный дашборд итерации' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Качество' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'План-факт' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Исследование куба в Superset' })).not.toBeInTheDocument();
  });
  it('gives the analyst the Superset explore link', async () => {
    mockApi({ reports: [200, { items: [{ reportId: 'R-06' }] }] });
    renderAt(<Dashboards />, ['reports-analyst']);
    expect(await screen.findByRole('link', { name: 'Новый срез куба' })).toHaveAttribute('href', 'http://localhost:8088/chart/add');
  });
});

describe('SCR-04 iteration', () => {
  it('asks to choose an iteration first and requests nothing else', async () => {
    const fetch = mockApi({ 'reports/R-03/options': options });
    renderAt(<IterationDashboard />, ['reports-team-lead'], '/' + period);
    expect(await screen.findByText(/Выберите итерацию/)).toBeInTheDocument();
    expect(posted(fetch, '/query')).toEqual([]);
  });
  it('counts tasks by status, overdue tasks and completions of the iteration', async () => {
    const fetch = mockApi({
      'reports/R-03/options': options,
      'reports/R-03/query': [200, report('R-03', [
        { status: { id: 's-1', label: 'Done' }, taskCount: 1, 'M-06': 100 },
        { status: { id: 's-2', label: 'In progress' }, taskCount: 2, 'M-06': 0 },
      ], { taskCount: 3, 'M-06': 33.33, 'M-03': 12.5 })],
      'reports/R-04/query': [200, report('R-04', [{ record: { id: 't-1', label: 'Срочная задача' }, 'M-05': 1, overdueDays: 4 }],
        { 'M-05': 1, overdueDays: 4, missingDueDates: 0 })],
      'reports/R-10/query': [200, report('R-10', [], { 'M-19': { throughput: { '2026-W41': 2, '2026-W40': 1 } } })],
    });
    renderAt(<IterationDashboard />, ['reports-team-lead'], '/' + period + '&iteration=x-1');
    expect(await within(await screen.findByText('Задач всего', { selector: 'dt' }).then((e) => e.parentElement!)).findByText('3')).toBeInTheDocument();
    expect(within(tile('Не завершено')).getByText('2')).toBeInTheDocument();
    expect(within(tile('Завершено')).getByText('1')).toBeInTheDocument();
    expect(within(await screen.findByText('Просрочено', { selector: 'dt' }).then((e) => e.parentElement!)).getByText('1')).toBeInTheDocument();
    expect(screen.getByText('Срочная задача')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Завершённые задачи по ISO-неделям' })).toBeInTheDocument();
    expect(posted(fetch, 'R-03/query')[0].params.iterationIds).toEqual(['x-1']);
    expect(screen.getByText(/Обновляется автоматически раз в минуту/)).toBeInTheDocument();
  });
});

describe('SCR-05 plan-fact', () => {
  it('marks a partial forecast, a zero pace and shows the budget in hours without cost rights', async () => {
    mockApi({
      'reports/R-06/options': options,
      'reports/R-06/query': [200, report('R-06', [{}], { 'M-01': 11.25, 'M-02': 10, 'M-03': -1.25, 'M-04': 1.25, 'M-07': 0, 'M-08': null,
        crossCheckFinish: null, quality: 'PARTIAL', missingInputs: ['RATE'] })],
      'reports/R-03/query': [200, report('R-03', [{}], { 'M-06': 100 })],
      'reports/R-01/query': [200, report('R-01', [{ week: { id: '2026-W40', label: '2026-W40' }, 'M-01': 7.5 }], { 'M-01': 7.5 })],
    });
    renderAt(<PlanFactDashboard />, ['reports-project-manager'], '/' + period + '&project=x-1');
    expect(await screen.findByText('неполные входы: Ставка')).toBeInTheDocument();
    expect(screen.getByText('темп 0 — не рассчитывается')).toBeInTheDocument();
    expect(within(tile('Перерасход, ч')).getByText('без права на деньги — в часах')).toBeInTheDocument();
    const progress = screen.getByRole('img', { name: /Факт за период от плана: 11,25 ч из 10 ч — 112,5 %/ });
    expect(progress).toBeInTheDocument();
    expect(screen.getByText(/сверх плана на 1,25 ч/)).toBeInTheDocument();
    expect(await screen.findByRole('img', { name: 'Факт, ч по ISO-неделям' })).toBeInTheDocument();
    expect(screen.getByText('Полоса — доля плана проекта (10 ч), выработанная за неделю.')).toBeInTheDocument();
  });
});

describe('SCR-06 quality', () => {
  it('says when there is no testing data', async () => {
    mockApi({ 'reports/R-07/options': options, 'reports/R-07/query': [200, report('R-07', [], {})],
      'reports/R-09/query': [200, report('R-09', [], {})], 'reports/R-05/query': [200, report('R-05', [], {})], 'reports/R-08/query': [200, report('R-08', [], {})] });
    renderAt(<QualityDashboard />, ['reports-qa-lead'], '/' + period + '&project=x-1');
    expect(await screen.findByText(/Нет данных тестирования/)).toBeInTheDocument();
  });
  it('shows the change to the previous period and the severity × status matrix', async () => {
    const fetch = mockApi({
      'reports/R-07/options': options,
      'reports/R-07/query': [200, report('R-07', [{}], { 'M-14': 80, 'M-15': 90, passed: 4, failed: 1, blocked: 0, skipped: 0 },
        { comparison: { periodFrom: '2026-09-01', periodTo: '2026-09-30', totals: { 'M-14': 60, 'M-15': 90 }, delta: null } })],
      'reports/R-09/query': [200, report('R-09', [{}], { 'M-16': null, 'M-17': 25, candidateDefectDensity: 10 })],
      'reports/R-05/query': [200, report('R-05', [{ week: { id: '2026-W40', label: '2026-W40' }, 'M-12': { opened: 2, closed: 1, remaining: 1 } }], {})],
      'reports/R-08/query': [200, report('R-08', [
        { severity: { id: 'MAJOR', label: 'MAJOR' }, status: { id: 'OPEN', label: 'OPEN' }, 'M-12': { opened: 0, closed: 0, remaining: 3 } },
        { severity: { id: 'MAJOR', label: 'MAJOR' }, status: { id: 'CLOSED', label: 'CLOSED' }, 'M-12': { opened: 1, closed: 1, remaining: 0 } },
      ], {})],
    });
    renderAt(<QualityDashboard />, ['reports-qa-lead'], '/' + period + '&project=x-1&iteration=x-1');
    expect(await screen.findByText('+20 к прошлому периоду')).toBeInTheDocument();
    expect(screen.getByText(/Методика Q-REP-12 не согласована; кандидат: 10/)).toBeInTheDocument();
    const matrix = await screen.findByRole('table', { name: /Открытые на конец периода дефекты/ });
    expect(within(matrix).getByRole('cell', { name: '3' })).toBeInTheDocument();
    expect(within(matrix).queryByRole('columnheader', { name: 'CLOSED' })).not.toBeInTheDocument();
    expect(screen.getByText('Результаты тест-кейсов: всего 5')).toBeInTheDocument();
    expect(screen.getByText('Успешно — 4 (80 %)')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Дефекты по ISO-неделям' })).toBeInTheDocument();
    expect(screen.getByText('Открыто на конец недели', { selector: '.legend li' })).toBeInTheDocument();
    expect(screen.getByText('переоткрытые / закрытые')).toBeInTheDocument();
    expect(posted(fetch, 'R-07/query')[0]).toMatchObject({ compareWithPrevious: true, params: { projectIds: ['x-1'], iterationIds: ['x-1'] } });
  });
});
