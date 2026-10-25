import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(process.env.REPORTS_DIAGRAM_MODULES
  ? path.join(process.env.REPORTS_DIAGRAM_MODULES, 'package.json') : import.meta.url);
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { default: mermaid } = await import(pathToFileURL(require.resolve('mermaid')));
mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let parsed = 0;
const errors = [];
async function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['node_modules', '.venv', '__pycache__'].includes(entry.name)) continue;
    const target = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(target);
    else if (target.endsWith('.md')) {
      for (const match of fs.readFileSync(target, 'utf8').matchAll(/```mermaid\s*\n([\s\S]*?)```/g)) {
        try { await mermaid.parse(match[1]); parsed++; }
        catch (error) { errors.push({ file: path.relative(root, target), error: String(error) }); }
      }
    }
  }
}
await walk(root);
const result = { mermaid: '11.12.0', parsed, errors, grammar: errors.length ? 'failed' : 'passed', rendered: false };
if (process.argv.includes('--record')) {
  const dir = path.join(root, 'pilots', 'artifacts');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'diagrams.json'), JSON.stringify(result, null, 2)+'\n');
}
console.log(JSON.stringify(result));
if (errors.length) process.exitCode = 1;
