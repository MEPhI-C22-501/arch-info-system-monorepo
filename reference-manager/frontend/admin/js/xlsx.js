// minimal .xlsx writer without dependencies: one sheet, inline strings, stored (uncompressed) zip entries
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).xlsx = factory();
})(globalThis, function () {
  'use strict';

  const encoder = new TextEncoder();

  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (let i = 0; i < bytes.length; i += 1) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }

  // control characters are not allowed in XML 1.0, they are dropped from cell text
  function escapeXml(value) {
    return String(value)
      .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '')
      .replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }

  function columnName(index) {
    let name = '';
    let n = index + 1;
    while (n > 0) {
      const remainder = (n - 1) % 26;
      name = String.fromCharCode(65 + remainder) + name;
      n = Math.floor((n - 1) / 26);
    }
    return name;
  }

  // text goes into inline strings, so a value that starts with "=" can never become a formula (NFR-RM-45)
  function cell(reference, value) {
    if (value === null || value === undefined || value === '') return '';
    if (typeof value === 'number' && Number.isFinite(value)) return `<c r="${reference}"><v>${value}</v></c>`;
    return `<c r="${reference}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(value)}</t></is></c>`;
  }

  function sheetXml(header, rows) {
    const lines = [header, ...rows].map((row, rowIndex) => {
      const cells = row.map((value, columnIndex) => cell(columnName(columnIndex) + (rowIndex + 1), value)).join('');
      return `<row r="${rowIndex + 1}">${cells}</row>`;
    });
    const columns = header.map((_, i) => `<col min="${i + 1}" max="${i + 1}" width="20" customWidth="1"/>`).join('');
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
      + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      + `<cols>${columns}</cols><sheetData>${lines.join('')}</sheetData></worksheet>`;
  }

  function workbookXml(sheetName) {
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
      + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
      + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
      + `<sheets><sheet name="${escapeXml(sheetName)}" sheetId="1" r:id="rId1"/></sheets></workbook>`;
  }

  const CONTENT_TYPES = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    + '<Default Extension="xml" ContentType="application/xml"/>'
    + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    + '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    + '</Types>';

  const ROOT_RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    + '</Relationships>';

  const WORKBOOK_RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    + '</Relationships>';

  function dosDateTime(date) {
    return {
      time: (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1),
      date: ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    };
  }

  function concat(parts) {
    const total = parts.reduce((sum, part) => sum + part.length, 0);
    const out = new Uint8Array(total);
    let offset = 0;
    for (const part of parts) { out.set(part, offset); offset += part.length; }
    return out;
  }

  // entries: [{ name, data: Uint8Array }], all stored without compression
  function zip(entries, date) {
    const stamp = dosDateTime(date || new Date());
    const local = [];
    const central = [];
    let offset = 0;
    for (const entry of entries) {
      const name = encoder.encode(entry.name);
      const crc = crc32(entry.data);
      const size = entry.data.length;

      const header = new DataView(new ArrayBuffer(30));
      header.setUint32(0, 0x04034b50, true);
      header.setUint16(4, 20, true);
      header.setUint16(6, 0x0800, true);
      header.setUint16(8, 0, true);
      header.setUint16(10, stamp.time, true);
      header.setUint16(12, stamp.date, true);
      header.setUint32(14, crc, true);
      header.setUint32(18, size, true);
      header.setUint32(22, size, true);
      header.setUint16(26, name.length, true);
      header.setUint16(28, 0, true);
      local.push(new Uint8Array(header.buffer), name, entry.data);

      const record = new DataView(new ArrayBuffer(46));
      record.setUint32(0, 0x02014b50, true);
      record.setUint16(4, 20, true);
      record.setUint16(6, 20, true);
      record.setUint16(8, 0x0800, true);
      record.setUint16(10, 0, true);
      record.setUint16(12, stamp.time, true);
      record.setUint16(14, stamp.date, true);
      record.setUint32(16, crc, true);
      record.setUint32(20, size, true);
      record.setUint32(24, size, true);
      record.setUint16(28, name.length, true);
      record.setUint16(30, 0, true);
      record.setUint16(32, 0, true);
      record.setUint16(34, 0, true);
      record.setUint16(36, 0, true);
      record.setUint32(38, 0, true);
      record.setUint32(42, offset, true);
      central.push(new Uint8Array(record.buffer), name);

      offset += 30 + name.length + size;
    }
    const centralSize = central.reduce((sum, part) => sum + part.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true);
    end.setUint16(4, 0, true);
    end.setUint16(6, 0, true);
    end.setUint16(8, entries.length, true);
    end.setUint16(10, entries.length, true);
    end.setUint32(12, centralSize, true);
    end.setUint32(16, offset, true);
    end.setUint16(20, 0, true);
    return concat([...local, ...central, new Uint8Array(end.buffer)]);
  }

  // build(sheetName, header: string[], rows: any[][]) -> Uint8Array with the workbook bytes
  function build(sheetName, header, rows, date) {
    const name = String(sheetName).replace(/[\\/?*[\]:]/g, '_').slice(0, 31) || 'Sheet1';
    return zip([
      { name: '[Content_Types].xml', data: encoder.encode(CONTENT_TYPES) },
      { name: '_rels/.rels', data: encoder.encode(ROOT_RELS) },
      { name: 'xl/workbook.xml', data: encoder.encode(workbookXml(name)) },
      { name: 'xl/_rels/workbook.xml.rels', data: encoder.encode(WORKBOOK_RELS) },
      { name: 'xl/worksheets/sheet1.xml', data: encoder.encode(sheetXml(header, rows)) },
    ], date);
  }

  const MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

  return { build, zip, crc32, columnName, escapeXml, MIME };
});
