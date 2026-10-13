const test = require('node:test');
const assert = require('node:assert/strict');
const filter = require('../js/filter.js');

const FIELDS = ['name', 'display_name', 'state', 'minor_units', 'symbol', 'employee', 'start_date', 'end_date'];
const rows = [
  { name: 'currencies/RUB', display_name: 'Российский рубль', state: 'ACTIVE', minor_units: 2, symbol: '₽' },
  { name: 'currencies/JPY', display_name: 'Японская иена', state: 'ACTIVE', minor_units: 0, symbol: '¥' },
  { name: 'currencies/XTS', display_name: 'Код для тестирования', state: 'DELETED', minor_units: 2, symbol: null },
];

function select(expression) {
  const predicate = filter.compile(expression, FIELDS);
  return rows.filter(predicate).map((r) => r.name);
}

test('equality, inequality and substring match', () => {
  assert.deepEqual(select('state = ACTIVE'), ['currencies/RUB', 'currencies/JPY']);
  assert.deepEqual(select('state != ACTIVE'), ['currencies/XTS']);
  assert.deepEqual(select('display_name:"рубль"'), ['currencies/RUB']);
  assert.deepEqual(select('display_name:РУБ'), ['currencies/RUB']);
});

test('numbers compare numerically, strings lexicographically', () => {
  assert.deepEqual(select('minor_units = 2'), ['currencies/RUB', 'currencies/XTS']);
  assert.deepEqual(select('minor_units < 2'), ['currencies/JPY']);
  assert.deepEqual(select('name >= "currencies/RUB"'), ['currencies/RUB', 'currencies/XTS']);
});

test('AND is implicit between terms and explicit with the keyword, OR and NOT combine', () => {
  assert.deepEqual(select('state = ACTIVE minor_units = 2'), ['currencies/RUB']);
  assert.deepEqual(select('state = ACTIVE AND minor_units = 2'), ['currencies/RUB']);
  assert.deepEqual(select('minor_units = 0 OR state = DELETED'), ['currencies/JPY', 'currencies/XTS']);
  assert.deepEqual(select('NOT state = ACTIVE'), ['currencies/XTS']);
  assert.deepEqual(select('state = ACTIVE AND (minor_units = 0 OR symbol = "₽")'), ['currencies/RUB', 'currencies/JPY']);
});

test('field:* tests presence and NOT field:* absence', () => {
  assert.deepEqual(select('symbol:*'), ['currencies/RUB', 'currencies/JPY']);
  assert.deepEqual(select('NOT symbol:*'), ['currencies/XTS']);
});

test('the assignment-on-a-date query from document 130 parses', () => {
  const predicate = filter.compile('employee = "employees/1024" AND start_date <= "2026-06-15" AND (end_date >= "2026-06-15" OR NOT end_date:*)', FIELDS);
  assert.equal(predicate({ employee: 'employees/1024', start_date: '2026-01-01', end_date: null }), true);
  assert.equal(predicate({ employee: 'employees/1024', start_date: '2026-01-01', end_date: '2026-03-31' }), false);
  assert.equal(predicate({ employee: 'employees/1024', start_date: '2026-01-01', end_date: '2026-09-30' }), true);
  assert.equal(predicate({ employee: 'employees/1', start_date: '2026-01-01', end_date: null }), false);
});

test('an empty filter matches everything', () => {
  assert.deepEqual(select(''), rows.map((r) => r.name));
  assert.deepEqual(select('   '), rows.map((r) => r.name));
});

test('syntax errors and unknown fields are FilterError', () => {
  for (const bad of ['state =', 'state ACTIVE', '(state = ACTIVE', 'state = "unterminated', 'state = ACTIVE )']) {
    assert.throws(() => filter.compile(bad, FIELDS), filter.FilterError, bad);
  }
  assert.throws(() => filter.compile('colour = red', FIELDS), /unknown field "colour"/);
});
