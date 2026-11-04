import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Freshness } from '../pages/Freshness';
import { mockApi, renderAt } from './helpers';

const streams = { items: [
  { source: 'task-tracker', stream: 'reports', dataAsOf: '2026-11-04T09:00:00Z', lagSeconds: 30, thresholdSeconds: 3600, state: 'FRESH' },
  { source: 'qa-system', stream: 'reports', dataAsOf: '2026-11-04T08:00:00Z', lagSeconds: 4000, thresholdSeconds: 3600, state: 'STALE' },
] };
const batches = { total: 2, items: [
  { batchId: 'b-2', source: 'task-tracker', status: 'LOADED', startedAt: '2026-11-04T09:00:00Z', finishedAt: '2026-11-04T09:00:05Z', rows: 13, error: null },
  { batchId: 'b-1', source: 'qa-system', status: 'REJECTED', startedAt: '2026-11-04T08:30:00Z', finishedAt: '2026-11-04T08:30:02Z', rows: null, error: 'SOURCE_LOAD_IN_PROGRESS' },
] };
const checks = { total: 1, items: [
  { reconciliationId: 'r-1', source: 'task-tracker', entity: 'work-items', sourceCount: 2, dwhCount: 2, missing: 0, extra: 0, mode: 'SOURCE', result: 'MATCH', checkedAt: '2026-11-04T09:00:05Z' },
] };
const journal = (loads: object[] = []) => ({
  freshness: [200, streams] as [number, unknown], 'etl/batches': [200, batches] as [number, unknown],
  'etl/reconciliations': [200, checks] as [number, unknown], 'GET etl/loads': [200, { items: loads }] as [number, unknown],
});

describe('SCR-10 freshness and ETL journal', () => {
  it('shows only the stream table to a business role and asks nothing of the ETL API', async () => {
    const fetch = mockApi({ freshness: [200, streams] });
    renderAt(<Freshness />, ['reports-member']);
    expect(await screen.findByRole('table', { name: 'Потоки данных' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Журнал пакетов' })).not.toBeInTheDocument();
    expect(fetch.mock.calls.some(([url]) => String(url).includes('/etl/'))).toBe(false);
  });
  it('gives the analyst the journal and the last batch and check of each source, without manual load', async () => {
    mockApi(journal());
    renderAt(<Freshness />, ['reports-analyst']);
    const table = await screen.findByRole('table', { name: 'Потоки данных' });
    expect(await within(table).findByText(/Загружен, 04\.11\.2026/)).toBeInTheDocument();
    expect(within(table).getByText(/Отклонён, 04\.11\.2026/)).toBeInTheDocument();
    expect(within(table).getByText(/Совпадает, 04\.11\.2026/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Обновить из источника/ })).not.toBeInTheDocument();
    const journalTable = await screen.findByRole('table', { name: /Пакеты загрузки/ });
    expect(within(journalTable).getByText('SOURCE_LOAD_IN_PROGRESS')).toBeInTheDocument();
    expect(within(journalTable).getByText('13')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: /Сверки/ })).toBeInTheDocument();
  });
  it('lets the administrator queue a load and says when one already waits', async () => {
    const fetch = mockApi({ ...journal(), 'POST etl/loads': [202, { source: 'qa-system', requestedAt: '2026-11-04T09:10:00Z', reason: 'MANUAL_LOAD', status: 'PENDING' }] });
    renderAt(<Freshness />, ['reports-admin']);
    await userEvent.click(await screen.findByRole('button', { name: 'Обновить из источника: Тестирование' }));
    expect(await screen.findByText(/Заявка принята: данные «Тестирование» перечитает ближайший цикл/)).toBeInTheDocument();
    const post = fetch.mock.calls.find(([url, init]) => String(url).endsWith('/etl/loads') && init?.method === 'POST')!;
    expect(JSON.parse(String(post[1]?.body))).toEqual({ source: 'qa-system' });
    mockApi({ ...journal(), 'POST etl/loads': [409, { code: 'LOAD_ALREADY_REQUESTED' }] });
    await userEvent.click(screen.getByRole('button', { name: 'Обновить из источника: Трекер задач' }));
    expect(await screen.findByText('Обновление «Трекер задач» уже ждёт выполнения.')).toBeInTheDocument();
  });
  it('shows a waiting request and disables the button of that source', async () => {
    mockApi(journal([{ source: 'qa-system', requestedAt: '2026-11-04T09:10:00Z', reason: 'MANUAL_LOAD', status: 'PENDING' }]));
    renderAt(<Freshness />, ['reports-admin']);
    expect(await screen.findByRole('button', { name: 'Обновить из источника: Тестирование' })).toBeDisabled();
    expect(screen.getByText(/Тестирование · вручную/)).toBeInTheDocument();
    expect(screen.getByText('Ждёт загрузки', { selector: '.list span' })).toBeInTheDocument();
  });
  it('says what changed when the sent request is done', async () => {
    const request = { source: 'task-tracker', requestedAt: '2026-11-04T09:10:00Z', reason: 'MANUAL_LOAD', status: 'PENDING' };
    // The list reloaded after the POST already reports the request done.
    mockApi({ ...journal([{ ...request, status: 'COMPLETED' }]), 'POST etl/loads': [202, request] });
    renderAt(<Freshness />, ['reports-admin']);
    expect(await screen.findByText(/Файл при этом не скачивается/)).toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Обновить из источника: Трекер задач' }));
    expect(await screen.findByText(/Данные «Трекер задач» обновлены из источника: пакет 04\.11\.2026, 12:00 МСК, записей 13\./)).toBeInTheDocument();
  });
});
