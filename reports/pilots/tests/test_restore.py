"""Round-trip a real PostgreSQL dump into a separate disposable database."""
import hashlib
import json
import os
import secrets
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path

from test_pipeline import Tracker
from api import report
from db import Database
from demo import MEMBER_1, MEMBER_2, fixture
from etl import load, tracker_extract


@unittest.skipUnless(os.getenv('REPORTS_TEST_DATABASE_URL'), 'PostgreSQL test DSN not supplied')
class Restore(unittest.TestCase):
    def test_dump_restore_preserves_data_history_checkpoint_and_scope(self):
        import pgserver
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import conninfo_to_dict, make_conninfo
        admin_dsn = os.environ['REPORTS_TEST_DATABASE_URL']
        admin = psycopg.connect(admin_dsn, autocommit=True)
        capability = admin.execute('SELECT rolcreatedb,rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()
        if not any(capability):
            admin.close(); self.skipTest('Restore test requires an isolated role with CREATEDB')
        names = ['reports_restore_'+secrets.token_hex(6) for _ in range(2)]
        params = conninfo_to_dict(admin_dsn)
        binaries = Path(pgserver.__file__).parent/'pginstall/bin'
        def utility(name, database, options, input=None):
            env = os.environ.copy()
            for key in ('host', 'port', 'user', 'password'):
                if key in params: env['PG'+key.upper()] = params[key]
            env['PGDATABASE'] = database
            return subprocess.run([str(binaries/name), *options], env=env, input=input,
                                  capture_output=True, timeout=60)
        try:
            for name in names: admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            source = Database(make_conninfo(**dict(params, dbname=names[0])))
            try:
                source.initialize()
                with source.transaction():
                    for subject in (MEMBER_1, MEMBER_2):
                        source.execute('INSERT INTO app.subject_binding VALUES (?,?)', (subject, subject))
                load(source, 'tracker', lambda: tracker_extract(Tracker()))
                changed = fixture(); changed['work-items'][0]['plannedHours'] = 22
                load(source, 'tracker', lambda: tracker_extract(Tracker(changed)))
                checkpoint = source.execute("SELECT value FROM etl.checkpoint WHERE source='tracker'").fetchone()[0]
            finally: source.close()
            dump = utility('pg_dump', names[0], ['--format=custom', '--no-owner', '--no-acl'])
            self.assertEqual(dump.returncode, 0, 'pg_dump failed')
            restored = utility('pg_restore', names[1], ['--dbname='+names[1], '--exit-on-error', '--no-owner', '--no-acl'], dump.stdout)
            self.assertEqual(restored.returncode, 0, 'pg_restore failed')
            target = Database(make_conninfo(**dict(params, dbname=names[1])))
            try:
                target.initialize()  # An upgrade/start after restore is idempotent.
                self.assertEqual(target.execute('SELECT SUM(hours_cents) FROM dwh.fact_time_log').fetchone()[0], 1125)
                self.assertEqual(target.execute('SELECT COUNT(*) FROM dwh.dimension_version').fetchone()[0], 4)
                self.assertEqual(target.execute('SELECT COUNT(*) FROM dwh.source_snapshot').fetchone()[0], 10)
                self.assertEqual(target.execute("SELECT value FROM etl.checkpoint WHERE source='tracker'").fetchone()[0], checkpoint)
                claims = {'sub': MEMBER_1, 'resource_access': {'reports': {'roles': ['reports-member']}}}
                self.assertEqual(sum(row['hours'] for row in report(target, claims)['data']), 3.75)
                # Replaying the restored batch must not double the hours/history.
                load(target, 'tracker', lambda: tracker_extract(Tracker(changed)))
                self.assertEqual(target.execute('SELECT COUNT(*) FROM dwh.fact_time_log').fetchone()[0], 6)
                self.assertEqual(target.execute('SELECT COUNT(*) FROM dwh.dimension_version').fetchone()[0], 4)
                damaged = utility('pg_restore', names[1], ['--dbname='+names[1], '--exit-on-error'], b'not a PostgreSQL archive')
                self.assertNotEqual(damaged.returncode, 0)
            finally: target.close()
            if os.getenv('REPORTS_RECORD_ARTIFACTS') == '1':
                root = Path(__file__).resolve().parents[3]
                sources = ['reports/pilots/tests/test_restore.py', 'reports/pilots/db.py',
                           'reports/pilots/etl.py', 'reports/pilots/demo.py']
                result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': True,
                          'scope': 'Isolated synthetic Reports database; no shared stand or Keycloak backup',
                          'checks': ['real_pg_dump_restore', 'hours', 'scd2_versions', 'daily_snapshot',
                                     'checkpoint', 'member_scope', 'idempotent_replay', 'invalid_archive_rejected'],
                          'source_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources}}
                (root/'reports/pilots/artifacts/restore-verification.json').write_text(json.dumps(result, indent=2)+'\n')
        finally:
            for name in names:
                admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))
            admin.close()
