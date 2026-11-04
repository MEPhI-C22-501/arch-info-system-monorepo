// formats of dates, times and numbers on the screens: Russian conventions for reading, the API keeps ISO 8601
// dates and a dot in numbers, inputs and filters keep the API form
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).format = factory();
})(globalThis, function () {
  'use strict';

  const ZERO_TIME = '0001-01-01T00:00:00Z';
  const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/;
  const LOCALE = 'ru-RU';

  const integerFormat = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
  const moneyFormats = new Map();

  function isEmpty(value) {
    return value === null || value === undefined || value === '';
  }

  // "2026-07-01" -> "01.07.2026", a timestamp keeps only its calendar date
  function date(value) {
    if (isEmpty(value)) return '';
    const match = ISO_DATE.exec(String(value));
    return match ? `${match[3]}.${match[2]}.${match[1]}` : String(value);
  }

  // "2026-10-31T10:57:17Z" -> "31.10.2026, 13:57" in the time zone of the browser, the zero time is empty
  function dateTime(value, timeZone) {
    if (isEmpty(value) || value === ZERO_TIME) return '';
    const moment = new Date(value);
    if (Number.isNaN(moment.getTime())) return String(value);
    return new Intl.DateTimeFormat(LOCALE, {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone,
    }).format(moment);
  }

  // 1234567 -> "1 234 567" with a non-breaking space between the groups
  function integer(value) {
    if (isEmpty(value)) return '';
    const number = Number(value);
    return Number.isFinite(number) ? integerFormat.format(number) : String(value);
  }

  // 150000.5 -> "150 000,50"
  function money(value, fractionDigits) {
    if (isEmpty(value)) return '';
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);
    const digits = fractionDigits === undefined ? 2 : fractionDigits;
    if (!moneyFormats.has(digits)) {
      moneyFormats.set(digits, new Intl.NumberFormat(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits }));
    }
    return moneyFormats.get(digits).format(number);
  }

  // a period of a dated record: "01.07.2026 - 14.07.2026", an open one ends with "сейчас"
  function period(start, end) {
    return `${date(start)} - ${isEmpty(end) ? 'сейчас' : date(end)}`;
  }

  return { ZERO_TIME, date, dateTime, integer, money, period, isEmpty };
});
