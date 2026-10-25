"""Scan Reports sources and recorded logs without displaying any secret value."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote

from dotenv import dotenv_values

KEYS = (
    'REPORTS_DB_PASSWORD', 'REPORTS_APP_DB_PASSWORD', 'REPORTS_CUBE_DB_PASSWORD', 'REPORTS_CUBE_SQL_PASSWORD',
    'REPORTS_SUPERSET_SECRET_KEY', 'REPORTS_SUPERSET_CLIENT_SECRET',
    'REPORTS_KC_ADMIN_PASSWORD', 'REPORTS_DEMO_ADMIN_PASSWORD',
    'REPORTS_DEMO_MEMBER_PASSWORD', 'REPORTS_SOURCE_TOKEN', 'REPORTS_DATABASE_URL',
)
EXCLUDED = {'.venv', 'node_modules', '__pycache__', '.cubestore', '.git'}
PRIVATE_KEY = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----')
JWT = re.compile(rb'(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{16,}')


def scan(root, values):
    needles = set()
    for value in values:
        if value:
            needles.update({value.encode(), quote(value, safe='').encode(),
                            json.dumps(value)[1:-1].encode()})
    findings, count = [], 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not path.is_file() or EXCLUDED.intersection(relative.parts) or path.suffix == '.pyc':
            continue
        count += 1
        data = path.read_bytes()
        reasons = []
        if any(value in data for value in needles): reasons.append('known-secret')
        if PRIVATE_KEY.search(data): reasons.append('private-key')
        if JWT.search(data): reasons.append('unredacted-jwt')
        if reasons: findings.append({'path': str(relative), 'reasons': reasons})
    return {'passed': not findings, 'files_scanned': count, 'findings': findings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    secret_file = Path.home()/'secrets.env'
    values = dotenv_values(secret_file) if secret_file.is_file() else {}
    result = scan(root, [values.get(key) for key in KEYS])
    result['known_values_checked'] = sum(bool(values.get(key)) for key in KEYS)
    result['scope'] = 'Reports files including artifacts and logs; excludes dependency/cache directories'
    if args.record:
        (root/'pilots/artifacts/secret-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
