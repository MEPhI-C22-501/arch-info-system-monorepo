"""Real HTTP sources -> ETL -> isolated DWH -> signed-token HTTP report.

The PostgreSQL variant creates/drops its own database. Neither the working
pilot nor other teams' databases are touched. Keys exist only in memory.
"""
import hashlib
import json
import os
import secrets
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jsonschema import Draft202012Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance_data import EXPECTED, SEED, dataset, source_server, uid
from adapters import Client, Rejected
from api import Handler, authorize
from contracts import validate_tracker
from db import Database
from demo import MEMBER_1, MEMBER_2
from etl import catalog_extract, load, planning_extract, tracker_extract

ROOT = Path(__file__).resolve().parents[3]


@contextmanager
def report_server(dsn, issuer, public_key_url):
    class Report(Handler): jwks = jwt.PyJWKClient(public_key_url)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Report)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    with patch.dict(os.environ, {'REPORTS_DATABASE_URL': dsn, 'REPORTS_OIDC_ISSUER': issuer}):
        thread.start()
        try: yield 'http://127.0.0.1:'+str(server.server_port)
        finally: server.shutdown(); server.server_close(); thread.join()


def request(url, token=None, method='GET', headers=None):
    headers = dict(headers or {})
    if token is not None: headers['Authorization'] = 'Bearer '+token
    req = urllib.request.Request(url, headers=headers, method=method)
    try: response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error: response = error
    with response:
        return response.status, dict(response.headers), json.loads(response.read())


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.dsn = 'sqlite:'+str(Path(self.directory.name)/'acceptance.sqlite')
        self.db = Database(self.dsn); self.db.initialize()
        with self.db.transaction():
            for subject in (MEMBER_1, MEMBER_2):
                self.db.execute('INSERT INTO app.subject_binding VALUES (?,?)', (subject, subject))

    def tearDown(self):
        self.db.close(); self.directory.cleanup()

    def test_all_four_sources_and_scoped_http_report_on_reference_dataset(self):
        data = dataset()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        public.update(kid='acceptance', use='sig', alg='RS256')
        with source_server(data, public) as (base, calls, manifest):
            clients = {source: Client(base+'/'+source, allow_http=True, interval=0)
                       for source in ['tracker', 'qa', 'reference', 'planning']}
            for _ in range(2):
                load(self.db, 'tracker', lambda: tracker_extract(clients['tracker']))
                for source in ['qa', 'reference']:
                    load(self.db, source, lambda: catalog_extract(clients[source], source))
                load(self.db, 'planning', lambda: planning_extract(clients['planning'], uid(5001)))
            self.assertEqual(self.db.execute('SELECT COUNT(*),SUM(hours_cents) FROM dwh.fact_time_log').fetchone(), (300, 56250))
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM dwh.source_record WHERE source='qa' AND entity='defects'").fetchone()[0], 15)
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM dwh.source_record WHERE source='qa' AND entity='test-runs'").fetchone()[0], 2)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM etl.checkpoint').fetchone()[0], 4)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM etl.snapshot_batch').fetchone()[0], 4)
            tombstone = self.db.execute("SELECT payload FROM dwh.source_record WHERE source='reference' AND entity='employees' AND entity_id='101'").fetchone()[0]
            self.assertTrue(json.loads(tombstone)['is_deleted'])
            forecast = self.db.execute("SELECT payload FROM dwh.source_record WHERE source='planning' AND entity='forecast'").fetchone()[0]
            self.assertEqual(json.loads(forecast)['data']['quality'], 'PARTIAL')
            self.assertIsNone(json.loads(forecast)['data']['remainingHours'])
            self.assertNotIn('rate', json.loads(forecast)['data'])
            self.assertTrue(any('time-logs?page=3' in path for _, path in calls))
            self.assertTrue(any('test-cases?page=2' in path for _, path in calls))
            self.assertTrue(any('pageToken=100' in path for _, path in calls))
            self.assertTrue(any('cursor=4' in path for _, path in calls))
            self.assertEqual({method for method, _ in calls}, {'GET', 'POST'})
            self.assertTrue(all(path == '/planning/api/v1/exports' for method, path in calls if method == 'POST'))
            # Validate the published Planning export envelope and typed rows.
            document = json.loads((ROOT/'planning-system/docs/contracts/openapi.json').read_text())
            for endpoint, payload in [('/api/v1/exports/{batchId}', manifest),
                ('/api/v1/exports/{batchId}/rows', {'batchId': manifest['batchId'], 'dataAsOf': manifest['dataAsOf'],
                                                 'items': data['planning'], 'nextCursor': None})]:
                schema = document['paths'][endpoint]['get']['responses']['200']['content']['application/json']['schema']
                Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
            # End the PostgreSQL read transaction before HTTP opens another connection.
            self.db.connection.commit()
            totals = {}
            with report_server(self.dsn, base, base+'/jwks') as api:
                for name, subject, role in [('member1', MEMBER_1, 'reports-member'),
                                            ('member2', MEMBER_2, 'reports-member'), ('admin', uid(9000), 'reports-analyst')]:
                    token = jwt.encode({'sub': subject, 'iss': base, 'aud': 'reports', 'iat': int(time.time()),
                                        'exp': int(time.time())+120, 'resource_access': {'reports': {'roles': [role]}}},
                                       key, algorithm='RS256', headers={'kid': 'acceptance'})
                    status, _, body = request(api+'/pilot/reports/time-logs?startDate=2026-10-01&endDate=2026-10-01', token)
                    self.assertEqual(status, 200)
                    totals[name] = sum(row['hours'] for row in body['data'])
                    self.assertEqual(totals[name], EXPECTED['total_hours' if name == 'admin' else name+'_hours'])
                    self.assertEqual(len(body['data']), 3)
                    if name == 'member1': self.assertTrue(all(row['hours'] == 62.5 for row in body['data']))
                    status, _, empty = request(api+'/pilot/reports/time-logs?startDate=2026-09-01&endDate=2026-09-30', token)
                    self.assertEqual(status, 200); self.assertEqual(empty['data'], [])
                self.assertTrue(any(path == '/jwks' for _, path in calls))
            if os.getenv('REPORTS_RECORD_ARTIFACTS') == '1' and not self.db.sqlite:
                paths = ['reports/pilots/acceptance_data.py', 'reports/pilots/tests/test_acceptance.py',
                         'reports/pilots/api.py', 'reports/pilots/etl.py', 'reports/pilots/adapters.py', 'reports/pilots/db.py']
                artifact = {'passed': True, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                            'backend': 'PostgreSQL', 'seed': SEED, 'dataset': EXPECTED,
                            'http_sources': ['tracker', 'qa', 'reference', 'planning'], 'replays': 2,
                            'http_report_totals': totals, 'real_sources_verified': False,
                            'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}}
                (ROOT/'reports/pilots/artifacts/acceptance-verification.json').write_text(json.dumps(artifact, indent=2)+'\n')

    def test_bad_pages_of_each_catalog_preserve_checkpoint_and_previous_records(self):
        data = dataset()
        with source_server(data) as (base, _, manifest):
            for source in ['qa', 'reference', 'planning']:
                client = Client(base+'/'+source, allow_http=True, interval=0)
                extract = (lambda: planning_extract(client, uid(5001))) if source == 'planning' else (lambda: catalog_extract(client, source))
                load(self.db, source, extract)
                checkpoint = self.db.execute('SELECT value FROM etl.checkpoint WHERE source=?', (source,)).fetchone()[0]
                before = self.db.execute('SELECT entity,entity_id,payload FROM dwh.source_record WHERE source=? ORDER BY entity,entity_id', (source,)).fetchall()
                if source == 'qa': data['qa']['test-cases'][-1]['id'] = data['qa']['test-cases'][0]['id']
                elif source == 'reference': data['reference']['employees'][-1]['id'] = 1
                else: manifest['status'] = 'EXPIRED'
                with self.assertRaises(Rejected): load(self.db, source, extract)
                self.assertEqual(self.db.execute('SELECT value FROM etl.checkpoint WHERE source=?', (source,)).fetchone()[0], checkpoint)
                self.assertEqual(self.db.execute('SELECT entity,entity_id,payload FROM dwh.source_record WHERE source=? ORDER BY entity,entity_id', (source,)).fetchall(), before)


@unittest.skipUnless(os.getenv('REPORTS_TEST_DATABASE_URL'), 'Native PostgreSQL runner required')
class PostgreSQLAcceptance(Acceptance):
    def setUp(self):
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import conninfo_to_dict, make_conninfo
        self.admin = psycopg.connect(os.environ['REPORTS_TEST_DATABASE_URL'], autocommit=True)
        self.name = 'reports_acceptance_'+secrets.token_hex(6)
        self.admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.name)))
        self.dsn = make_conninfo(**dict(conninfo_to_dict(os.environ['REPORTS_TEST_DATABASE_URL']), dbname=self.name))
        self.db = Database(self.dsn); self.db.initialize()
        with self.db.transaction():
            for subject in (MEMBER_1, MEMBER_2):
                self.db.execute('INSERT INTO app.subject_binding VALUES (?,?)', (subject, subject))

    def tearDown(self):
        from psycopg import sql
        self.db.close()
        self.admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(self.name)))
        self.admin.close()


class FixtureContract(unittest.TestCase):
    def test_fixed_seed_and_tracker_schemas(self):
        data = dataset()
        self.assertEqual(data, dataset())
        self.assertEqual(len(data['tracker']['work-items']), 40)
        self.assertEqual(len(data['tracker']['time-logs']), 300)
        for entity, schema in [('work-items', 'ReportWorkItem'), ('time-logs', 'TimeLog'),
                               ('iterations', 'ReportIteration'), ('statuses', 'Status'), ('history', 'History')]:
            for item in data['tracker'][entity]: validate_tracker(schema, item)

    def test_malformed_roles_cannot_be_interpreted_as_admin(self):
        for access in [None, [], {'reports': None}, {'reports': {'roles': 'reports-admin'}},
                       {'reports': {'roles': ['reports-admin', {}]}}]:
            with self.subTest(access=access), self.assertRaises(PermissionError):
                authorize({'sub': MEMBER_1, 'resource_access': access})
