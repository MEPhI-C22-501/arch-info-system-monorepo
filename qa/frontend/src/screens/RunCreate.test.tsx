import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, test } from 'vitest';
import { mockFetch, page, renderScreen } from '../test/helpers';
import { RunCreate } from './RunCreate';

const suite = { id: 's1', name: 'Приёмка стенда', kind: 'MANUAL', purpose: 'ACCEPTANCE', status: 'ACTIVE', owner: 'x', caseIds: [], caseCount: 25 };
const environment = { id: 'e1', code: 'dev', name: 'Локальный стенд', baseUrls: {}, isActive: true };

function mockSources(onPost: () => { status: number; body: unknown }) {
  return mockFetch(({ method, url }) => {
    if (method === 'POST') return onPost();
    if (url.includes('/suites')) return page([suite]);
    if (url.includes('/test-plans')) return page([]);
    if (url.includes('/admin/environments')) return page([environment]);
    return undefined;
  });
}

test('набор из адреса предвыбран, а запрос запускает прогон на выбранном окружении', async () => {
  const calls = mockSources(() => ({ status: 201, body: { id: 'r1', key: 'RUN-02' } }));
  renderScreen(<RunCreate />, { path: '/runs/new?suiteId=s1', pattern: '/runs/new' });
  await screen.findByRole('option', { name: /Приёмка стенда/ });
  expect((screen.getByLabelText(/^Набор/) as HTMLSelectElement).value).toBe('s1');
  await screen.findByRole('option', { name: /Локальный стенд/ });
  fireEvent.click(screen.getByRole('button', { name: 'Создать прогон' }));
  await screen.findByText('другой экран');
  expect(calls.find((call) => call.method === 'POST')!.body).toEqual({ suiteId: 's1', environment: 'dev', start: true });
});

test('без источника запрос не уходит', async () => {
  const calls = mockSources(() => ({ status: 201, body: {} }));
  renderScreen(<RunCreate />, { path: '/runs/new', pattern: '/runs/new' });
  await screen.findByRole('option', { name: /Локальный стенд/ });
  fireEvent.click(screen.getByRole('button', { name: 'Создать прогон' }));
  expect(await screen.findByText('Выберите набор')).toBeTruthy();
  expect(calls.some((call) => call.method === 'POST')).toBe(false);
});

test('SUITE_ALREADY_RUNNING показывает, какой прогон выполняется', async () => {
  mockSources(() => ({ status: 409, body: { code: 'SUITE_ALREADY_RUNNING', message: 'Набор уже выполняется', errors: [{ field: 'suiteId', reason: 'running:RUN-02' }] } }));
  renderScreen(<RunCreate />, { path: '/runs/new?suiteId=s1', pattern: '/runs/new' });
  await screen.findByRole('option', { name: /Локальный стенд/ });
  fireEvent.click(screen.getByRole('button', { name: 'Создать прогон' }));
  await waitFor(() => expect(screen.getByText('выполняется RUN-02')).toBeTruthy());
});
