"""Neighbours' contracts that Reports reads, checked against the shared catalog api/openapi.

For every operation the Reports adapters call, the operation is taken from the
owner's spec in the shared catalog with all $ref expanded, and its SHA-256 is
compared with reports/ci/contracts.lock.json. A change in what Reports reads
fails the check and names the neighbour and the operation; a change elsewhere in
the neighbour's spec does not. After the adapter is checked against the new
format, record it: python reports/ci/check_contracts.py --update
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT/'reports/ci/contracts.lock.json'
RM = 'api/openapi/reference-manager/{}/openapi.yaml'
# Operations called by reports/pilots/adapters.py and etl.py, by owner.
NEIGHBOURS = {
    'task-tracker': ('api/openapi/task-tracker/v1/openapi.yaml', [
        ('get', '/reports/work-items'), ('get', '/reports/time-logs'), ('get', '/reports/iterations'),
        ('get', '/reports/statuses'), ('get', '/reports/history')]),
    'planning-system': ('api/openapi/planning-system/v1/openapi.json', [
        ('post', '/api/v1/exports'), ('get', '/api/v1/exports/{batchId}'), ('get', '/api/v1/exports/{batchId}/rows')]),
    'qa': ('api/openapi/qa/v1/openapi.yaml', [('get', '/reports/{resource}')]),
    **{f'reference-manager/{name}': (RM.format(name), [('get', f'/v1/{name}s/')])
       for name in ['employee', 'org_unit', 'position', 'project_role', 'grade']},
    'reference-manager/profile': (RM.format('profile'), [('get', '/v1/profiles')]),
}


def expanded(node, spec, seen=()):
    """The node with every local $ref replaced by its target; a cycle keeps the reference name."""
    if isinstance(node, dict):
        ref = node.get('$ref')
        if isinstance(ref, str) and ref.startswith('#/'):
            if ref in seen: return {'$ref': ref}
            target = spec
            for part in ref[2:].split('/'): target = target[part.replace('~1', '/').replace('~0', '~')]
            return expanded(target, spec, seen+(ref,))
        return {k: expanded(v, spec, seen) for k, v in node.items()}
    if isinstance(node, list): return [expanded(v, spec, seen) for v in node]
    return node


def fingerprints():
    result, missing = {}, []
    for owner, (file, operations) in NEIGHBOURS.items():
        text = (ROOT/file).read_text(encoding='utf-8')
        spec = json.loads(text) if file.endswith('.json') else yaml.safe_load(text)
        result[owner] = {'file': file, 'operations': {}}
        for method, path in operations:
            operation = (spec.get('paths') or {}).get(path, {}).get(method)
            name = f'{method.upper()} {path}'
            if operation is None:
                missing.append(f'{owner}: в {file} нет операции {name}')
                continue
            canonical = json.dumps(expanded(operation, spec), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            result[owner]['operations'][name] = hashlib.sha256(canonical.encode()).hexdigest()
    return result, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update', action='store_true', help='Record the current formats after checking the adapters')
    args = parser.parse_args()
    current, missing = fingerprints()
    if args.update:
        if missing: print('\n'.join(missing)); return 1
        LOCK.write_text(json.dumps(current, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(f'Recorded {sum(len(v["operations"]) for v in current.values())} operations of {len(current)} contracts')
        return 0
    locked = json.loads(LOCK.read_text(encoding='utf-8'))
    problems = list(missing)
    for owner, entry in current.items():
        before = locked.get(owner, {}).get('operations', {})
        changed = [name for name, digest in entry['operations'].items() if before.get(name) != digest]
        if changed:
            problems.append(f'{owner} изменил контракт {entry["file"]}: ' + ', '.join(changed))
    if problems:
        print('Контракты соседей, по которым читает Reports, изменились:')
        print('\n'.join('- ' + p for p in problems))
        print('Проверьте адаптер reports/pilots/adapters.py по новому формату, затем: python reports/ci/check_contracts.py --update')
        return 1
    print(json.dumps({'neighbour_contracts': 'unchanged', 'operations': {o: len(v['operations']) for o, v in current.items()}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
