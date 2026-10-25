"""Exercise the real Keycloak authorization-code flow and Superset data API.

Each account has an isolated cookie jar. No tokens, cookies, passwords or OAuth
callback URLs enter artifacts or stdout. This complements browser screenshots.
"""
import argparse
import concurrent.futures
import http.cookiejar
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from dotenv import dotenv_values


class CheckFailure(RuntimeError):
    pass


class LocalPilotCookiePolicy(http.cookiejar.DefaultCookiePolicy):
    def return_ok_secure(self, cookie, request):
        # Browsers treat http://localhost as a trustworthy local origin.
        # Keycloak sets Secure cookies there; urllib needs this explicit,
        # loopback-only exception to reproduce the real browser flow.
        url = urllib.parse.urlsplit(request.full_url)
        return (super().return_ok_secure(cookie, request) or
                (url.scheme == 'http' and url.hostname == 'localhost' and url.port in {8180, 8088}))


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
        self.active = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'form' and attrs.get('id') == 'kc-form-login':
            self.action, self.active = attrs.get('action'), True
        if self.active and tag == 'input' and attrs.get('type') == 'hidden' and attrs.get('name'):
            self.fields[attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form': self.active = False


class Session:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(
            http.cookiejar.CookieJar(policy=LocalPilotCookiePolicy())))
        self.csrf = None

    def request(self, path, payload=None, extra_headers=None):
        headers = {'Accept': 'application/json', 'Referer': self.base+'/'}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers['Content-Type'] = 'application/json'
            if self.csrf: headers['X-CSRFToken'] = self.csrf
        headers.update(extra_headers or {})
        req = urllib.request.Request(self.base+path, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=60) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as error:
            raw, status = error.read(), error.code
        try: return status, json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError): return status, {'non_json': True}

    def login(self, username, password, expect_denied=False):
        with self.opener.open(self.base+'/login/keycloak', timeout=30) as response:
            html = response.read().decode()
        form = LoginForm(); form.feed(html)
        if not form.action: raise CheckFailure('Keycloak login form was not returned')
        target = urllib.parse.urlsplit(form.action)
        if target.hostname not in {'localhost', '127.0.0.1'} or target.port != 8180:
            raise CheckFailure('Unexpected login form destination')
        fields = dict(form.fields, username=username, password=password)
        req = urllib.request.Request(form.action, data=urllib.parse.urlencode(fields).encode(),
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with self.opener.open(req, timeout=60) as response: response.read()
        status, user = self.request('/api/v1/me/')
        if expect_denied:
            if status not in {401, 403}: raise CheckFailure('Account without Reports role obtained a session')
            return None
        if status != 200 or not isinstance(user.get('result'), dict):
            raise CheckFailure('Superset did not establish an authenticated session')
        status, csrf = self.request('/api/v1/security/csrf_token/')
        if status != 200 or not csrf.get('result'): raise CheckFailure('CSRF token was not issued')
        self.csrf = csrf['result']
        return user['result']

    def chart(self, dataset_id, filters=None, force=True):
        return self.request('/api/v1/chart/data', {
            'datasource': {'id': dataset_id, 'type': 'table'}, 'force': force,
            'queries': [{'columns': ['project_id', 'user_id'], 'metrics': ['actual_hours'],
                         'filters': filters or [], 'row_limit': 1000, 'time_range': 'No filter',
                         'orderby': [['actual_hours', False]]}],
            'result_format': 'json', 'result_type': 'full',
        })


def rows(status, payload):
    if status != 200: raise CheckFailure('Chart data HTTP '+str(status))
    result = payload.get('result', [])
    if not result or result[0].get('error'): raise CheckFailure('Chart execution failed')
    return result[0]['data']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://localhost:8088')
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--benchmark', action='store_true', help='100 warm chart API requests with 20 isolated client sessions')
    args = parser.parse_args()
    target = Path(__file__).with_name('artifacts')/'bi-verification.json'
    if args.record:
        target.write_text(json.dumps({'passed': False, 'state': 'running'})+'\n')
    secrets_path = Path.home()/'secrets.env'
    values = dotenv_values(secrets_path)
    required = ['REPORTS_DEMO_ADMIN_PASSWORD', 'REPORTS_DEMO_MEMBER_PASSWORD']
    if not all(values.get(name) for name in required):
        raise CheckFailure('Missing Reports test credentials in ~/secrets.env')
    sessions, users, checks = {}, {}, []
    anonymous = Session(args.base_url)
    status, _ = anonymous.request('/api/v1/me/')
    if status not in {401, 403}: raise CheckFailure('Anonymous session accepted')
    checks.append({'account': 'anonymous', 'check': 'session_denied', 'passed': True})
    Session(args.base_url).login('noaccess', values['REPORTS_DEMO_MEMBER_PASSWORD'], expect_denied=True)
    checks.append({'account': 'noaccess', 'check': 'reports_role_required', 'passed': True})
    for name in ['admin', 'member1', 'member2']:
        session = Session(args.base_url)
        password = values['REPORTS_DEMO_ADMIN_PASSWORD' if name == 'admin' else 'REPORTS_DEMO_MEMBER_PASSWORD']
        users[name] = session.login(name, password)
        sessions[name] = session
        checks.append({'account': name, 'check': 'keycloak_login', 'passed': True})
    status, charts = sessions['admin'].request('/api/v1/chart/?q=(page_size:100)')
    if status != 200: raise CheckFailure('Chart catalog HTTP '+str(status))
    chart = next(c for c in charts['result'] if c['slice_name'] == 'R-01 Трудозатраты')
    status, details = sessions['admin'].request('/api/v1/chart/'+str(chart['id']))
    if status != 200: raise CheckFailure('Chart metadata unavailable')
    params = json.loads(details['result']['params'])
    dataset_id = int(params['datasource'].split('__')[0])
    database_id = details['result'].get('datasource', {}).get('database', {}).get('id', 1)
    expected = {'admin': Decimal('11.25'), 'member1': Decimal('3.75'), 'member2': Decimal('7.50')}
    for name, session in sessions.items():
        data = rows(*session.chart(dataset_id))
        total = sum((Decimal(str(row['actual_hours'])) for row in data), Decimal(0))
        if total != expected[name]: raise CheckFailure('Incorrect hours for '+name)
        if name != 'admin' and any(row['user_id'] != users[name]['username'] for row in data):
            raise CheckFailure('Foreign row visible to '+name)
        checks.append({'account': name, 'check': 'dashboard_data', 'hours': str(total), 'passed': True})
        if name != 'admin':
            other = 'member2' if name == 'member1' else 'member1'
            data = rows(*session.chart(dataset_id, [{'col': 'user_id', 'op': 'IN', 'val': [users[other]['username']]}]))
            if data: raise CheckFailure('RLS bypass via foreign employee filter')
            checks.append({'account': name, 'check': 'foreign_filter_denied', 'passed': True})
            status, _ = session.request('/api/v1/sqllab/execute/', {'database_id': database_id, 'sql': 'SELECT 1', 'runAsync': False})
            if status != 403: raise CheckFailure('SQL Lab must return 403 for '+name)
            checks.append({'account': name, 'check': 'sql_lab_denied', 'http_status': status, 'passed': True})
            csrf, session.csrf = session.csrf, None
            # Chart-data is an intentionally exempt, read-only Superset API.
            # A deliberately invalid field type prevents creation even if
            # the security protection unexpectedly stops working.
            invalid_dashboard = {'dashboard_title': []}
            status, denied = session.request('/api/v1/dashboard/', invalid_dashboard)
            session.csrf = csrf
            if status != 400 or 'csrf' not in json.dumps(denied).lower():
                raise CheckFailure('Missing CSRF token accepted for '+name)
            checks.append({'account': name, 'check': 'csrf_required', 'http_status': status, 'passed': True})
            status, denied = session.request('/api/v1/dashboard/', invalid_dashboard, {'Origin': 'https://foreign.invalid'})
            if status != 403 or denied.get('message') != 'Origin is not allowed':
                raise CheckFailure('Foreign-origin write with a valid CSRF token was accepted')
            checks.append({'account': name, 'check': 'foreign_origin_denied', 'http_status': status, 'passed': True})
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
              'authorization_code_flow': True, 'real_keycloak': True, 'real_superset': True, 'passed': True}
    root = Path(__file__).resolve().parents[2]
    source_names = ['compose.yaml', 'check_bi.py', 'provision.py', 'db.py', 'contracts.py', 'etl.py',
                    'cube/cube.js', 'cube/dataset.sql', 'cube/model/TimeLogs.js',
                    'worker.py', 'demo.py', 'api.py', 'superset/setup_bi.py', 'superset/superset_config.py',
                    'superset/session_policy.py', 'superset/check_session.py', 'superset/Dockerfile']
    source_names += ['superset/cube_driver/pyproject.toml', 'superset/cube_driver/reports_cube/dialect.py',
                     'superset/cube_driver/reports_cube/engine.py']
    result['source_sha256'] = {str((Path(__file__).parent/name).relative_to(root)):
        hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in source_names}
    if args.benchmark:
        clients = []
        for index in range(20):
            name = 'member1' if index % 2 == 0 else 'member2'
            client = Session(args.base_url)
            user = client.login(name, values['REPORTS_DEMO_MEMBER_PASSWORD'])
            clients.append((client, name, user['username']))
            # Warm the real chart cache before the warm-mode measurement.
            data = rows(*client.chart(dataset_id, force=False))
            if any(row['user_id'] != user['username'] for row in data):
                raise CheckFailure('Cache warm-up crossed an employee scope')
        def measure(item):
            client, name, subject = item
            delays, hits = [], 0
            for _ in range(5):
                started = time.perf_counter()
                status, payload = client.chart(dataset_id, force=False)
                data = rows(status, payload)
                hits += bool(payload['result'][0].get('is_cached'))
                delays.append(time.perf_counter()-started)
                if any(row['user_id'] != subject for row in data): raise CheckFailure('RLS failed under load')
                if sum((Decimal(str(row['actual_hours'])) for row in data), Decimal(0)) != expected[name]:
                    raise CheckFailure('Chart total differs under load')
            return delays, hits
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            samples = list(pool.map(measure, clients))
        delays = [delay for values_, _ in samples for delay in values_]
        cache_hits = sum(hits for _, hits in samples)
        p95 = sorted(delays)[94]
        benchmark = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'clients': 20, 'requests': 100,
                     'accounts': 2, 'source_time_logs': 6, 'cache': 'Cube and Superset metastore cache warm; TTL 60 seconds',
                     'cache_hits': cache_hits,
                     'scope': 'Chart data API including RLS; excludes browser rendering and the million-row Cube test',
                     'p95_seconds': round(p95, 4), 'threshold_seconds': 3, 'passed': p95 <= 3 and cache_hits >= 95,
                     'source_sha256': result['source_sha256']}
        if args.record:
            target.with_name('bi-benchmark.json').write_text(json.dumps(benchmark, indent=2)+'\n')
        if not benchmark['passed']: raise CheckFailure('Warm chart API p95 exceeds 3 seconds')
        result['benchmark'] = benchmark
    if args.record:
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as error:
        # Error text from HTTP redirects may contain a temporary code. Never
        # print arbitrary exception details or response bodies here.
        print(json.dumps({'passed': False, 'error_type': type(error).__name__, 'check': str(error) if isinstance(error, CheckFailure) else 'unexpected dependency response'}))
        sys.exit(1)
