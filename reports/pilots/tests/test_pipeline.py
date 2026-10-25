import copy
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jwt
import yaml
from cryptography.hazmat.primitives.asymmetric import rsa
from jsonschema import Draft202012Validator, FormatChecker
from adapters import Client, Rejected, numbered, planning, reference
from api import Handler as ReportHandler, authorize, report
from contracts import validate_tracker
from contracts import tracker_validator
from db import Database
from demo import Handler as MockHandler, MEMBER_1, MEMBER_2, fixture
from etl import load, now, planning_extract, tracker_extract, transform_time_logs
from redact import sanitize

ROOT = Path(__file__).resolve().parents[3]


class Tracker:
    def __init__(self, data=None, mutate=None):
        self.data, self.mutate = data or fixture(), mutate

    def request(self, path, params=None, body=None):
        rows = self.data[path.rsplit('/', 1)[1]]
        if path.endswith('/statuses'):
            return copy.deepcopy(rows)
        page, size = params['page'], params['pageSize']
        result = {'items': copy.deepcopy(rows[(page-1)*size:page*size]), 'page': page,
                  'pageSize': size, 'total': len(rows), 'totalPages': (len(rows)+size-1)//size}
        if self.mutate:
            self.mutate(result)
        return result


class Batch:
    def __init__(self):
        self.rows = [{'entityType': 'forecast', 'entityId': 'forecast-1',
                      'data': {'quality': 'PARTIAL', 'missingInputs': ['RATE']}}]
        self.manifest = {'batchId': 'batch-1', 'dataAsOf': now(), 'schemaVersion': '1.0.0', 'status': 'READY',
                         'expiresAt': (datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(),
                         'counts': [{'entityType': k, 'count': int(k == 'forecast')}
                                    for k in ['plan', 'demand', 'availability', 'allocation', 'forecast']]}

    def request(self, path, params=None, body=None, idempotency_key=None):
        if path.endswith('/rows'):
            return {'batchId': self.manifest['batchId'], 'dataAsOf': self.manifest['dataAsOf'],
                    'items': self.rows, 'nextCursor': None}
        return copy.deepcopy(self.manifest)


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.db = Database('sqlite::memory:')
        self.db.initialize()
        with self.db.transaction():
            for subject in [MEMBER_1, MEMBER_2]:
                self.db.execute('INSERT INTO app.subject_binding VALUES (?,?)', (subject, subject))

    def tearDown(self):
        self.db.close()

    def count(self, table):
        return self.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    def test_actual_tracker_contracts_validate_fixture_and_page(self):
        document = yaml.safe_load((ROOT/'task-tracker/docs/block-g-api-and-events/openapi.yaml').read_text())
        for resource, name in [('time-logs', 'TimeLogPage'), ('work-items', 'ReportWorkItemPage')]:
            schema = {'$ref': '#/components/schemas/'+name, 'components': document['components']}
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(
                Tracker().request('/'+resource, {'page': 1, 'pageSize': 100}))

    def test_tracker_missing_required_field_rejected(self):
        data = fixture()
        del data['work-items'][0]['priorityId']
        with self.assertRaisesRegex(Rejected, 'CONTRACT'):
            load(self.db, 'tracker', lambda: tracker_extract(Tracker(data)))
        self.assertEqual(self.count('dwh.fact_time_log'), 0)

    def test_container_contract_override_does_not_resolve_repository_parents(self):
        contract = ROOT/'task-tracker/docs/block-g-api-and-events/openapi.yaml'
        tracker_validator.cache_clear()
        try:
            with patch('contracts.__file__', '/app/contracts.py'), patch.dict(os.environ, {'REPORTS_TRACKER_CONTRACT': str(contract)}):
                validate_tracker('TimeLog', fixture()['time-logs'][0])
        finally: tracker_validator.cache_clear()

    def test_http_source_to_storage_idempotent_and_exact_sum(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), MockHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client(f'http://127.0.0.1:{server.server_port}', allow_http=True, interval=0)
            for _ in range(2):
                result = load(self.db, 'tracker', lambda: tracker_extract(client))
                self.assertEqual(result['status'], 'LOADED')
            self.assertEqual(self.count('dwh.fact_time_log'), 6)
            self.assertEqual(self.db.execute('SELECT SUM(hours_cents) FROM dwh.fact_time_log').fetchone()[0], 1125)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_rejected_batch_keeps_previous_checkpoint_and_facts(self):
        load(self.db, 'tracker', lambda: tracker_extract(Tracker()))
        before = self.db.execute('SELECT value FROM etl.checkpoint').fetchone()[0]
        def corrupt(page):
            page['total'] += 1
        with self.assertRaises(Rejected):
            load(self.db, 'tracker', lambda: tracker_extract(Tracker(mutate=corrupt)))
        self.assertEqual(self.db.execute('SELECT value FROM etl.checkpoint').fetchone()[0], before)
        self.assertEqual(self.count('dwh.fact_time_log'), 6)
        self.assertEqual(self.count('stg.record'), 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM etl.batch WHERE status='REJECTED'").fetchone()[0], 1)

    def test_failed_merge_rolls_back_already_inserted_rows(self):
        entities, checkpoint, stamp, facts = tracker_extract(Tracker())
        facts.append(('bad', MEMBER_1, 'project', None, '2026-10-01', -1))
        with self.assertRaises(Rejected):
            load(self.db, 'tracker', lambda: (entities, checkpoint, stamp, facts))
        for table in ['dwh.fact_time_log', 'dwh.source_record', 'etl.checkpoint', 'stg.record',
                      'dwh.dimension_version', 'dwh.source_snapshot', 'etl.snapshot_batch', 'etl.source_state']:
            self.assertEqual(self.count(table), 0, table)

    def test_missing_total_is_rejected(self):
        with self.assertRaises(Rejected):
            numbered(Tracker(mutate=lambda p: p.pop('total')), 'time-logs')

    def test_missing_middle_page_rejected(self):
        def corrupt(p):
            if p['page'] == 2:
                p['items'] = []
        with self.assertRaisesRegex(Rejected, 'INCOMPLETE|EMPTY'):
            numbered(Tracker(mutate=corrupt), 'time-logs', page_size=2)

    def test_repeated_record_across_pages_rejected(self):
        data = fixture(); data['time-logs'][2]['id'] = data['time-logs'][0]['id']
        with self.assertRaisesRegex(Rejected, 'DUPLICATE'):
            numbered(Tracker(data), 'time-logs', page_size=2)

    def test_changing_total_rejected(self):
        def corrupt(p):
            if p['page'] == 2:
                p['total'] += 1
        with self.assertRaisesRegex(Rejected, 'UNSTABLE'):
            numbered(Tracker(mutate=corrupt), 'time-logs', page_size=2)

    def test_oversized_and_wrong_page_rejected(self):
        for mutate in [lambda p: p.update(page=0), lambda p: p.update(page=True), lambda p: p.update(pageSize=True),
                       lambda p: p.update(totalPages=-1), lambda p: p.update(total=True)]:
            with self.subTest(mutate=mutate), self.assertRaises(Rejected):
                numbered(Tracker(mutate=mutate), 'time-logs')

    def test_unknown_project_and_missing_parent_preserve_hours(self):
        logs = fixture()['time-logs']
        logs[0].pop('workItemId')
        rows = transform_time_logs(logs, [])
        self.assertEqual(sum(r[-1] for r in rows), 1125)
        self.assertTrue(all(r[2] == 'UNASSIGNED' for r in rows))

    def test_invalid_hours_rejected(self):
        for hours in [-1, True, 'NaN', 'Infinity', 0.001]:
            data = fixture(); data['time-logs'][0]['hours'] = hours
            with self.subTest(hours=hours), self.assertRaises(Rejected):
                transform_time_logs(data['time-logs'], data['work-items'])

    def test_hour_corrections_replace_instead_of_add(self):
        load(self.db, 'tracker', lambda: tracker_extract(Tracker()))
        data = fixture(); data['time-logs'][0]['hours'] = 1.5
        load(self.db, 'tracker', lambda: tracker_extract(Tracker(data)))
        self.assertEqual(self.count('dwh.fact_time_log'), 6)
        self.assertEqual(self.db.execute('SELECT SUM(hours_cents) FROM dwh.fact_time_log').fetchone()[0], 1150)

    def test_planning_replay_preserves_partial_and_missing_money(self):
        client = Batch()
        for _ in range(2):
            load(self.db, 'planning', lambda: planning_extract(client, 'portfolio'))
        self.assertEqual(self.count('dwh.source_record'), 1)
        raw = json.loads(self.db.execute('SELECT payload FROM dwh.source_record').fetchone()[0])
        self.assertEqual(raw['data']['quality'], 'PARTIAL')
        self.assertNotIn('rate', raw['data'])
        self.assertEqual(self.db.execute("SELECT value FROM etl.checkpoint WHERE source='planning'").fetchone()[0], 'batch-1')
        portfolio = json.loads(self.db.execute(
            "SELECT value FROM etl.checkpoint WHERE source='planning:portfolio'").fetchone()[0])
        self.assertEqual(portfolio['batchId'], 'batch-1')

    def test_expired_unsupported_and_bad_count_batches_rejected(self):
        for field, value in [('expiresAt', '2000-01-01T00:00:00Z'), ('schemaVersion', '2.0.0'), ('status', 'EXPIRED')]:
            client = Batch(); client.manifest[field] = value
            with self.subTest(field=field), self.assertRaises(Rejected):
                planning(client, 'portfolio')
        client = Batch(); client.rows = []
        with self.assertRaisesRegex(Rejected, 'COUNT'):
            planning(client, 'portfolio')

    def test_planning_duplicate_and_foreign_batch_rejected(self):
        client = Batch(); client.rows *= 2
        with self.assertRaisesRegex(Rejected, 'DUPLICATE'):
            planning(client, 'portfolio')
        class Foreign(Batch):
            def request(self, path, params=None, body=None, idempotency_key=None):
                result = super().request(path, params, body)
                if path.endswith('/rows'): result['batchId'] = 'foreign'
                return result
        with self.assertRaisesRegex(Rejected, 'BATCH_MISMATCH'):
            planning(Foreign(), 'portfolio')

    def test_planning_permission_or_expiry_change_before_merge_rejected(self):
        class Expires(Batch):
            reads = 0
            def request(self, path, params=None, body=None, idempotency_key=None):
                result = super().request(path, params, body)
                if path.endswith('/batch-1'):
                    self.reads += 1
                    if self.reads > 1: result['status'] = 'EXPIRED'
                return result
        with self.assertRaisesRegex(Rejected, 'BATCH_NOT_READY'):
            load(self.db, 'planning', lambda: planning_extract(Expires(), 'portfolio'))
        self.assertEqual(self.count('dwh.source_record'), 0)
        self.assertEqual(self.count('etl.checkpoint'), 0)

    def test_http_redirect_does_not_forward_bearer(self):
        reached = []
        class Target(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                reached.append(True)
                self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        target = ThreadingHTTPServer(('127.0.0.1', 0), Target)
        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', f'http://127.0.0.1:{target.server_port}/receive')
                self.end_headers()
        redirect = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        for server in [target, redirect]: threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            client = Client(f'http://127.0.0.1:{redirect.server_port}', secrets.token_urlsafe(24), allow_http=True)
            with self.assertRaisesRegex(Rejected, 'SOURCE_HTTP_302'): client.request('/resource')
            self.assertEqual(reached, [])
        finally:
            for server in [redirect, target]: server.shutdown(); server.server_close()

    def test_reference_real_parameter_names_and_tombstone(self):
        calls = []
        class HR:
            def request(self, path, params):
                calls.append((path, params))
                return {'employees': [{'id': 1, 'is_deleted': True}], 'nextPageToken': None}
        self.assertEqual(reference(HR(), 'employees')[0]['is_deleted'], True)
        self.assertEqual(calls, [('/v1/employees/', {'pageSize': 100, 'allowDeleted': 'true'})])

    def test_repeated_reference_cursor_rejected(self):
        class HR:
            def request(self, *_):
                return {'employees': [{'id': 1}], 'nextPageToken': 'same'}
        with self.assertRaisesRegex(Rejected, 'REPEATED'):
            reference(HR(), 'employees')

    def test_qa_pages_use_total_pages_without_total(self):
        def no_total(p): p.pop('total')
        self.assertEqual(len(numbered(Tracker(mutate=no_total), 'time-logs', tracker=False, page_size=2)), 6)

    def test_member_scope_admin_scope_and_sql_injection(self):
        load(self.db, 'tracker', lambda: tracker_extract(Tracker()))
        member = {'sub': MEMBER_1, 'resource_access': {'reports': {'roles': ['reports-member']}}}
        admin = {'sub': 'admin', 'resource_access': {'reports': {'roles': ['reports-admin']}}}
        self.assertEqual(report(self.db, member)['data'][0]['hours'], 3.75)
        self.assertEqual(report(self.db, admin)['data'][0]['hours'], 11.25)
        with self.assertRaises(ValueError): report(self.db, member, 'employee;DROP TABLE')
        with self.assertRaises(PermissionError): report(self.db, {'sub': MEMBER_1})
        malicious = copy.deepcopy(member); malicious['sub'] = "' OR 1=1 --"
        with self.assertRaises(PermissionError): report(self.db, malicious)

    def test_missing_identity_binding_denies_access_even_if_ids_coincide(self):
        load(self.db, 'tracker', lambda: tracker_extract(Tracker()))
        with self.db.transaction():
            self.db.execute('DELETE FROM app.subject_binding WHERE subject=?', (MEMBER_1,))
        claims = {'sub': MEMBER_1, 'resource_access': {'reports': {'roles': ['reports-member']}}}
        with self.assertRaises(PermissionError): report(self.db, claims)

    def test_explicit_tracker_to_subject_mapping_is_used(self):
        data = fixture()
        for row in data['time-logs']:
            if row['userId'] == MEMBER_1: row['userId'] = 'tracker-person-a'
        with self.db.transaction():
            self.db.execute('UPDATE app.subject_binding SET tracker_user_id=? WHERE subject=?', ('tracker-person-a', MEMBER_1))
        load(self.db, 'tracker', lambda: tracker_extract(Tracker(data)))
        claims = {'sub': MEMBER_1, 'resource_access': {'reports': {'roles': ['reports-member']}}}
        self.assertEqual(report(self.db, claims)['data'][0]['hours'], 3.75)

    def test_empty_storage_is_stale(self):
        admin = {'sub': 'admin', 'resource_access': {'reports': {'roles': ['reports-admin']}}}
        self.assertEqual(report(self.db, admin)['freshness'], 'STALE')

    def test_secret_url_and_accidental_http_are_rejected(self):
        for url in ['https://user:password@example.org', 'https://example.org?token=secret', 'http://example.org']:
            with self.assertRaises(ValueError): Client(url)

    def test_diagnostics_redact_raw_and_encoded_secrets(self):
        from urllib.parse import quote
        value = secrets.token_urlsafe(24)+'/+"'
        for encoded in [value, quote(value, safe=''), json.dumps(value)[1:-1]]:
            self.assertEqual(sanitize('diagnostic '+encoded, [value]), 'diagnostic [redacted]')

    def test_diagnostics_redact_temporary_jwt_without_saving_it(self):
        token = jwt.encode({'sub': 'synthetic'}, secrets.token_urlsafe(32), algorithm='HS256')
        self.assertNotIn(token, sanitize('Authorization: Bearer '+token, []))


class HttpSecurity(unittest.TestCase):
    def test_bi_secure_cookie_exception_is_confined_to_local_pilot_ports(self):
        from check_bi import LocalPilotCookiePolicy
        cookie = type('SecureCookie', (), {'secure': True})()
        policy = LocalPilotCookiePolicy()
        for url in ['https://example.org', 'http://localhost:8180', 'http://localhost:8088']:
            self.assertTrue(policy.return_ok_secure(cookie, urllib.request.Request(url)))
        for url in ['http://example.org:8180', 'http://localhost.example.org:8180', 'http://localhost:9000']:
            self.assertFalse(policy.return_ok_secure(cookie, urllib.request.Request(url)))

    def test_jwks_signature_audience_expiry_and_member_scope_over_http(self):
        # Ephemeral keys/tokens stay only in process memory and are never logged.
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update(kid='test', use='sig', alg='RS256')
        class Keys(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                data = json.dumps({'keys': [jwk]}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(data)
        keys = ThreadingHTTPServer(('127.0.0.1', 0), Keys)
        threading.Thread(target=keys.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as tmp:
            dsn = 'sqlite:'+str(Path(tmp)/'pilot.sqlite')
            db = Database(dsn); db.initialize()
            with db.transaction(): db.execute('INSERT INTO app.subject_binding VALUES (?,?)', (MEMBER_1, MEMBER_1))
            load(db, 'tracker', lambda: tracker_extract(Tracker())); db.close()
            issuer = f'http://127.0.0.1:{keys.server_port}'
            ReportHandler.jwks = jwt.PyJWKClient(issuer)
            api = ThreadingHTTPServer(('127.0.0.1', 0), ReportHandler)
            threading.Thread(target=api.serve_forever, daemon=True).start()
            try:
                with patch.dict(os.environ, {'REPORTS_DATABASE_URL': dsn, 'REPORTS_OIDC_ISSUER': issuer}):
                    stamp = int(datetime.now(timezone.utc).timestamp())
                    base = {'sub': MEMBER_1, 'iss': issuer, 'aud': 'reports', 'iat': stamp, 'exp': stamp+60,
                            'resource_access': {'reports': {'roles': ['reports-member']}}}
                    def call(claims, signing_key=key, kid='test'):
                        headers = {} if claims is None else {'Authorization': 'Bearer '+jwt.encode(claims, signing_key, algorithm='RS256', headers={'kid': kid})}
                        request = urllib.request.Request(f'http://127.0.0.1:{api.server_port}/pilot/reports/time-logs', headers=headers)
                        try:
                            with urllib.request.urlopen(request) as response: return response.status, json.load(response)
                        except urllib.error.HTTPError as error: return error.code, None
                    status, result = call(base)
                    self.assertEqual(status, 200); self.assertEqual(result['data'][0]['hours'], 3.75)
                    for claims in [None, dict(base, exp=stamp-10), dict(base, aud='other'), dict(base, iss='other')]:
                        self.assertEqual(call(claims)[0], 401)
                    bad_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                    self.assertEqual(call(base, bad_key)[0], 401)
                    self.assertEqual(call(base, kid='unknown')[0], 401)
                    self.assertEqual(call(dict(base, resource_access={}))[0], 403)
            finally:
                api.shutdown(); api.server_close()
        keys.shutdown(); keys.server_close()


@unittest.skipUnless(os.getenv('REPORTS_TEST_DATABASE_URL'), 'PostgreSQL test DSN not supplied')
class PostgreSQL(unittest.TestCase):
    def test_atomic_etl_on_postgres(self):
        # The supplied DB must be a disposable dedicated pilot-test database.
        db = Database(os.environ['REPORTS_TEST_DATABASE_URL']); db.initialize()
        try:
            for _ in range(2): load(db, 'tracker', lambda: tracker_extract(Tracker()))
            self.assertEqual(db.execute('SELECT SUM(hours_cents) FROM dwh.fact_time_log').fetchone()[0], 1125)
            before = db.execute('SELECT value FROM etl.checkpoint').fetchone()[0]
            entities, checkpoint, stamp, facts = tracker_extract(Tracker())
            facts.append(('invalid', MEMBER_1, 'project', None, '2026-10-01', -1))
            with self.assertRaises(Rejected):
                load(db, 'tracker', lambda: (entities, checkpoint, stamp, facts))
            self.assertEqual(db.execute('SELECT SUM(hours_cents) FROM dwh.fact_time_log').fetchone()[0], 1125)
            self.assertEqual(db.execute('SELECT value FROM etl.checkpoint').fetchone()[0], before)
        finally: db.close()

    def test_view_reader_has_no_direct_access_to_identity_bindings(self):
        import psycopg
        db = Database(os.environ['REPORTS_TEST_DATABASE_URL']); db.initialize()
        capability = db.execute('SELECT rolcreaterole,rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()
        db.connection.rollback()
        if not any(capability):
            db.close(); self.skipTest('Role creation requires an isolated privileged test database')
        load(db, 'tracker', lambda: tracker_extract(Tracker()))
        role = 'reports_pilot_reader_'+secrets.token_hex(4)
        try:
            with db.transaction():
                db.execute(f'CREATE ROLE {role} NOLOGIN')
                db.execute(f'GRANT USAGE ON SCHEMA dwh TO {role}')
                db.execute(f'GRANT SELECT ON dwh.report_time_log TO {role}')
            with db.transaction():
                db.execute(f'SET LOCAL ROLE {role}')
                self.assertEqual(db.execute('SELECT COUNT(*) FROM dwh.report_time_log').fetchone()[0], 6)
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with db.transaction():
                    db.execute(f'SET LOCAL ROLE {role}')
                    db.execute('SELECT * FROM app.subject_binding')
        finally:
            with db.transaction():
                db.execute(f'DROP OWNED BY {role}')
                db.execute(f'DROP ROLE {role}')
            db.close()


if __name__ == '__main__': unittest.main()
