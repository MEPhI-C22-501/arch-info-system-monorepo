import { afterEach, expect, test, vi } from 'vitest';
import { clearSession, saveSession } from '../session';
import { mockFetch } from '../test/helpers';
import { ApiError, loadAll, request, withQuery } from './client';

afterEach(() => clearSession());

test('запрос несёт демо-токен выбранной роли и имени', async () => {
  saveSession({ role: 'qa-lead', name: 'ivanov' });
  const calls = mockFetch(() => ({ body: { ok: true } }));
  await expect(request('GET', '/runs')).resolves.toEqual({ ok: true });
  expect(calls[0].url).toBe('/api/v1/runs');
  expect(calls[0].headers.Authorization).toBe('Bearer demo-qa-lead@ivanov');
  expect(calls[0].headers['Content-Type']).toBeUndefined();
});

test('тело уходит JSON, а дополнительные заголовки добавляются', async () => {
  saveSession({ role: 'qa-tester', name: 'petrov' });
  const calls = mockFetch(() => ({ status: 201, body: {} }));
  await request('POST', '/runs', { environment: 'dev' }, { 'Idempotency-Key': 'abc' });
  expect(calls[0].body).toEqual({ environment: 'dev' });
  expect(calls[0].headers['Content-Type']).toBe('application/json');
  expect(calls[0].headers['Idempotency-Key']).toBe('abc');
});

test('ошибка разбирается в код, сообщение и перечень причин', async () => {
  saveSession({ role: 'qa-admin', name: 'root' });
  mockFetch(() => ({
    status: 409,
    body: { code: 'VALUE_IN_USE', message: 'используется', correlationId: 'req-1', errors: [{ field: 'isActive', reason: 'used-by:case:TC-RM-01' }] },
  }));
  const error = await request('PUT', '/admin/classifiers/PRIORITY/HIGH', {}).catch((failure) => failure);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({
    status: 409, code: 'VALUE_IN_USE', message: 'используется', correlationId: 'req-1',
    errors: [{ field: 'isActive', reason: 'used-by:case:TC-RM-01' }],
  });
});

test('ответ не в формате API превращается в ошибку с кодом статуса', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>Bad Gateway</html>', { status: 502 })));
  await expect(request('GET', '/runs')).rejects.toMatchObject({ status: 502, code: 'HTTP_502' });
});

test('недоступный сервер — NETWORK_ERROR, а не необработанное исключение', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('failed'); }));
  await expect(request('GET', '/runs')).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
});

test('401 завершает сессию и сообщает приложению', async () => {
  saveSession({ role: 'qa-lead', name: 'ivanov' });
  mockFetch(() => ({ status: 401, body: { code: 'UNAUTHENTICATED', message: 'нет', errors: [] } }));
  const expired = vi.fn();
  window.addEventListener('qa:session-expired', expired);
  await expect(request('GET', '/runs')).rejects.toMatchObject({ code: 'UNAUTHENTICATED' });
  window.removeEventListener('qa:session-expired', expired);
  expect(expired).toHaveBeenCalledOnce();
  expect(localStorage.getItem('qa.session')).toBeNull();
});

test('204 не разбирается как JSON', async () => {
  mockFetch(() => ({ status: 204 }));
  await expect(request('DELETE', '/test-plans/1/cases/2')).resolves.toBeUndefined();
});

test('withQuery пропускает пустые значения и сохраняет false', () => {
  expect(withQuery('/test-cases', { module: 'RM', q: '', status: undefined, automated: false, page: null })).toBe('/test-cases?module=RM&automated=false');
  expect(withQuery('/test-cases', {})).toBe('/test-cases');
});

test('loadAll проходит все страницы', async () => {
  const fetchPage = vi.fn(async (page: number) => ({ items: [page], page, pageSize: 1, totalPages: 3 }));
  await expect(loadAll(fetchPage)).resolves.toEqual([1, 2, 3]);
});
