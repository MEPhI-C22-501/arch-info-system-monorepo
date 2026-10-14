const test = require('node:test');
const assert = require('node:assert/strict');
const xlsx = require('../js/xlsx.js');

function readUint32(bytes, offset) {
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(offset, true);
}

test('crc32 matches the reference value for "123456789"', () => {
  assert.equal(xlsx.crc32(new TextEncoder().encode('123456789')), 0xcbf43926);
});

test('column names follow the spreadsheet convention', () => {
  assert.deepEqual([0, 1, 25, 26, 27, 701, 702].map(xlsx.columnName), ['A', 'B', 'Z', 'AA', 'AB', 'ZZ', 'AAA']);
});

test('the workbook is a zip with five parts and a worksheet of inline strings', () => {
  const bytes = xlsx.build('currencies', ['name', 'minor_units', 'symbol'], [
    ['currencies/RUB', 2, '₽'],
    ['currencies/XTS', 2, null],
  ], new Date('2026-10-13T12:00:00'));
  assert.equal(readUint32(bytes, 0), 0x04034b50, 'local file header signature');
  const text = new TextDecoder().decode(bytes);
  for (const part of ['[Content_Types].xml', '_rels/.rels', 'xl/workbook.xml', 'xl/_rels/workbook.xml.rels', 'xl/worksheets/sheet1.xml']) {
    assert.ok(text.includes(part), part);
  }
  assert.ok(text.includes('<c r="A2" t="inlineStr"><is><t xml:space="preserve">currencies/RUB</t></is></c>'));
  assert.ok(text.includes('<c r="B2"><v>2</v></c>'), 'numbers are numeric cells');
  assert.ok(text.includes('<row r="3"><c r="A3" t="inlineStr"><is><t xml:space="preserve">currencies/XTS</t></is></c><c r="B3"><v>2</v></c></row>'), 'empty cells are skipped');
  assert.ok(text.includes('<sheet name="currencies" sheetId="1" r:id="rId1"/>'));
});

test('text that looks like a formula or markup stays text', () => {
  const bytes = xlsx.build('t', ['value'], [['=SUM(A1:A9)'], ['<b>&"x"</b>'], ['tab\there\u0001']]);
  const text = new TextDecoder().decode(bytes);
  assert.ok(text.includes('<t xml:space="preserve">=SUM(A1:A9)</t>'), 'a leading "=" is kept inside an inline string');
  assert.ok(text.includes('<t xml:space="preserve">&lt;b&gt;&amp;&quot;x&quot;&lt;/b&gt;</t>'));
  assert.ok(text.includes('<t xml:space="preserve">tab\there</t>'), 'control characters are dropped');
  assert.ok(!text.includes('<f>'), 'no formula cells');
});

test('the central directory counts every entry and points at the local headers', () => {
  const bytes = xlsx.build('s', ['a'], [['b']]);
  const endOffset = bytes.length - 22;
  assert.equal(readUint32(bytes, endOffset), 0x06054b50, 'end of central directory signature');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  assert.equal(view.getUint16(endOffset + 10, true), 5, 'five entries');
  const centralOffset = view.getUint32(endOffset + 16, true);
  assert.equal(readUint32(bytes, centralOffset), 0x02014b50, 'central directory signature');
  const firstLocal = view.getUint32(centralOffset + 42, true);
  assert.equal(firstLocal, 0);
});
