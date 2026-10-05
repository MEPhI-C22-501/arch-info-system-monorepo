"""Validate document links, traceability, OpenAPI and event examples.

python -m pip install -r planning-system/scripts/requirements-docs.txt
python planning-system/scripts/validate-docs.py
Application/runtime integration tests are separate.
"""
from pathlib import Path
import copy
import json
import re
import sys
from urllib.parse import unquote, urlsplit
from collections import Counter
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate

root = Path(__file__).resolve().parents[2]
module = root / 'planning-system'
docs = module / 'docs'
errors = []
counts = Counter()

def check(condition, message):
    if not condition:
        errors.append(message)

def anchors(text):
    result = set(re.findall(r'<a\s+id="([^"]+)"', text))
    used = Counter()
    for h in re.findall(r'^#{1,6}\s+(.+)', text, re.M):
        h = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', h)
        slug = re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-')
        n = used[slug]
        used[slug] += 1
        result.add(slug + (f'-{n}' if n else ''))
    return result

for file in module.rglob('*.md'):
    text = file.read_text(encoding='utf-8')
    visible = re.sub(r'```.*?```', '', text, flags=re.S)
    for target in re.findall(r'\]\(([^)]+)\)', visible):
        target = target.strip().strip('<>')
        if urlsplit(target).scheme:
            continue
        name, _, anchor = unquote(target).partition('#')
        dest = (file.parent / name).resolve() if name else file
        counts['links'] += 1
        check(dest.exists(), f'{file.relative_to(root)}: missing {target}')
        if dest.is_file() and dest.suffix == '.md' and anchor:
            check(anchor in anchors(dest.read_text(encoding='utf-8')),
                  f'{file.relative_to(root)}: missing anchor {target}')
    # A blank line splitting a table body creates an unrendered Markdown row.
    for block in re.findall(r'(?:^\|.*\n)+', text, re.M):
        lines = block.splitlines()
        check(len(lines) >= 2 and re.match(r'^\|[ :|-]+\|$', lines[1]),
              f'{file.relative_to(root)}: table body without header: {lines[0][:65]}')
    counts['markdown'] += 1

for number in ['010','020','030','040','050','060','070','075','080','090','095','110','115','120','130','135','140','145','146','150','155','160','162','165']:
    check(any(docs.glob(number+'.*.md')), f'Missing document {number}')
matrix=(docs/'095.requirements-check.md').read_text(encoding='utf-8')
rows=re.findall(r'^\| ((?:FR|INT|NFR|TECH)-\d+) \|.*',matrix,re.M)
check(len(rows)==45 and len(set(rows))==45,'Expected 45 unique requirements')
statuses=Counter(re.findall(r'^\| (?:FR|INT|NFR|TECH)-\d+ \|.*?\| (covered|partial|missing) \|',matrix,re.M))
check(statuses=={'covered':17,'partial':28},f'Coverage counts differ: {dict(statuses)}')
stories=[]
for f in docs.glob('080.*.md'):
    stories+=re.findall(r'^## (US-[A-Z]+-\d+)',f.read_text(encoding='utf-8'),re.M)
check(len(stories)==20 and len(set(stories))==20,'Expected 20 unique stories')
for story in stories:
    check(story in matrix,f'{story} missing from traceability')

format_checker=FormatChecker()
for file in sorted((docs/'contracts/events').glob('*.schema.json')):
    schema=json.loads(file.read_text(encoding='utf-8'))
    sample=json.loads(file.with_name(file.name.replace('.schema','.example')).read_text(encoding='utf-8'))
    try:
        Draft202012Validator.check_schema(schema)
        v=Draft202012Validator(schema,format_checker=format_checker)
        v.validate(sample)
        for field in schema['required']:
            bad=copy.deepcopy(sample); del bad[field]
            check(not v.is_valid(bad),f'{file.name} accepts missing {field}')
        bad=copy.deepcopy(sample);bad['eventId']='invalid-uuid'
        check(not v.is_valid(bad),f'{file.name} accepts malformed ID')
        if 'actualHours' in sample['payload']:
            bad=copy.deepcopy(sample);bad['payload']['actualHours']=-1
            check(not v.is_valid(bad),f'{file.name} accepts negative actualHours')
    except Exception as exc:
        errors.append(f'{file.name}: {exc}')
    counts['events']+=1

for file in [docs/'contracts/openapi.json',docs/'contracts/task-tracker-receiver.openapi.json']:
    spec=json.loads(file.read_text(encoding='utf-8'))
    try:
        validate(spec)
        for route, methods in spec['paths'].items():
            for method,op in methods.items():
                media=[]
                if 'requestBody' in op: media+=list(op['requestBody']['content'].values())
                for response in op['responses'].values():media+=list(response.get('content',{}).values())
                for content in media:
                    schema={**content['schema'],'components':spec['components']}
                    samples=[content['example']] if 'example' in content else []
                    samples += [x['value'] for x in content.get('examples',{}).values()]
                    for sample in samples:
                        Draft202012Validator(schema,format_checker=format_checker).validate(sample)
                        counts['http_examples']+=1
                counts['operations']+=1
    except Exception as exc:
        errors.append(f'{file.name}: {exc}')

spec=json.loads((docs/'contracts/openapi.json').read_text(encoding='utf-8'))
fixtures=json.loads((docs/'contracts/http-examples.json').read_text(encoding='utf-8'))
by_id={op['operationId']:op for methods in spec['paths'].values() for op in methods.values()}
check(set(by_id)=={f['operationId'] for f in fixtures},'HTTP example operation coverage mismatch')
for f in fixtures:
    op=by_id[f['operationId']]
    for case in ['success','failure']:
        response=f[case]['response']
        content=op['responses'][str(response['status'])]['content']
        schema=next(iter(content.values()))['schema']
        try:
            Draft202012Validator({**schema,'components':spec['components']},format_checker=format_checker).validate(response['body'])
            if case=='success' and 'body' in f[case]['request']:
                schema=op['requestBody']['content']['application/json']['schema']
                Draft202012Validator({**schema,'components':spec['components']},format_checker=format_checker).validate(f[case]['request']['body'])
        except Exception as exc:errors.append(f"{f['operationId']}/{case}: {exc}")

print(json.dumps({'checks':dict(counts),'requirements':dict(statuses),'stories':len(stories),'errors':len(errors)},ensure_ascii=False))
for error in errors: print(error)
sys.exit(bool(errors))
