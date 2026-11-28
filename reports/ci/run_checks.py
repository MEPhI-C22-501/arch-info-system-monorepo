"""All Reports checks with one command on any machine with Docker: python reports/ci/run_checks.py

The checks run in the Linux image reports/ci/checks.Dockerfile, the same set as CI
(record_checks.py --native-postgres): tests on a temporary PostgreSQL, Cube
measures and scope, neighbour contracts, UI tests and build, diagrams, the
secret scan. Node dependencies live in named Docker volumes, so the host's
node_modules (for example Windows binaries) are never used. The result is
reports/pilots/artifacts/verification.json; the summary lists every skipped
test with its reason.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'reports-checks'
VOLUMES = {'reports-cube-nm': 'reports/pilots/cube/node_modules', 'reports-ui-nm': 'reports/pilots/ui/node_modules',
           'reports-ci-nm': 'reports/ci/node_modules'}


def docker(*arguments, root=False, check=True):
    mounts = ['-v', f'{ROOT}:/src'] + [x for name, path in VOLUMES.items() for x in ('-v', f'{name}:/src/{path}')]
    # The repository belongs to the host user; git inside the container must accept it.
    env = ['-e', 'GIT_CONFIG_COUNT=1', '-e', 'GIT_CONFIG_KEY_0=safe.directory', '-e', 'GIT_CONFIG_VALUE_0=/src']
    command = ['docker', 'run', '--rm', *(['-u', '0'] if root else []), *mounts, *env, '-w', '/src', IMAGE, *arguments]
    return subprocess.run(command, check=check)


def main():
    # The summary is Russian; a pipe or a Windows console must not garble it.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    subprocess.run(['docker', 'build', '-q', '-f', str(ROOT/'reports/ci/checks.Dockerfile'), '-t', IMAGE, str(ROOT/'reports/pilots')], check=True)
    # Linux dependencies once per volume; npm ci follows the lock file of the UI.
    docker('sh', '-c', 'cd /src && '
           '(test -d reports/pilots/ui/node_modules/vitest || npm ci --no-audit --no-fund --prefix reports/pilots/ui) && '
           '(test -d reports/pilots/cube/node_modules/@cubejs-backend || npm install --no-audit --no-fund --prefix reports/pilots/cube) && '
           '(test -d reports/ci/node_modules/mermaid || npm install --no-audit --no-fund --no-package-lock --prefix reports/ci) && '
           'chown -R 1000:1000 ' + ' '.join(VOLUMES.values()), root=True)
    code = docker('python', 'reports/ci/record_checks.py', '--native-postgres', check=False).returncode
    result = json.loads((ROOT/'reports/pilots/artifacts/verification.json').read_text(encoding='utf-8'))
    failed = [c['name'] for c in result.get('checks', []) if c['exit_code']]
    print(f"\nПроверок: {len(result.get('checks', []))}, не пройдено: {len(failed)}" + (f" — {', '.join(failed)}" if failed else ''))
    skipped = result.get('skipped_tests', [])
    print(f'Пропущено тестов: {len(skipped)}' + ''.join(f"\n- {s['test']}: {s['reason']}" for s in skipped))
    return code


if __name__ == '__main__':
    sys.exit(main())
