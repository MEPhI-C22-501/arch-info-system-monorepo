const test = require('node:test');
const assert = require('node:assert/strict');
const { createApi, ApiError } = require('../js/mock-api.js');
const { USERS, CATALOGS } = require('../js/catalogs.js');

const user = (key) => USERS.find((u) => u.key === key);
const admin = user('admin');
const hrAdmin = user('hr-admin');
const reader = user('reader');
const hrReader = user('hr-reader');
const anonymous = user('anonymous');

async function expectError(promise, status, check) {
  try {
    await promise;
  } catch (e) {
    assert.ok(e instanceof ApiError, `expected ApiError, got ${e && e.stack}`);
    assert.equal(e.status, status, e.message);
    if (check) check(e);
    return e;
  }
  assert.fail(`expected ${status}`);
}

const fieldsOf = (e) => e.fieldViolations.map((v) => v.field);

test('every catalog of the first version is seeded and lists as ACTIVE by default', async () => {
  const api = createApi();
  for (const collection of Object.keys(CATALOGS)) {
    const page = await api.list(hrAdmin, collection, {});
    assert.ok(page.total_size > 0, collection);
    assert.ok(page[collection].every((r) => r.state === 'ACTIVE'), collection);
  }
  const withDeleted = await api.list(admin, 'currencies', { showDeleted: true });
  assert.ok(withDeleted.currencies.some((r) => r.name === 'currencies/XTS' && r.state === 'DELETED'));
});

test('List applies filter, order_by, page_size and opaque page tokens', async () => {
  const api = createApi();
  const first = await api.list(admin, 'currencies', { filter: 'minor_units = 2', orderBy: 'display_name desc', pageSize: 3 });
  assert.equal(first.total_size, 6);
  assert.equal(first.currencies.length, 3);
  assert.notEqual(first.next_page_token, '');
  const second = await api.list(admin, 'currencies', { filter: 'minor_units = 2', orderBy: 'display_name desc', pageSize: 3, pageToken: first.next_page_token });
  assert.equal(second.currencies.length, 3);
  assert.equal(second.next_page_token, '');
  const names = [...first.currencies, ...second.currencies].map((r) => r.display_name);
  assert.deepEqual(names, [...names].sort((a, b) => b.localeCompare(a, 'ru')));
  await expectError(api.list(admin, 'currencies', { pageToken: first.next_page_token }), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['page_token']));
  await expectError(api.list(admin, 'currencies', { filter: 'colour = red' }), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['filter']));
  await expectError(api.list(admin, 'currencies', { orderBy: 'colour' }), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['order_by']));
});

test('roles: reader and admin cannot read salaries, anonymous gets UNAUTHENTICATED, admin cannot write HR catalogs', async () => {
  const api = createApi();
  await expectError(api.list(reader, 'salaries', {}), 'PERMISSION_DENIED');
  await expectError(api.list(admin, 'absences', {}), 'PERMISSION_DENIED');
  assert.ok((await api.list(hrReader, 'salaries', {})).total_size > 0);
  await expectError(api.list(anonymous, 'currencies', {}), 'UNAUTHENTICATED');
  await expectError(api.create(admin, 'positions', { display_name: 'x' }, 'x-position'), 'PERMISSION_DENIED');
  await expectError(api.create(hrAdmin, 'currencies', { display_name: 'x', numeric_code: '001', minor_units: 2 }, 'XAA'), 'PERMISSION_DENIED');
  await expectError(api.exportList(reader, 'salaries', {}), 'PERMISSION_DENIED');
});

