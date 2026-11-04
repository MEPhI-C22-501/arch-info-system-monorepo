const test = require('node:test');
const assert = require('node:assert/strict');
const format = require('../js/format.js');

const NBSP = ' ';

test('calendar dates read as day, month and year, a timestamp keeps its date, empty stays empty', () => {
  assert.equal(format.date('2026-07-01'), '01.07.2026');
  assert.equal(format.date('2026-07-01T00:00:00Z'), '01.07.2026');
  assert.equal(format.date(''), '');
  assert.equal(format.date(null), '');
  assert.equal(format.date('not a date'), 'not a date');
});

test('times are shown in the given time zone, the zero time of a never deleted record is empty', () => {
  assert.equal(format.dateTime('2026-10-31T10:57:17Z', 'UTC'), '31.10.2026, 10:57');
  assert.equal(format.dateTime('2026-10-31T10:57:17Z', 'Europe/Moscow'), '31.10.2026, 13:57');
  assert.equal(format.dateTime(format.ZERO_TIME, 'UTC'), '');
  assert.equal(format.dateTime(undefined), '');
});

test('numbers are grouped by thousands with a non-breaking space and a decimal comma', () => {
  assert.equal(format.integer(1234567), `1${NBSP}234${NBSP}567`);
  assert.equal(format.integer('42'), '42');
  assert.equal(format.money(150000.5), `150${NBSP}000,50`);
  assert.equal(format.money('98000'), `98${NBSP}000,00`);
  assert.equal(format.money(1.005, 0), '1');
  assert.equal(format.money(null), '');
});

test('a period ends with its last day or "сейчас" while it is open', () => {
  assert.equal(format.period('2026-07-01', '2026-07-14'), '01.07.2026 - 14.07.2026');
  assert.equal(format.period('2026-07-01', null), '01.07.2026 - сейчас');
});
