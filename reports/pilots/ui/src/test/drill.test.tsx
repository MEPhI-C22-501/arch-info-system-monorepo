import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { nextSlice, readDrill, writeDrill } from '../drill';
import { Exports } from '../pages/Exports';
import { ReportPage } from '../pages/ReportPage';
import { mockApi, renderAt } from './helpers';

const R01 = ['project', 'unit', 'role', 'employee', 'iteration', 'epic', 'week', 'month', 'record'];
const definition = { reportId: 'R-01', name: 'Трудозатраты', question: '?', contour: 'ANALYTICAL', sources: ['task-tracker'], version: 1,
  slices: ['project', 'employee', 'record'], measures: [{ key: 'M-01', title: 'Факт, ч', formula: 'SUM(hours)' }] };
const fresh = { source: 'task-tracker', stream: 'reports', dataAsOf: '2026-10-31T09:00:00Z', lagSeconds: 30, thresholdSeconds: 3600, state: 'FRESH' };
const columns = (...dims: string[]) => [...dims.map((key) => ({ key, title: key, type: 'dimension' })), { key: 'M-01', title: 'Факт, ч', type: 'measure' }];
const result = (rows: object[], ...dims: string[]) => ({ reportId: 'R-01', columns: columns(...dims), rows, totals: { 'M-01': 11.25 }, notes: [], freshness: [fresh], comparison: null });
/** Body of the latest POST to the path (optionally the one that matches). */
const body = (fetch: ReturnType<typeof mockApi>, path: string, match: (b: any) => boolean = () => true) =>
  [...fetch.mock.calls].reverse().filter(([url, init]) => String(url).endsWith(path) && init?.method === 'POST')
    .map(([, init]) => JSON.parse(String(init?.body))).find(match);

describe('drill levels', () => {
  it('go down the report slices and stop after the source records', () => {
    expect(nextSlice(R01, ['project'])).toBe('unit');
    expect(nextSlice(R01, ['project', 'unit', 'role', 'employee'])).toBe('iteration');
    expect(nextSlice(R01, ['week'])).toBe('record');
    expect(nextSlice(R01, ['project', 'record'])).toBeNull();
  });
  it('survive the address bar and ignore anything malformed', () => {
    const path = [{ slice: 'project', id: 'p-1' }, { slice: 'employee', id: null }];
    expect(readDrill(writeDrill(path))).toEqual(path);
    expect(readDrill('not json')).toEqual([]);
    expect(readDrill('[[1,2],["project","p"]]')).toEqual([{ slice: 'project', id: 'p' }]);
  });
});

describe('SCR-03 drill-down', () => {
  const open = (drill: [number, unknown]) => {
    const fetch = mockApi({
      'reports/R-01': [200, definition],
      'reports/R-01/query': [200, result([{ project: { id: 'p-1', label: 'Проект А' }, 'M-01': 11.25 }], 'project')],
      'reports/R-01/drilldown': drill,
    });
    renderAt(<ReportPage />, ['reports-analyst'], '/reports/R-01?from=2026-10-01&to=2026-10-31&slice=project', '/reports/:reportId');
    return fetch;
  };
  it('opens the next level of the clicked row with breadcrumbs', async () => {
    const fetch = open([200, result([
      { project: { id: 'p-1', label: 'Проект А' }, employee: { id: 'u-1', label: 'Иванова Анна' }, 'M-01': 3.75 },
      { project: { id: 'p-1', label: 'Проект А' }, employee: { id: 'u-2', label: 'Петров Игорь' }, 'M-01': 7.5 },
    ], 'project', 'employee')]);
    await userEvent.click(await screen.findByRole('button', { name: 'Детализировать: Проект А' }));
    const panel = await screen.findByRole('complementary', { name: 'Детализация: Сотрудник' });
    expect(await within(panel).findByText('Проект: Проект А')).toBeInTheDocument();
    expect(body(fetch, '/drilldown')).toEqual({ params: { periodFrom: '2026-10-01', periodTo: '2026-10-31' }, slice: ['project', 'employee'],
      compareWithPrevious: false, path: [{ slice: 'project', id: 'p-1' }] });
    const table = within(panel).getByRole('table');
    expect(within(table).queryByRole('columnheader', { name: 'project' })).not.toBeInTheDocument();
    await userEvent.click(within(table).getByRole('button', { name: 'Детализировать: Иванова Анна' }));
    expect(body(fetch, '/drilldown').path).toEqual([{ slice: 'project', id: 'p-1' }, { slice: 'employee', id: 'u-1' }]);
    expect(body(fetch, '/drilldown').slice).toEqual(['project', 'employee', 'record']);
    await userEvent.click(within(panel).getByRole('button', { name: 'Итог' }));
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });
  it('says the level is closed for the role and keeps the aggregate', async () => {
    open([403, { code: 'FORBIDDEN' }]);
    await userEvent.click(await screen.findByRole('button', { name: 'Детализировать: Проект А' }));
    expect(await screen.findByText(/Детализация до уровня «Сотрудник» недоступна для вашей роли/)).toBeInTheDocument();
    expect(screen.getByRole('table', { name: /R-01: Трудозатраты/ })).toBeInTheDocument();
  });
});

describe('filters by name', () => {
  it('lists the scope values for the period and sends their ids', async () => {
    const fetch = mockApi({
      'reports/R-01': [200, definition],
      'reports/R-01/query': [200, result([], 'project')],
      'reports/R-01/options': [200, { items: [{ id: 'p-1', label: 'Проект А' }, { id: 'p-2', label: 'Проект Б' }] }],
    });
    renderAt(<ReportPage />, ['reports-analyst'], '/reports/R-01?from=2026-10-01&to=2026-10-31&slice=project', '/reports/:reportId');
    await userEvent.click(await screen.findByText('Фильтры'));
    const projects = await screen.findByRole('group', { name: 'Проекты' });
    await userEvent.click(await within(projects).findByLabelText('Проект Б'));
    expect(body(fetch, '/options', (b) => b.slice[0] === 'project')).toEqual({ params: { periodFrom: '2026-10-01', periodTo: '2026-10-31' }, slice: ['project'] });
    await userEvent.click(screen.getByRole('button', { name: 'Сформировать' }));
    await screen.findByText(/проекты: выбрано 1/);
    expect(body(fetch, '/query').params.projectIds).toEqual(['p-2']);
  });
});

describe('SCR-08 exports', () => {
  it('shows the parameters and queues a failed job again', async () => {
    const query = { params: { periodFrom: '2026-10-01', periodTo: '2026-10-31' }, slice: ['employee'] };
    const fetch = mockApi({
      exports: [200, { items: [{ exportId: 'e-1', reportId: 'R-01', format: 'xlsx', status: 'FAILED', createdAt: '2026-11-01T09:00:00Z',
        expiresAt: null, rowCount: null, error: 'SOURCE_NOT_LOADED', query }] }],
      'POST exports': [202, { exportId: 'e-2', status: 'QUEUED' }],
    });
    renderAt(<Exports />, ['reports-analyst']);
    expect(await screen.findByText('период 2026-10-01 — 2026-10-31, разрез «Сотрудник»')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(body(fetch, '/exports')).toEqual({ reportId: 'R-01', query, format: 'xlsx' });
  });
});