test('Create validates fields, rejects duplicates and names deleted ids', async () => {
  const api = createApi();
  await expectError(api.create(admin, 'countries', { display_name: 'Тест', alpha3: 'tst', numeric_code: '12', currency: 'currencies/XXX' }, 'TT'), 'INVALID_ARGUMENT', (e) => {
    assert.deepEqual(fieldsOf(e).sort(), ['alpha3', 'currency', 'numeric_code']);
  });
  await expectError(api.create(admin, 'countries', { display_name: 'Тест', alpha3: 'RUS', numeric_code: '643' }, 'TT'), 'INVALID_ARGUMENT', (e) => {
    assert.ok(e.fieldViolations.every((v) => /already used by countries\/RU/.test(v.description)));
  });
  await expectError(api.create(admin, 'currencies', { display_name: 'x', numeric_code: '001', minor_units: 2 }, 'rub'), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['currency_id']));
  await expectError(api.create(admin, 'currencies', { display_name: 'x', numeric_code: '001', minor_units: 2 }, 'RUB'), 'ALREADY_EXISTS');
  const deleted = await expectError(api.create(admin, 'currencies', { display_name: 'x', numeric_code: '001', minor_units: 2 }, 'XTS'), 'ALREADY_EXISTS');
  assert.equal(deleted.metadata.state, 'DELETED');
  const created = await api.create(admin, 'countries', { display_name: 'Тест', alpha3: 'TST', numeric_code: '999', currency: 'currencies/RUB' }, 'TT');
  assert.equal(created.name, 'countries/TT');
  assert.equal(created.state, 'ACTIVE');
  const history = await api.listRevisions(admin, 'countries', 'TT');
  assert.equal(history.total_size, 1);
  assert.equal(history.revisions[0].action, 'CREATED');
  assert.equal(history.revisions[0].author, 'admin@erp');
});

test('Update writes only the update_mask fields and records a revision with the differences', async () => {
  const api = createApi();
  const before = await api.get(admin, 'currencies', 'RUB');
  const after = await api.update(admin, 'currencies', 'RUB', { symbol: 'руб', display_name: 'ignored' }, 'symbol');
  assert.equal(after.symbol, 'руб');
  assert.equal(after.display_name, before.display_name);
  assert.notEqual(after.etag, before.etag);
  const history = await api.listRevisions(admin, 'currencies', 'RUB');
  assert.equal(history.revisions[0].action, 'UPDATED');
  assert.deepEqual(history.revisions[0].changes, [{ field: 'symbol', old_value: '₽', new_value: 'руб' }]);
  const asOf = await api.getAtRevision(admin, 'currencies', 'RUB', 1);
  assert.equal(asOf.symbol, 'руб.', 'the seed history starts with the old symbol');
  await expectError(api.update(admin, 'currencies', 'RUB', { symbol: 'x' }, ''), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['update_mask']));
  await expectError(api.update(admin, 'currencies', 'RUB', { state: 'DELETED' }, 'state'), 'INVALID_ARGUMENT');
  await expectError(api.update(admin, 'currencies', 'XTS', { symbol: 'x' }, 'symbol'), 'FAILED_PRECONDITION', (e) => assert.equal(e.reason, 'RECORD_DELETED'));
});

test('Delete is soft, Undelete restores, both refuse the wrong state', async () => {
  const api = createApi();
  const deleted = await api.remove(admin, 'currencies', 'JPY');
  assert.equal(deleted.state, 'DELETED');
  assert.ok(deleted.delete_time);
  assert.ok(!(await api.list(admin, 'currencies', {})).currencies.some((r) => r.name === 'currencies/JPY'));
  assert.equal((await api.get(admin, 'currencies', 'JPY')).state, 'DELETED', 'Get still returns a deleted record');
  await expectError(api.remove(admin, 'currencies', 'JPY'), 'FAILED_PRECONDITION');
  const restored = await api.undelete(admin, 'currencies', 'JPY');
  assert.equal(restored.state, 'ACTIVE');
  assert.equal(restored.delete_time, null);
  await expectError(api.undelete(admin, 'currencies', 'JPY'), 'FAILED_PRECONDITION');
  const history = await api.listRevisions(admin, 'currencies', 'JPY');
  assert.deepEqual(history.revisions.map((r) => r.action), ['UNDELETED', 'DELETED', 'CREATED']);
  await expectError(api.get(admin, 'currencies', 'ZZZ'), 'NOT_FOUND');
});

