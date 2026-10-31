const test = require('node:test');
const assert = require('node:assert/strict');
const catalogs = require('../js/catalogs.js');

const { CATALOGS, GROUPS, can, hasAnyRole, toBody, updateMask, recordLabel, queryFields, listColumns, fieldLabel } = catalogs;

test('every catalog of the first version is in a group and every group lists existing catalogs', () => {
  const listed = Object.values(GROUPS).flatMap((g) => g.collections);
  assert.deepEqual([...listed].sort(), Object.keys(CATALOGS).sort());
});

test('roles map to the levels of document 070', () => {
  const reader = { roles: ['reference-reader'] };
  const hrReader = { roles: ['reference-hr-reader'] };
  const admin = { roles: ['reference-admin'] };
  const hrAdmin = { roles: ['reference-hr-admin'] };
  assert.ok(can(reader, 'countries', 'R') && !can(reader, 'countries', 'C') && !can(reader, 'salaries', 'R'));
  assert.ok(can(hrReader, 'salaries', 'R') && !can(hrReader, 'salaries', 'C'));
  assert.ok(can(admin, 'countries', 'D') && can(admin, 'employees', 'X') && !can(admin, 'employees', 'U') && !can(admin, 'absences', 'R'));
  assert.ok(can(hrAdmin, 'employees', 'C') && can(hrAdmin, 'salaries', 'D') && !can(hrAdmin, 'countries', 'U'));
  assert.ok(hasAnyRole(hrAdmin) && !hasAnyRole({ roles: ['offline_access'] }) && !hasAnyRole(null));
});

test('the body types the inputs: numbers for ids and amounts, null for empty optional fields', () => {
  assert.deepEqual(toBody('salaries', { employee_id: '5', amount: '150000.50', currency_id: '1', start_date: '2026-01-01', end_date: '' }),
    { employee_id: 5, amount: 150000.5, currency_id: 1, start_date: '2026-01-01', end_date: null });
  assert.deepEqual(toBody('org_units', { code: ' qa ', name: 'QA', kind: 'TEAM', parent_id: '' }),
    { code: 'qa', name: 'QA', kind: 'TEAM', parent_id: null });
  assert.deepEqual(toBody('employees', { personnel_number: '1024', family_name: 'Petrova', given_name: 'Maria', middle_name: '', email: 'm@example.org', username: 'm.petrova', hire_date: '2026-11-02' }),
    { personnel_number: '1024', family_name: 'Petrova', given_name: 'Maria', middle_name: null, email: 'm@example.org', username: 'm.petrova', hire_date: '2026-11-02' });
  assert.equal(toBody('currencies', { code: 'USD', number: '840', name: '', decimals: '2' }).name, '', 'a required field stays empty for the service to report');
});

test('the update mask names the changed updatable fields only', () => {
  const stored = { id: 2, personnel_number: '1024', family_name: 'Petrova', given_name: 'Maria', middle_name: null, email: 'm@example.org', username: 'm.petrova', hire_date: '2026-11-02' };
  assert.deepEqual(updateMask('employees', stored, { ...stored, middle_name: '', email: 'maria@example.org', username: 'changed' }), ['email']);
  assert.deepEqual(updateMask('employees', stored, { ...stored, family_name: 'Petrova ' }), []);
  assert.deepEqual(updateMask('assignments', { employee_id: 1, org_unit_id: 2, position_id: 3, start_date: '2026-01-01', end_date: null }, { end_date: '2026-06-30' }), ['end_date']);
});

test('labels and columns: an employee by the full name, a dated record by its id, a classifier by code and name', () => {
  assert.equal(recordLabel('employees', { id: 1, family_name: 'Иванов', given_name: 'Иван', middle_name: 'Иванович' }), 'Иванов Иван Иванович');
  assert.equal(recordLabel('employees', { id: 1, family_name: 'Иванов', given_name: 'Иван', middle_name: null }), 'Иванов Иван');
  assert.equal(recordLabel('assignments', { id: 7 }), '#7');
  assert.equal(recordLabel('currencies', { id: 1, code: 'RUB', name: 'Рубль' }), 'RUB Рубль');
  assert.deepEqual(listColumns('positions'), ['id', 'code', 'name', 'is_deleted']);
  assert.ok(listColumns('employees').includes('account_state'));
  assert.ok(queryFields('employees').includes('account_user_id') && queryFields('employees').includes('revision'));
  assert.ok(!queryFields('employees').includes('id'), 'the service does not sort or filter by id');
  assert.equal(fieldLabel('employees', 'account_state'), 'Учётная запись');
  assert.equal(fieldLabel('employees', 'unknown'), 'unknown');
});
