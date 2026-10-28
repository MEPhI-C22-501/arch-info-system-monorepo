"""Security at the real HTTP boundary, including browser-origin requests."""
import io
import json
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance_data import dataset, source_server
from adapters import Client
from db import Database
from demo import MEMBER_1
from etl import load, tracker_extract
from test_acceptance import report_server, request


class HttpBoundary(unittest.TestCase):
    def test_cookie_cross_origin_queries_writes_and_error_logs(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        public.update(kid='acceptance', use='sig', alg='RS256')
        diagnostics = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, source_server(dataset(), public) as (base, _, _):
            dsn = 'sqlite:'+str(Path(directory)/'http.sqlite')
            db = Database(dsn); db.initialize()
            with db.transaction(): db.execute('INSERT INTO app.subject_binding VALUES (?,?)', (MEMBER_1, MEMBER_1))
            load(db, 'tracker', lambda: tracker_extract(Client(base+'/tracker', allow_http=True, interval=0)))
            # Defense at the response boundary even if untrusted text has
            # reached storage. JSON transport is not a browser-rendering test.
            payload = '<svg onload=alert(1)>'
            with db.transaction(): db.execute('UPDATE dwh.fact_time_log SET project_id=?', (payload,))
            db.close()
            def token(access):
                return jwt.encode({'sub': MEMBER_1, 'iss': base, 'aud': 'reports', 'iat': int(time.time()),
                                   'exp': int(time.time())+120, 'resource_access': access}, key,
                                  algorithm='RS256', headers={'kid': 'acceptance'})
            valid = token({'reports': {'roles': ['reports-member']}})
            with redirect_stderr(diagnostics), report_server(dsn, base, base+'/jwks') as api:
                url = api+'/pilot/reports/time-logs'
                status, headers, body = request(url, valid, headers={'Origin': 'https://foreign.invalid'})
                self.assertEqual(status, 200)
                self.assertEqual(body['data'][0]['dimension'], payload)
                self.assertEqual(headers['Content-Type'], 'application/json')
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertFalse(any(key.lower().startswith('access-control-allow') for key in headers))
                self.assertEqual(request(url, headers={'Cookie': 'session=synthetic-cookie'})[0], 401)
                for method in ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']:
                    status, headers, _ = request(url, valid, method, {'Origin': 'https://foreign.invalid'})
                    self.assertEqual(status, 405)
                    self.assertEqual(headers['Allow'], 'GET')
                    self.assertNotIn('Access-Control-Allow-Origin', headers)
                for query in ['group=employee%3BDROP%20TABLE', 'group=project&group=employee',
                              'userId=someone-else', 'limit=0', 'offset=-1', 'startDate=invalid&endDate=invalid']:
                    status, _, body = request(url+'?'+query, valid)
                    self.assertEqual(status, 422)
                    self.assertEqual(body, {'error': 'invalid query'})
                for roles in ['reports-admin', ['reports-admin', {}], None]:
                    self.assertEqual(request(url, token({'reports': {'roles': roles}}))[0], 403)
                self.assertEqual(request(url, 'malformed')[0], 401)
            self.assertFalse(valid in diagnostics.getvalue(), 'Access token leaked to diagnostics')
            self.assertNotIn(payload, diagnostics.getvalue())