test('hire: the profile is saved, the account is created and enabled, Create answers ENABLED', async () => {
  const api = createApi();
  const body = { display_name: 'Орлов Пётр Семёнович', family_name: 'Орлов', given_name: 'Пётр', middle_name: 'Семёнович', email: 'p.orlov@example.org', username: 'p.orlov', hire_date: '2026-11-02' };
  const rec = await api.create(hrAdmin, 'employees', body, '1024');
  assert.equal(rec.name, 'employees/1024');
  assert.equal(rec.employment_state, 'EMPLOYED');
  assert.equal(rec.account_state, 'ENABLED');
  assert.ok(rec.account_user_id);
  assert.equal(rec.org_unit, null);
  const account = api.keycloak.list().find((u) => u.username === 'p.orlov');
  assert.equal(account.attributes.employee, 'employees/1024');
  assert.deepEqual(account.requiredActions, ['UPDATE_PASSWORD']);
  const history = await api.listRevisions(hrAdmin, 'employees', '1024');
  assert.deepEqual(history.revisions.map((r) => r.action), ['UPDATED', 'CREATED']);
  assert.ok(!JSON.stringify(history).includes('password'));
  await expectError(api.create(hrAdmin, 'employees', { ...body, email: 'other@example.org' }, '1025'), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['username']));
  await expectError(api.create(hrAdmin, 'employees', { ...body, username: 'other' }, '1025'), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['email']));
});

test('hire with Keycloak down: UNAVAILABLE, profile PENDING, SyncAccount finishes without a duplicate account', async () => {
  const api = createApi({ keycloakAvailable: false });
  const body = { display_name: 'Орлов Пётр', family_name: 'Орлов', given_name: 'Пётр', email: 'p.orlov@example.org', username: 'p.orlov', hire_date: '2026-11-02' };
  const error = await expectError(api.create(hrAdmin, 'employees', body, '1024'), 'UNAVAILABLE');
  assert.equal(error.reason, 'ACCOUNT_PENDING');
  assert.deepEqual(error.metadata, { name: 'employees/1024', operation: 'CREATE' });
  const pending = await api.get(hrAdmin, 'employees', '1024');
  assert.equal(pending.account_state, 'PENDING');
  assert.equal(pending.account_user_id, null);
  await expectError(api.syncAccount(hrAdmin, '1024'), 'UNAVAILABLE');
  api.config.keycloakAvailable = true;
  const synced = await api.syncAccount(hrAdmin, '1024');
  assert.equal(synced.account_state, 'ENABLED');
  assert.equal(api.keycloak.list().filter((u) => u.username === 'p.orlov').length, 1);
  const again = await api.syncAccount(hrAdmin, '1024');
  assert.equal(again.etag, synced.etag, 'a second sync changes nothing');
});

test('sync after a lost answer: the account exists in Keycloak, the retry adopts it instead of creating a second one', async () => {
  const api = createApi({ keycloakAvailable: false });
  const body = { display_name: 'Орлов Пётр', family_name: 'Орлов', given_name: 'Пётр', email: 'p.orlov@example.org', username: 'p.orlov', hire_date: '2026-11-02' };
  await expectError(api.create(hrAdmin, 'employees', body, '1024'), 'UNAVAILABLE');
  api.config.keycloakAvailable = true;
  api.keycloak.seedUser({ id: 'lost-answer', username: 'p.orlov', email: body.email, attributes: { employee: 'employees/1024' } });
  const synced = await api.syncAccount(hrAdmin, '1024');
  assert.equal(synced.account_user_id, 'lost-answer');
  assert.equal(api.keycloak.list().filter((u) => u.username === 'p.orlov').length, 1);
});

test('a seeded PENDING employee can be completed with SyncAccount', async () => {
  const api = createApi();
  const before = await api.get(hrAdmin, 'employees', '1009');
  assert.equal(before.account_state, 'PENDING');
  const after = await api.syncAccount(hrAdmin, '1009');
  assert.equal(after.account_state, 'ENABLED');
});

test('changing a name or an email propagates to the account, with Keycloak down it stays PENDING', async () => {
  const api = createApi();
  const updated = await api.update(hrAdmin, 'employees', '1001', { email: 'ivan.ivanov@example.org' }, 'email');
  assert.equal(updated.account_state, 'ENABLED');
  assert.equal(api.keycloak.list().find((u) => u.username === 'i.ivanov').email, 'ivan.ivanov@example.org');
  api.config.keycloakAvailable = false;
  await expectError(api.update(hrAdmin, 'employees', '1002', { family_name: 'Иванова' }, 'family_name'), 'UNAVAILABLE');
  const pending = await api.get(hrAdmin, 'employees', '1002');
  assert.equal(pending.family_name, 'Иванова');
  assert.equal(pending.account_state, 'PENDING');
  api.config.keycloakAvailable = true;
  assert.equal((await api.syncAccount(hrAdmin, '1002')).account_state, 'ENABLED');
  await expectError(api.update(hrAdmin, 'employees', '1002', { username: 'other' }, 'username'), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['username']));
});

