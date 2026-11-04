import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { Header } from '../components/Header';
import { Catalog } from '../pages/Catalog';
import { Freshness } from '../pages/Freshness';
import { ReportPage } from '../pages/ReportPage';
import { Subscriptions } from '../pages/Subscriptions';
import { SessionContext } from '../session';
import { mockApi, renderAt, session } from './helpers';

const definition = (reportId: string, name: string) => ({
  reportId, name, question: name + '?', contour: 'ANALYTICAL', sources: ['task-tracker'], version: 1,
  slices: ['project', 'employee'], measures: [{ key: 'M-01', title: 'Факт, ч', formula: 'SUM(hours) за период' }],
});
const fresh = { source: 'task-tracker', stream: 'reports', dataAsOf: '2026-10-31T09:00:00Z', lagSeconds: 30, thresholdSeconds: 3600, state: 'FRESH' };
const result = (overrides = {}) => ({
  reportId: 'R-01',
  columns: [{ key: 'project', title: 'Проект', type: 'dimension' }, { key: 'M-01', title: 'Факт, ч', type: 'measure', formula: 'SUM(hours) за период' }],
  rows: [{ project: { id: 'p-1', label: 'Проект А' }, 'M-01': 11.25 }, { project: { id: null, label: 'не задано' }, 'M-01': 2 }],
  totals: { 'M-01': 13.25 }, notes: [], freshness: [fresh], comparison: null, ...overrides,
});

