// @vitest-environment node
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { expect, test } from 'vitest';

const ROOT = resolve(import.meta.dirname, '../..');
const SCHEMA = 'src/api/schema.d.ts';

test('schema.d.ts собран из текущей openapi.yaml: иначе выполните npm run gen:api', () => {
  const script: string = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).scripts['gen:api'];
  const [tool, ...args] = script.split(' ');
  const directory = mkdtempSync(join(tmpdir(), 'qa-schema-'));
  try {
    const generated = join(directory, 'schema.d.ts');
    const toolArgs = args.map((arg) => (arg === SCHEMA ? generated : arg));
    execFileSync(join(ROOT, 'node_modules/.bin', tool), toolArgs, { cwd: ROOT, stdio: 'pipe' });
    expect(readFileSync(generated, 'utf8')).toBe(readFileSync(join(ROOT, SCHEMA), 'utf8'));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}, 30_000);
