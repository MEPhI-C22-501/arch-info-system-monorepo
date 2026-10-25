"""Check local links, JSON contracts, YAML and Python syntax without services."""
import ast
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
errors, links, diagrams = [], 0, 0
def sources(pattern):
    return (p for p in ROOT.rglob(pattern) if not {'.venv', 'node_modules', '__pycache__'}.intersection(p.relative_to(ROOT).parts))

for path in sources('*.md'):
    text = path.read_text()
    for obsolete in ['кода Reports в репозитории ещё нет', 'проверка — после появления кода',
                     'проверка возможна только после кода', 'Docker на машине проверки отсутствует',
                     'Контейнерный и браузерный прогон ещё требуется']:
        if obsolete in text:
            errors.append(f'{path.relative_to(ROOT)}: obsolete implementation status')
    diagrams += len(re.findall(r'^```mermaid\s*$', text, re.M))
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if target.startswith(('http:', 'https:', 'mailto:', '#')):
            continue
        target = unquote(urlsplit(target.strip('<>')).path)
        if target and not (path.parent / target).exists():
            errors.append(f'{path.relative_to(ROOT)}: missing {target}')
        links += 1
for path in sources('*.py'):
    ast.parse(path.read_text(), filename=str(path))
for path in sources('*.yaml'):
    list(yaml.safe_load_all(path.read_text()))
for path in sources('*.json'):
    value = json.loads(path.read_text())
    if path.name.endswith('.schema.json'):
        Draft202012Validator.check_schema(value)
matrix = (ROOT/'docs/095.requirements-check.md').read_text()
statuses = Counter(re.findall(r'^\| (?:FR|NFR|INT)-[^\n]+\| (covered|partial|missing)[^|]*\|\s*$', matrix, re.M))
summary = re.search(r'covered — (\d+), partial — (\d+), missing — (\d+)', matrix)
if not summary or tuple(statuses[key] for key in ('covered', 'partial', 'missing')) != tuple(map(int, summary.groups())):
    errors.append('095: coverage totals disagree with the matrix rows')
for name, row_id in [('075.nfr.md', 'NFR-04.2'), ('146.logic-scheme.md', 'F-03')]:
    row = next((line for line in (ROOT/'docs'/name).read_text().splitlines() if line.startswith('| '+row_id+' |')), '')
    if '60 секунд' not in row:
        errors.append(name+': Tracker polling interval disagrees with the accepted local fallback')
execution = (ROOT/'docs/test-evidence.md').read_text()
test_ids = re.findall(r'^\| (T-\d{2}) \|', execution, re.M)
if len(test_ids) != 35 or set(test_ids) != {f'T-{i:02d}' for i in range(1, 36)}:
    errors.append('test-evidence: each T-01…T-35 must appear exactly once')
if errors:
    raise SystemExit('\n'.join(errors))
print(json.dumps({'local_links': links, 'mermaid_blocks': diagrams, 'syntax': 'passed',
                  'documentation_statuses': 'passed', 'coverage': dict(statuses)}))
