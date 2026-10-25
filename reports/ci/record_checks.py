"""Record actual local check exits and source hashes. No credentials collected."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT/'reports'
ARTIFACTS = REPORTS/'pilots/artifacts'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-postgres', action='store_true')
    parser.add_argument('--bi', action='store_true', help='Also exercise the running local Keycloak/Superset stack')
    args = parser.parse_args()
    ARTIFACTS.mkdir(exist_ok=True)
    path = ARTIFACTS/'verification.json'
    path.write_text(json.dumps({'state': 'running'}))
    test = ['reports/pilots/check_postgres.py', '--record'] if args.native_postgres else ['-m', 'unittest', 'discover', '-s', 'reports/pilots/tests', '-v']
    node = os.getenv('NODE', 'node')
    commands = [
        ('contracts-and-links', [sys.executable, 'reports/ci/validate.py']),
        ('python-tests', [sys.executable, *test]),
        ('cube-scope-tests', [node, '--test', 'reports/pilots/tests/cube-auth.test.cjs']),
        ('ui-javascript-syntax', [node, '--check', 'reports/pilots/ui/app.js']),
        ('mermaid-grammar', [node, 'reports/ci/check_diagrams.mjs', '--record']),
        ('diff-check', ['git', 'diff', '--check', '--', 'reports']),
    ]
    if args.bi:
        commands.append(('real-kafka-events', [sys.executable, 'reports/pilots/record_events.py']))
        commands.append(('keycloak-role-revocation', [sys.executable, 'reports/pilots/check_roles.py', '--record']))
        commands.append(('keycloak-superset', [sys.executable, 'reports/pilots/check_bi.py', '--record', '--benchmark']))
        commands.append(('reports-product', [sys.executable, 'reports/pilots/check_product.py', '--record']))
        commands.append(('bi-session-expiry', [sys.executable, 'reports/pilots/launch.py', 'exec', '-T',
                                               'superset', 'python', '/app/pythonpath/check_session.py']))
    commands.append(('reports-secret-scan', [sys.executable, 'reports/ci/check_secrets.py', '--record']))
    if args.native_postgres:
        commands.insert(2,('cube-all-measures',[sys.executable,'reports/pilots/check_semantics.py']))
    checks, logs = [], []
    for name, command in commands:
        if name == 'reports-secret-scan':
            # Include this run's logs in the scan, not just a previous run.
            (ARTIFACTS/'checks.log').write_text('\n'.join(logs))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        checks.append({'name': name, 'exit_code': result.returncode})
        logs.append(name+'\n'+result.stdout+result.stderr)
        print(name, 'passed' if result.returncode == 0 else 'failed')
    hashes = {}
    for source in REPORTS.rglob('*'):
        relative = source.relative_to(ROOT)
        if source.is_file() and not {'artifacts', '.venv', 'node_modules', '__pycache__'}.intersection(relative.parts):
            hashes[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    contracts = ['task-tracker/docs/block-g-api-and-events/openapi.yaml',
                 'qa/api/openapi/v1/openapi.yaml', 'planning-system/docs/contracts/openapi.json',
                 'reference-manager/backend/api/openapi/v1/employee/openapi.yaml']
    for name in contracts: hashes[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    output = {'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'native_postgres_test': args.native_postgres, 'checks': checks, 'source_sha256': hashes,
              'container_stack_verified': args.bi and all(c['exit_code'] == 0 for c in checks if c['name'] in
                  {'keycloak-superset', 'keycloak-role-revocation', 'bi-session-expiry'}),
              'real_source_integrations_verified': False,
              'local_restore_verified': args.native_postgres and json.loads((ARTIFACTS/'restore-verification.json').read_text()).get('passed', False),
              'product_verified': args.bi and any(c['name']=='reports-product' and c['exit_code']==0 for c in checks),
              'github_workflow_registered': False, 'passed': all(c['exit_code'] == 0 for c in checks)}
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    (ARTIFACTS/'checks.log').write_text('\n'.join(logs))
    return 0 if output['passed'] else 1


if __name__ == '__main__': sys.exit(main())
