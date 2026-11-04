const test = require('node:test');
const assert = require('node:assert/strict');
const views = require('../js/views.js');
const { ApiError } = require('../js/api.js');

const reader = { roles: ['reference-reader'] };
const hrReader = { roles: ['reference-hr-reader'] };
const admin = { roles: ['reference-admin'] };
const hrAdmin = { roles: ['reference-hr-admin'] };

const employee = { id: 1, personnel_number: '1001', family_name: 'Иванов', given_name: 'Иван', middle_name: null, email: 'i@example.org', username: 'i.ivanov', hire_date: '2026-01-12', is_deleted: false };

test('an empty catalog offers the first record to a role that may create, a reader only gets the explanation', () => {
  const forAdmin = views.emptyState('positions', hrAdmin, { filter: '', allowDeleted: false });
  assert.equal(forAdmin.kind, 'empty');
  assert.equal(forAdmin.action, 'create');

  const forReader = views.emptyState('positions', reader, {});
  assert.equal(forReader.kind, 'empty');
  assert.equal(forReader.action, null);
  assert.match(forReader.text, /администратор/);
});

test('an empty page of a filtered list offers to reset the filter, not to create a record', () => {
  assert.deepEqual(
    { kind: views.emptyState('employees', hrAdmin, { filter: 'family_name = "Нет"' }).kind, action: views.emptyState('employees', hrAdmin, { filter: 'x' }).action },
    { kind: 'no-match', action: 'reset' },
  );
  assert.equal(views.emptyState('employees', reader, { allowDeleted: true }).kind, 'no-match');

  const slice = views.emptyState('positions', hrAdmin, { readTime: '2020-01-01T09:00:00.000Z' });
  assert.deepEqual([slice.kind, slice.action], ['no-match', 'reset'], 'a slice never offers to create a record');
  assert.match(slice.text, /момент/);
  assert.equal(views.hasSelection({ readTime: '2020-01-01T09:00:00.000Z' }), true);
});

test('a failed request maps to a screen state, only transient failures offer a retry', () => {
  const network = views.errorState(new TypeError('Failed to fetch'));
  assert.deepEqual([network.kind, network.retry], ['unavailable', true]);

  const cases = [
    [400, 'invalid', false],
    [401, 'session', false],
    [403, 'denied', false],
    [404, 'not-found', false],
    [409, 'conflict', true],
    [429, 'busy', true],
    [500, 'error', true],
    [503, 'unavailable', true],
  ];
  for (const [status, kind, retry] of cases) {
    const state = views.errorState(new ApiError(status, 'reason', [], 't-1'));
    assert.deepEqual([state.kind, state.retry], [kind, retry], `status ${status}`);
    assert.ok(state.title && state.text, `status ${status} has a title and a text`);
  }
  assert.match(views.errorState(new ApiError(400, 'filter: syntax error')).text, /filter: syntax error/);
});

test('the form of an existing employee for the HR administrator: editable, the login locked, delete offered', () => {
  const model = views.formModel('employees', employee, hrAdmin, new URLSearchParams());
  assert.equal(model.editable, true);
  assert.equal(model.readOnlyReason, null);
  assert.deepEqual(model.actions, ['save', 'delete', 'back']);
  const byName = Object.fromEntries(model.fields.map((f) => [f.name, f]));
  assert.equal(byName.username.locked, true, 'the login does not change after creation');
  assert.equal(byName.email.locked, false);
  assert.match(byName.username.notes, /не меняется/);
  assert.match(byName.family_name.notes, /обязательно/);
  assert.equal(byName.middle_name.required, false);
});

test('a reader sees the same form read only with the role as the reason and no actions but back', () => {
  const model = views.formModel('employees', employee, reader, new URLSearchParams());
  assert.equal(model.editable, false);
  assert.equal(model.readOnlyReason, 'role');
  assert.deepEqual(model.actions, ['back']);
  assert.ok(model.fields.every((f) => f.locked));

  const classifierForHr = views.formModel('countries', { id: 3, is_deleted: false }, hrAdmin, new URLSearchParams());
  assert.equal(classifierForHr.editable, false, 'the HR administrator only reads the classifiers');
});

test('a deleted record can only be purged, its fields are locked because it is deleted', () => {
  const model = views.formModel('countries', { id: 3, alpha2: 'RU', is_deleted: true }, admin, new URLSearchParams());
  assert.equal(model.editable, false);
  assert.equal(model.readOnlyReason, 'deleted');
  assert.deepEqual(model.actions, ['purge', 'back']);
});

test('a new dated record opened from the employee card keeps the employee it was opened for', () => {
  const model = views.formModel('assignments', null, hrAdmin, new URLSearchParams('employee_id=4&back=/admin/employees/4'));
  assert.equal(model.isNew, true);
  assert.deepEqual(model.actions, ['save', 'back']);
  const byName = Object.fromEntries(model.fields.map((f) => [f.name, f]));
  assert.equal(byName.employee_id.locked, true);
  assert.equal(byName.org_unit_id.locked, false);

  const plain = views.formModel('assignments', null, hrAdmin, new URLSearchParams());
  assert.equal(plain.fields.find((f) => f.name === 'employee_id').locked, false);

  const forHrReader = views.formModel('salaries', null, hrReader, new URLSearchParams());
  assert.equal(forHrReader.editable, false);
  assert.deepEqual(forHrReader.actions, ['back']);
});

test('table cells: dates and money in Russian notation, references and states keep their kind', () => {
  assert.deepEqual(views.cell('employees', 'hire_date', '2026-01-12'), { kind: 'date', text: '12.01.2026', iso: '2026-01-12' });
  assert.deepEqual(views.cell('salaries', 'amount', 150000), { kind: 'num', text: '150 000,00' });
  assert.deepEqual(views.cell('salaries', 'currency_id', 1), { kind: 'ref', text: '#1', ref: 'currencies' });
  assert.deepEqual(views.cell('employees', 'employment_state', 'EMPLOYED'), { kind: 'enum', text: 'EMPLOYED' });
  assert.deepEqual(views.cell('employees', 'middle_name', null), { kind: 'empty', text: 'пусто' });
  assert.deepEqual(views.cell('employees', 'id', 7), { kind: 'id', text: '#7' });
  assert.deepEqual(views.cell('employees', 'is_deleted', true), { kind: 'state', text: 'DELETED' });
  assert.equal(views.cell('grades', 'rank', 3).kind, 'num');
  assert.equal(views.cell('positions', 'created_at', '2026-10-01T09:00:00Z').kind, 'time');
});

test('the selection is described for the table caption and the export', () => {
  assert.equal(views.selectionText({}), 'все активные записи в порядке создания');
  assert.equal(views.selectionText({ filter: 'kind = "TEAM"', orderBy: 'name', allowDeleted: true }), 'фильтр kind = "TEAM", сортировка name, с удалёнными записями');
});
