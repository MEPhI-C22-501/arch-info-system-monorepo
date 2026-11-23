// The forms and filters of the panel come from the catalog descriptions of js/catalogs.js (ADR-026). This test reads
// the OpenAPI spec of every catalog and fails when a form field, its required flag or a read-only field differs from
// the spec, so the descriptions cannot drift from the contract (FR-RM-29, FR-RM-38).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { CATALOGS } = require('../js/catalogs.js');

const SPECS = path.join(__dirname, '..', '..', '..', 'backend', 'api', 'openapi', 'v1');

// collection of the panel -> folder of its spec and the name of its record schema
const SPEC_OF = {
  currencies: ['currency', 'Currency'],
  countries: ['country', 'Country'],
  project_roles: ['project_role', 'ProjectRole'],
  grades: ['grade', 'Grade'],
  org_units: ['org_unit', 'OrgUnit'],
  positions: ['position', 'Position'],
  employees: ['employee', 'Employee'],
  assignments: ['assignment', 'Assignment'],
  salaries: ['salary', 'Salary'],
  absences: ['absence', 'Absence'],
};

// the generated specs keep one layout: a schema under "  schemas:" at four spaces, its keys at six, properties at eight
function schema(file, name) {
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  const start = lines.findIndex((line, i) => line === `    ${name}:` && lines.slice(0, i).includes('  schemas:'));
  assert.notEqual(start, -1, `schema ${name} in ${file}`);
  const body = [];
  for (const line of lines.slice(start + 1)) {
    if (/^ {0,4}\S/.test(line)) break;
    body.push(line);
  }
  const section = (key) => {
    const from = body.indexOf(`      ${key}:`);
    if (from === -1) return [];
    const out = [];
    for (const line of body.slice(from + 1)) {
      if (/^ {0,6}\S/.test(line)) break;
      out.push(line);
    }
    return out;
  };
  return {
    properties: section('properties').map((l) => /^ {8}([a-z_0-9]+):$/.exec(l)).filter(Boolean).map((m) => m[1]),
    required: section('required').map((l) => /^ {8}- ([a-z_0-9]+)$/.exec(l)).filter(Boolean).map((m) => m[1]),
  };
}

test('every catalog of the panel has a spec and every catalog spec has a panel description', () => {
  assert.deepEqual(Object.keys(SPEC_OF).sort(), Object.keys(CATALOGS).sort());
  const folders = fs.readdirSync(SPECS).filter((name) => !['health', 'profile'].includes(name)).sort();
  assert.deepEqual(Object.values(SPEC_OF).map(([folder]) => folder).sort(), folders);
});

for (const [collection, [folder, name]] of Object.entries(SPEC_OF)) {
  test(`${collection}: form fields and required flags follow the spec`, () => {
    const file = path.join(SPECS, folder, 'openapi.yaml');
    const record = schema(file, name);
    const fields = CATALOGS[collection].fields;
    assert.deepEqual(fields.map((f) => f.name).sort(), record.properties.filter((p) => p !== 'is_deleted').sort(), 'writable fields');
    assert.deepEqual(fields.filter((f) => f.required).map((f) => f.name).sort(), record.required.filter((p) => p !== 'is_deleted').sort(), 'required fields');
  });

  test(`${collection}: read-only fields of the form exist in the expanded record of the spec`, () => {
    const file = path.join(SPECS, folder, 'openapi.yaml');
    const expanded = schema(file, `Expanded${name}`).properties;
    for (const field of CATALOGS[collection].readOnly || []) {
      assert.ok(expanded.includes(field.name), `${field.name} in Expanded${name}`);
    }
  });
}
