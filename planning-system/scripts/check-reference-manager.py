"""Read real HR collections; optionally replace only the current local cache.

Credentials come from RM_TOKEN or the configured client-credentials endpoint.
The report contains counts and a digest, never employee data or credentials.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import storage as db
from server.reference_manager import ReferenceManagerClient, ReferenceManagerError, refresh_cache, snapshot_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', help='Reference Manager URL ending in /v1; otherwise RM_BASE_URL')
    parser.add_argument('--sync', action='store_true', help='Atomically update the current HR cache in DATABASE_URL')
    parser.add_argument('--read-time', help='Optional fixed RFC3339 UTC snapshot time')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'artifacts/reference-manager-report.json')
    args = parser.parse_args()
    if args.base_url:os.environ['RM_BASE_URL'] = args.base_url
    try:
        client = ReferenceManagerClient.from_env()
        if args.sync:
            db.migrate()
            report = refresh_cache(client, read_time=args.read_time)
        else:
            report = snapshot_summary(client.fetch(read_time=args.read_time))
        report.update(passed=True, mode='live-source', cacheUpdated=args.sync)
    except ReferenceManagerError as exc:
        report = {'source': 'ReferenceManager', 'passed': False, 'error': str(exc), 'cacheUpdated': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
