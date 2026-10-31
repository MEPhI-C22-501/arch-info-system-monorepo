const test = require('node:test');
const assert = require('node:assert/strict');
const { createApi, ApiError, buildQuery, parseFilename } = require('../js/api.js');

function response(status, body, headers) {
  const map = new Map(Object.entries(headers || {}));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => map.get(name) || null },
    json: async () => body,
    text: async () => (body === undefined ? '' : JSON.stringify(body)),
    blob: async () => body,
  };
}

function client(handler, options) {
  const calls = [];
  const api = createApi({
    base: '/v1',
    token: async () => 'tok',
    fetch: async (url, init) => { calls.push({ url, init }); return handler(url, init, calls.length); },
    ...(options || {}),
  });
  return { api, calls };
}

test('the query keeps only set parameters and the file name is read from the header', () => {
  assert.equal(buildQuery({ filter: 'a = 1', pageSize: 20, pageToken: '', allowDeleted: false, force: true }), '?filter=a+%3D+1&pageSize=20&force=true');
  assert.equal(buildQuery({}), '');
  assert.equal(parseFilename('attachment; filename="employees.xlsx"', 'x'), 'employees.xlsx');
  assert.equal(parseFilename('attachment; filename=employees.xlsx', 'x'), 'employees.xlsx');
  assert.equal(parseFilename(null, 'fallback.xlsx'), 'fallback.xlsx');
});

test('list sends the contract parameters with the token and unwraps the page', async () => {
  const { api, calls } = client(() => response(200, { employees: [{ id: 1 }], nextPageToken: 'n1' }));
  const page = await api.list('employees', { filter: 'employment_state = "EMPLOYED"', orderBy: 'id desc', pageSize: 50, pageToken: 'p0', allowDeleted: true });
  assert.deepEqual(page, { items: [{ id: 1 }], nextPageToken: 'n1' });
  assert.equal(calls[0].url, '/v1/employees/?filter=employment_state+%3D+%22EMPLOYED%22&order_by=id+desc&pageSize=50&pageToken=p0&allowDeleted=true');
  assert.equal(calls[0].init.method, 'GET');
  assert.equal(calls[0].init.headers.Authorization, 'Bearer tok');
});

test('listAll follows the page tokens', async () => {
  const { api, calls } = client((url) => (url.includes('pageToken=n1')
    ? response(200, { countries: [{ id: 3 }], nextPageToken: '' })
    : response(200, { countries: [{ id: 1 }, { id: 2 }], nextPageToken: 'n1' })));
  const items = await api.listAll('countries', { orderBy: 'id' });
  assert.deepEqual(items.map((i) => i.id), [1, 2, 3]);
  assert.equal(calls.length, 2);
});

test('create, update, delete and the custom methods use the contract paths and bodies', async () => {
  const { api, calls } = client((url, init) => (init.method === 'DELETE' && url.includes('force=true') ? response(204) : response(200, { id: 7 })));
  await api.create('positions', { code: 'qa', name: 'QA' });
  await api.update('positions', 7, { code: 'qa', name: 'QA lead' }, 'name');
  await api.remove('positions', 7);
  assert.equal(await api.remove('positions', 7, true), null);
  await api.dismiss(7, '2026-12-31');
  await api.syncAccount(7);
  await api.getRevision('positions', 7, 2, true);
  assert.deepEqual(calls.map((c) => `${c.init.method} ${c.url}`), [
    'POST /v1/positions/',
    'PATCH /v1/positions/7?updateMask=name',
    'DELETE /v1/positions/7',
    'DELETE /v1/positions/7?force=true',
    'POST /v1/employees/7/dismiss',
    'POST /v1/employees/7/syncAccount',
    'GET /v1/positions/7/revisions/2?allowDeleted=true',
  ]);
  assert.equal(calls[0].init.body, '{"code":"qa","name":"QA"}');
  assert.equal(calls[4].init.body, '{"dismissal_date":"2026-12-31"}');
  assert.equal(calls[5].init.body, undefined);
});

test('an error answer becomes ApiError with the status, the message, the field details and the trace', async () => {
  const { api } = client(() => response(400, { message: 'validation failed', details: [{ field: 'email', message: 'must match' }, { message: 'other' }] }, { 'X-Trace-Id': 't-1' }));
  const error = await api.create('employees', {}).catch((e) => e);
  assert.ok(error instanceof ApiError);
  assert.equal(error.status, 400);
  assert.equal(error.message, 'validation failed');
  assert.deepEqual(error.fieldErrors, { email: 'must match' });
  assert.equal(error.traceId, 't-1');
});

test('401 calls the unauthenticated handler, 429 waits for Retry-After and repeats', async () => {
  let unauthenticated = 0;
  const { api } = client(() => response(401, { message: 'unauthenticated' }), { onUnauthenticated: () => { unauthenticated += 1; } });
  await assert.rejects(api.get('countries', 1), (e) => e instanceof ApiError && e.status === 401);
  assert.equal(unauthenticated, 1);

  const limited = client((url, init, n) => (n === 1 ? response(429, undefined, { 'Retry-After': '0' }) : response(200, { id: 1 })));
  assert.deepEqual(await limited.api.get('countries', 1), { id: 1 });
  assert.equal(limited.calls.length, 2);
});

test('export asks for the file and names it from the header', async () => {
  const { api, calls } = client(() => response(200, 'bytes', { 'Content-Disposition': 'attachment; filename="grades.xlsx"' }));
  const file = await api.exportFile('grades');
  assert.deepEqual(file, { blob: 'bytes', filename: 'grades.xlsx' });
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(calls[0].url, '/v1/grades/export');
});