describe('Header', () => {
  const header = (roles: string[]) => render(
    <SessionContext.Provider value={session(roles)}><MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><Header unread={2} /></MemoryRouter></SessionContext.Provider>,
  );
  it('shows audit only to administrators and announces unread notifications', () => {
    header(['reports-member']);
    expect(screen.queryByRole('link', { name: 'Аудит' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Подписки' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Уведомления, непрочитанных: 2' })).toBeInTheDocument();
  });
  it('gives administrators the audit link', () => {
    header(['reports-admin', 'reports-analyst']);
    expect(screen.getByRole('link', { name: 'Аудит' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Подписки' })).toBeInTheDocument();
  });
});

describe('Catalog', () => {
  it('groups reports and filters by search', async () => {
    mockApi({
      reports: [200, { items: [definition('R-01', 'Трудозатраты'), definition('R-08', 'Дефекты')] }],
      freshness: [200, { items: [fresh] }],
      views: [200, { items: [] }],
    });
    renderAt(<Catalog />, ['reports-analyst']);
    expect(await screen.findByRole('heading', { name: 'Время и ресурсы' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Качество' })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Поиск отчёта'), 'дефект');
    expect(screen.queryByRole('link', { name: /R-01/ })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /R-08/ })).toBeInTheDocument();
  });
  it('tells a user without reports whom to ask', async () => {
    mockApi({ reports: [200, { items: [] }], freshness: [200, { items: [] }], views: [200, { items: [] }] });
    renderAt(<Catalog />, ['reports-member']);
    expect(await screen.findByText(/Вам не назначены отчёты/)).toBeInTheDocument();
  });
});

describe('ReportPage', () => {
  const open = (routes: Record<string, [number, unknown]>) => {
    const fetch = mockApi({ 'reports/R-01': [200, definition('R-01', 'Трудозатраты')], ...routes });
    renderAt(<ReportPage />, ['reports-analyst'], '/reports/R-01?from=2026-10-01&to=2026-10-31&slice=project', '/reports/:reportId');
    return fetch;
  };
  it('shows totals, a table with formulas and the missing value in italics', async () => {
    open({ 'reports/R-01/query': [200, result()] });
    const table = await screen.findByRole('table', { name: /R-01/ });
    expect(within(table).getByText('Проект А')).toBeInTheDocument();
    expect(within(table).getByText('не задано').closest('td')).toHaveClass('not-set');
    expect(within(table).getByRole('note', { name: 'Формула: SUM(hours) за период' })).toBeInTheDocument();
    expect(screen.getAllByText('13,25').length).toBeGreaterThan(0);
  });
  it('warns when a source is stale and switches to the chart', async () => {
    open({ 'reports/R-01/query': [200, result({ freshness: [{ ...fresh, state: 'STALE' }] })] });
    expect(await screen.findByText(/Данные источника «Трекер задач» актуальны на 31\.10\.2026, 12:00 МСК, задержка 30 с/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'График' }));
    expect(screen.getByRole('img', { name: /Факт, ч по разрезу/ })).toBeInTheDocument();
  });
  it('explains 403 without retry and empty results with a message', async () => {
    open({ 'reports/R-01/query': [403, { code: 'FORBIDDEN' }] });
    expect(await screen.findByText(/Нет доступа к выбранному проекту/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument();
  });
  it('says when there is no data', async () => {
    open({ 'reports/R-01/query': [200, result({ rows: [], notes: ['NO_DATA'] })] });
    expect(await screen.findByText('По заданным параметрам данных нет: период 2026-10-01 — 2026-10-31, разрез «Проект».')).toBeInTheDocument();
  });
  it('offers a file when the result is too large for the screen', async () => {
    const fetch = open({ 'reports/R-01/query': [422, { code: 'RESULT_TOO_LARGE' }], exports: [202, { exportId: 'e-1' }] });
    expect(await screen.findByText(/Результат слишком большой для экрана/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Выгрузить XLSX' }));
    expect(await screen.findByText(/Выгрузка XLSX поставлена в очередь/)).toBeInTheDocument();
    const [, init] = fetch.mock.calls.find(([url]) => String(url).endsWith('/exports'))!;
    expect(JSON.parse(String(init?.body))).toMatchObject({ reportId: 'R-01', format: 'xlsx', query: { slice: ['project'] } });
  });
  it('marks an overrun with a plus sign, not by colour alone', async () => {
    open({ 'reports/R-01/query': [200, result({
      columns: [{ key: 'project', title: 'Проект', type: 'dimension' }, { key: 'M-04', title: 'Перерасход, ч', type: 'measure' }],
      rows: [{ project: { id: 'p-1', label: 'Проект А' }, 'M-04': 1.25 }], totals: { 'M-04': 1.25 },
    })] });
    const cell = await screen.findByText((_, element) => element?.tagName === 'TD' && (element.textContent ?? '').startsWith('+1,25'));
    expect(cell).toHaveClass('overrun');
    expect(within(cell).getByText('(перерасход)')).toBeInTheDocument();
  });
});

describe('Freshness', () => {
  it('lists streams and says when a source was never loaded', async () => {
    mockApi({ freshness: [200, { items: [fresh, { source: 'qa-system', stream: 'reports', dataAsOf: null, lagSeconds: null, thresholdSeconds: 3600, state: 'UNKNOWN' }] }] });
    renderAt(<Freshness />, ['reports-admin']);
    const rows = await screen.findAllByRole('row');
    expect(within(rows[1]).getByText('Актуально')).toBeInTheDocument();
    expect(within(rows[2]).getByText('Нет данных', { selector: 'td.status' })).toBeInTheDocument();
  });
});

describe('Subscriptions', () => {
  it('takes the parameters of a saved view', async () => {
    const view = { viewId: 'v-1', reportId: 'R-01', name: 'Команда А', createdAt: '2026-11-01T09:00:00Z',
      query: { params: { periodFrom: '2026-09-01', periodTo: '2026-09-30', projectIds: ['p-1'] }, slice: ['employee'] } };
    const fetch = mockApi({
      subscriptions: [200, { items: [] }],
      'POST subscriptions': [201, { subscriptionId: 's-1' }],
      reports: [200, { items: [definition('R-01', 'Трудозатраты')] }],
      views: [200, { items: [view] }],
    });
    renderAt(<Subscriptions />, ['reports-analyst']);
    await userEvent.selectOptions(await screen.findByLabelText('Параметры'), 'Представление «Команда А»');
    expect(screen.getByText(/Период 2026-09-01 — 2026-09-30, разрез «Сотрудник»/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Создать подписку' }));
    const [, init] = fetch.mock.calls.find(([url, request]) => String(url).endsWith('/subscriptions') && request?.method === 'POST')!;
    expect(JSON.parse(String(init?.body))).toMatchObject({ reportId: 'R-01', query: view.query, schedule: '0 9 * * 1', format: 'xlsx' });
  });
});