test('dated records: periods of one employee must not overlap, a new value is a new record', async () => {
  const api = createApi();
  const employee = 'employees/1002';
  await expectError(api.create(hrAdmin, 'assignments', { employee, org_unit: 'org_units/dev-backend', position: 'positions/senior-developer', start_date: '2026-10-01' }), 'INVALID_ARGUMENT', (e) => {
    assert.deepEqual(fieldsOf(e), ['start_date', 'end_date']);
  });
  const current = (await api.list(hrAdmin, 'assignments', { filter: `employee = "${employee}" AND NOT end_date:*` })).assignments[0];
  await api.update(hrAdmin, 'assignments', current.name.split('/')[1], { end_date: '2026-09-30' }, 'end_date');
  const created = await api.create(hrAdmin, 'assignments', { employee, org_unit: 'org_units/dev-backend', position: 'positions/senior-developer', start_date: '2026-10-01' });
  assert.match(created.name, /^assignments\/\d+$/);
  assert.equal(created.end_date, null);
  const all = await api.list(hrAdmin, 'assignments', { filter: `employee = "${employee}"`, orderBy: 'start_date' });
  assert.equal(all.total_size, 2);
  const onDate = await api.list(hrAdmin, 'assignments', { filter: `employee = "${employee}" AND start_date <= "2026-06-15" AND (end_date >= "2026-06-15" OR NOT end_date:*)` });
  assert.equal(onDate.assignments[0].position, 'positions/developer');
  await expectError(api.create(hrAdmin, 'absences', { employee, kind: 'VACATION', start_date: '2026-12-10', end_date: '2026-12-01' }), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['end_date']));
  await expectError(api.create(hrAdmin, 'assignments', { employee, org_unit: 'org_units/dev-backend', position: 'positions/nobody', start_date: '2027-01-01' }), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['position']));
  await expectError(api.create(hrAdmin, 'salaries', { employee: 'employees/1007', amount: 1, currency: 'currencies/RUB', start_date: '2027-01-01' }), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['employee']));
});

test('the employee record shows the org unit and position of the assignment in effect', async () => {
  const api = createApi({ now: () => new Date('2026-10-13T10:00:00Z') });
  const ivanov = await api.get(reader, 'employees', '1001');
  assert.equal(ivanov.org_unit, 'org_units/dev-backend');
  assert.equal(ivanov.position, 'positions/senior-developer');
  const dismissed = await api.get(reader, 'employees', '1007');
  assert.equal(dismissed.org_unit, null);
  const filtered = await api.list(reader, 'employees', { filter: 'employment_state = EMPLOYED AND org_unit = "org_units/dev-backend"' });
  assert.deepEqual(filtered.employees.map((r) => r.name), ['employees/1001', 'employees/1003', 'employees/1008']);
});

