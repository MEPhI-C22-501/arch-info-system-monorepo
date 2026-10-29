"""Repeatable document inventory and requirement/story/link trace audit."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from collections import Counter

root=Path(__file__).resolve().parents[2];module=root/'planning-system';docs=module/'docs'
matrix=(docs/'095.requirements-check.md').read_text()
tz=(docs/'technical-specification.md').read_text();nfr=(docs/'075.nfr.md').read_text()
errors=[]
rows={m.group(1):m.group(0) for m in re.finditer(r'^\| ((?:FR|INT|NFR|TECH)-\d+) \|.*$',matrix,re.M)}
expected={*(f'FR-{i:02}' for i in range(1,16)),*(f'INT-{i:02}' for i in range(1,9)),*(f'NFR-{i:02}' for i in range(1,17)),*(f'TECH-{i:02}' for i in range(1,7))}
if set(rows)!=expected:errors.append('Requirement inventory differs')
if set(re.findall(r'^\| (FR-\d+) \|',tz,re.M))!={f'FR-{i:02}' for i in range(1,16)}:errors.append('FR inventory differs from technical specification')
nfr_ids=set(re.findall(r'NFR-\d+',nfr))
if not {f'NFR-{i:02}' for i in range(1,17)}<=nfr_ids:errors.append('NFR inventory differs from 075')
for key,row in rows.items():
 if 'T-'+key not in row:errors.append(key+' has no test specification')
 if not re.search(r'\| (covered|partial|missing) \|',row):errors.append(key+' has no status')
stories={story:[] for f in docs.glob('080.*.md') for story in re.findall(r'^## (US-[A-Z]+-\d+)',f.read_text(),re.M)}
for story in stories:
 stories[story]=[key for key,row in rows.items() if story in row]
 if not stories[story]:errors.append(story+' is untraced')
counts=Counter(re.findall(r'^\| (?:FR|INT|NFR|TECH)-\d+ \|.*?\| (covered|partial|missing) \|',matrix,re.M))
# Hash exact review inputs; exclude this generated audit and execution outputs.
source_suffixes={'.md','.py','.mjs','.js','.css','.html','.json','.txt','.yaml','.yml','.sql'}
inputs={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for folder in [docs,module/'scripts',module/'server',module/'ui',module/'migrations',module/'deploy',module/'dev'] for f in sorted(folder.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.suffix in source_suffixes}
for f in sorted(module.glob('*')):
 if f.is_file() and (f.suffix in {'.md','.yaml','.yml'} or f.name in {'Dockerfile','.env.example','Dockerfile.dockerignore'}):inputs[str(f.relative_to(root))]=hashlib.sha256(f.read_bytes()).hexdigest()
for f in sorted((root/'.github/workflows').glob('planning*')):inputs[str(f.relative_to(root))]=hashlib.sha256(f.read_bytes()).hexdigest()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
base=re.search(r'База повторной сверки: `main` на коммите `([0-9a-f]{40})`',matrix)
if not base:errors.append('095 must name the exact main base commit')
report={'baseMain':base.group(1) if base else None,'checkoutHead':head,'workingTreeInputs':True,
        'requirements':len(rows),'coverage':dict(counts),'stories':stories,'inputSha256':inputs,'errors':errors,
        'meaning':'Document traceability; not runtime or integration acceptance'}
out=module/'artifacts/document-audit.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'requirements':len(rows),'coverage':dict(counts),'stories':len(stories),'hashedInputs':len(inputs),'errors':errors},ensure_ascii=False))
raise SystemExit(bool(errors))
