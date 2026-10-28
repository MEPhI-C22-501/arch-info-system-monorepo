"""Optional native PostgreSQL regression, no Docker and no external database."""
import os
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
import pgserver
import psycopg
import fasteners


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    if args.record:
        os.environ['REPORTS_RECORD_ARTIFACTS'] = '1'
        (Path(__file__).with_name('artifacts')/'restore-verification.json').write_text(json.dumps({'passed': False, 'state': 'running'})+'\n')
    # Short, private Unix socket directory. PostgreSQL does not listen on TCP.
    with tempfile.TemporaryDirectory(prefix='rp-', dir='/tmp') as tmp:
        pgserver.PostgresServer.runtime_path = Path(tmp)/'run'
        pgserver.PostgresServer.lock_path = Path(tmp)/'pgserver.lock'
        pgserver.PostgresServer._lock = fasteners.InterProcessLock(pgserver.PostgresServer.lock_path)
        server = pgserver.get_server(Path(tmp)/'data', cleanup_mode='delete')
        try:
            uri = server.get_uri()
            with psycopg.connect(uri) as connection:
                print('Test PostgreSQL version:', connection.execute('SHOW server_version').fetchone()[0])
            os.environ['REPORTS_TEST_DATABASE_URL'] = uri
            suite = unittest.defaultTestLoader.discover(str(Path(__file__).with_name('tests')))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        finally:
            os.environ.pop('REPORTS_TEST_DATABASE_URL', None)
            server.cleanup()
    sys.exit(0 if result.wasSuccessful() else 1)