test('dismiss: DISMISSED, assignment and salary closed, account DISABLED, repeated dismiss and Delete before dismiss refused', async () => {
  const api = createApi();
  await expectError(api.remove(hrAdmin, 'employees', '1001'), 'FAILED_PRECONDITION', (e) => assert.equal(e.reason, 'EMPLOYEE_ACTIVE'));
  await expectError(api.dismiss(hrAdmin, '1001', { dismissal_date: '2020-01-01' }), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['dismissal_date']));
  const rec = await api.dismiss(hrAdmin, '1001', { dismissal_date: '2026-10-31' });
  assert.equal(rec.employment_state, 'DISMISSED');
  assert.equal(rec.dismissal_date, '2026-10-31');
  assert.equal(rec.account_state, 'DISABLED');
  assert.equal(api.keycloak.list().find((u) => u.username === 'i.ivanov').enabled, false);
  const assignments = await api.list(hrAdmin, 'assignments', { filter: 'employee = "employees/1001"', orderBy: 'start_date desc' });
  assert.equal(assignments.assignments[0].end_date, '2026-10-31');
  const salaries = await api.list(hrAdmin, 'salaries', { filter: 'employee = "employees/1001"', orderBy: 'start_date desc' });
  assert.equal(salaries.salaries[0].end_date, '2026-10-31');
  assert.equal((await api.get(hrAdmin, 'employees', '1001')).name, 'employees/1001', 'the record stays readable');
  await expectError(api.dismiss(hrAdmin, '1001', { dismissal_date: '2026-11-30' }), 'FAILED_PRECONDITION', (e) => assert.equal(e.reason, 'ALREADY_DISMISSED'));
  const removed = await api.remove(hrAdmin, 'employees', '1001');
  assert.equal(removed.state, 'DELETED');
  await expectError(api.dismiss(admin, '1002', { dismissal_date: '2026-10-31' }), 'PERMISSION_DENIED');
});

test('dismiss with Keycloak down: the dismissal is saved, the account stays PENDING until SyncAccount', async () => {
  const api = createApi({ keycloakAvailable: false });
  const error = await expectError(api.dismiss(hrAdmin, '1002', { dismissal_date: '2026-10-31' }), 'UNAVAILABLE');
  assert.equal(error.metadata.operation, 'DISABLE');
  const rec = await api.get(hrAdmin, 'employees', '1002');
  assert.equal(rec.employment_state, 'DISMISSED');
  assert.equal(rec.account_state, 'PENDING');
  api.config.keycloakAvailable = true;
  assert.equal((await api.syncAccount(hrAdmin, '1002')).account_state, 'DISABLED');
});

test('org units: a parent reference that forms a cycle is rejected', async () => {
  const api = createApi();
  await expectError(api.update(hrAdmin, 'org_units', 'dev', { parent: 'org_units/dev-backend' }, 'parent'), 'INVALID_ARGUMENT', (e) => assert.deepEqual(fieldsOf(e), ['parent']));
  await expectError(api.update(hrAdmin, 'org_units', 'dev', { parent: 'org_units/dev' }, 'parent'), 'INVALID_ARGUMENT');
  const moved = await api.update(hrAdmin, 'org_units', 'qa-automation', { parent: 'org_units/dev' }, 'parent');
  assert.equal(moved.parent, 'org_units/dev');
  const children = await api.list(reader, 'org_units', { filter: 'parent = "org_units/dev"' });
  assert.equal(children.total_size, 3);
});

test('export: the selection becomes an .xlsx file, above the limit the service refuses with EXPORT_TOO_LARGE', async () => {
  const api = createApi({ exportLimit: 5 });
  const file = await api.exportList(reader, 'countries', { filter: 'currency = "currencies/EUR" OR currency = "currencies/USD"', orderBy: 'name' });
  assert.equal(file.filename, 'countries.xlsx');
  assert.equal(file.rows, 2);
  assert.equal(file.bytes[0], 0x50);
  assert.equal(file.bytes[1], 0x4b);
  const error = await expectError(api.exportList(reader, 'countries', {}), 'FAILED_PRECONDITION');
  assert.equal(error.reason, 'EXPORT_TOO_LARGE');
  assert.equal(error.metadata.selected, '7');
  await expectError(api.exportList(reader, 'countries', { filter: 'bad =' }), 'INVALID_ARGUMENT');
});

test('errors serialize as google.rpc.Status with a request id', async () => {
  const api = createApi();
  const error = await expectError(api.get(reader, 'currencies', 'ZZZ'), 'NOT_FOUND');
  const status = error.toJSON().error;
  assert.equal(status.code, 404);
  assert.equal(status.status, 'NOT_FOUND');
  assert.ok(status.details.some((d) => d['@type'] === 'type.googleapis.com/google.rpc.RequestInfo' && d.requestId));
});

test('reset returns the seed state', async () => {
  const api = createApi();
  await api.remove(admin, 'currencies', 'JPY');
  api.reset();
  assert.equal((await api.get(admin, 'currencies', 'JPY')).state, 'ACTIVE');
});
