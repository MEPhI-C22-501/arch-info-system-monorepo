"""Optional real Cube/PostgreSQL smoke and warm load test on synthetic data."""
import concurrent.futures
import argparse
import hashlib
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import fasteners
import jwt
import pgserver
from cryptography.hazmat.primitives.asymmetric import rsa
from db import Database


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    artifact = Path(__file__).with_name('artifacts')/'cube-benchmark.json'
    if args.record: artifact.write_text(json.dumps({'passed': False, 'state': 'running'})+'\n')
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='pilot-ephemeral', use='sig', alg='RS256')
    class Keys(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            raw = json.dumps({'keys': [jwk]}).encode()
            self.send_response(200); self.end_headers(); self.wfile.write(raw)
    keys = ThreadingHTTPServer(('127.0.0.1', 0), Keys)
    threading.Thread(target=keys.serve_forever, daemon=True).start()
    issuer = f'http://127.0.0.1:{keys.server_port}'
    node = os.getenv('NODE', 'node')
    with tempfile.TemporaryDirectory(prefix='rc-', dir='/tmp') as tmp:
        pgserver.PostgresServer.runtime_path = Path(tmp)/'run'
        pgserver.PostgresServer._lock = fasteners.InterProcessLock(Path(tmp)/'pg.lock')
        server = pgserver.get_server(Path(tmp)/'data', cleanup_mode='delete')
        cube, raw_cube = None, None
        try:
            uri = server.get_uri()
            database = Database(uri); database.initialize()
            with database.transaction():
                database.execute("""INSERT INTO dwh.fact_time_log(id,user_id,project_id,work_item_id,logged_date,hours_cents)
                    SELECT 'bench-'||n, 'tracker-user-'||lpad((n % 300)::text,3,'0'),
                    'project-'||(n % 50), NULL,
                    (date '2026-10-01'+(n % 28)::int)::text, 125
                    FROM generate_series(1,1000000) AS n""")
                database.execute("""INSERT INTO app.subject_binding
                    SELECT 'user-'||lpad(n::text,3,'0'), 'tracker-user-'||lpad(n::text,3,'0')
                    FROM generate_series(0,299) AS n""")
            pg_version = database.execute('SHOW server_version').fetchone()[0]
            database.close()
            parsed = urllib.parse.urlsplit(uri)
            host = urllib.parse.parse_qs(parsed.query).get('host', [parsed.hostname])[0]
            api_port, sql_port = free_port(), free_port()
            sql_password = secrets.token_urlsafe(32)  # Ephemeral test-only credential, never persisted.
            env = os.environ.copy()
            env.update({'CUBEJS_DB_TYPE': 'postgres', 'CUBEJS_DB_HOST': host, 'CUBEJS_DB_NAME': 'postgres',
                        'CUBEJS_DB_USER': 'postgres', 'CUBEJS_DEV_MODE': 'false',
                        'CUBEJS_CACHE_AND_QUEUE_DRIVER': 'memory', 'CUBEJS_TELEMETRY': 'false',
                        'CUBESQL_SQL_PUSH_DOWN': 'false',
                        'CUBEJS_PRE_AGGREGATIONS_SCHEMA': 'reports_preaggregations',
                        'CUBEJS_PRE_AGGREGATIONS_BUILDER': 'true', 'CUBEJS_LOG_LEVEL': 'error',
                        'CUBEJS_ROLLUP_ONLY': 'true',
                        'REPORTS_OIDC_ISSUER': issuer, 'REPORTS_OIDC_JWKS_URL': issuer,
                        'REPORTS_CUBE_SQL_PASSWORD': sql_password,
                        'REPORTS_CUBE_CONFIG': str(Path(__file__).with_name('cube')/'cube.js'),
                        'PORT': str(api_port), 'CUBEJS_PG_SQL_PORT': str(sql_port)})
            bootstrap = """const path=require('path');
const Server=require('@cubejs-backend/server');
const config=require(process.env.REPORTS_CUBE_CONFIG);
config.schemaPath='model';
config.logger=()=>{};
new Server(config).listen().catch(()=>process.exit(1));"""
            # Output remains in memory; only a sanitized diagnostic is emitted.
            cube = subprocess.Popen([node, '-e', bootstrap], cwd=Path(__file__).with_name('cube'),
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = bytearray()
            def drain():
                for chunk in iter(lambda: cube.stdout.read(4096), b''):
                    if len(log) < 64000: log.extend(chunk)
            threading.Thread(target=drain, daemon=True).start()
            def token(member=None):
                stamp = int(time.time())
                return jwt.encode({'iss': issuer, 'aud': 'reports', 'sub': member or 'test-admin', 'iat': stamp, 'exp': stamp+600,
                                   'resource_access': {'reports': {'roles': ['reports-member' if member else 'reports-analyst']}}},
                                  key, algorithm='RS256', headers={'kid': 'pilot-ephemeral'})
            admin_token = token()
            def request(route, access_token, query=None):
                url = f'http://127.0.0.1:{api_port}/cubejs-api/v1/'+route
                if query: url += '?'+urllib.parse.urlencode({'query': json.dumps(query)})
                req = urllib.request.Request(url, headers={'Authorization': access_token})
                try:
                    with urllib.request.urlopen(req, timeout=60) as response: return json.load(response)
                except urllib.error.HTTPError as error:
                    body = json.load(error)
                    message = str(body.get('error', 'request failed')).replace(sql_password, '[redacted]')
                    import re
                    message = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[redacted]', message)
                    raise RuntimeError('Cube HTTP '+str(error.code)+': '+message) from None
            for _ in range(90):
                if cube.poll() is not None:
                    text = log.decode(errors='replace').replace(sql_password, '[redacted]')
                    # Log should have no token; redact JWT-shaped strings as well.
                    import re
                    text = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[redacted]', text)
                    raise RuntimeError('Cube startup failed: '+text[-2500:])
                try:
                    request('meta', admin_token)
                    break
                except (urllib.error.URLError, TimeoutError): time.sleep(1)
            else: raise RuntimeError('Cube readiness timed out')
            query = {'measures': ['TimeLogs.hours'], 'dimensions': ['TimeLogs.projectId', 'TimeLogs.userId'],
                     'timeDimensions': [{'dimension': 'TimeLogs.loggedDate', 'granularity': 'month',
                                         'dateRange': ['2026-10-01', '2026-10-31']}]}
            def load(access_token):
                for _ in range(90):
                    result = request('load', access_token, query)
                    if result.get('error') == 'Continue wait': time.sleep(1); continue
                    if result.get('error'): raise RuntimeError('Cube query failed: '+str(result['error']))
                    return result
                raise RuntimeError('Cube query timed out')
            cold_start = time.perf_counter()
            warm = load(admin_token)
            cold_seconds = time.perf_counter()-cold_start
            assert sum(float(r['TimeLogs.hours']) for r in warm['data']) == 1250000.0
            # Production responses hide usedPreAggregations. Rollup-only mode
            # rejects queries without a matching rollup inside the orchestrator.
            import psycopg
            with psycopg.connect(uri) as connection:
                used = [r[0] for r in connection.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='reports_preaggregations'")]
            if not used: raise RuntimeError('No physical pre-aggregation was built')
            # Exercise the same SQL dataset as Superset through the real PG API.
            dataset_sql = (Path(__file__).with_name('cube')/'dataset.sql').read_text()
            with psycopg.connect(host='127.0.0.1', port=sql_port, dbname='db', user='reports_bi',
                                 password=sql_password, sslmode='disable', connect_timeout=10) as connection:
                total = connection.execute('SELECT SUM(hours) FROM ('+dataset_sql+') dataset').fetchone()[0]
                if float(total) != 1250000.0: raise RuntimeError('BI SQL dataset total differs')
                sorted_rows = connection.execute('SELECT project_id, user_id, SUM(hours) AS actual_hours FROM ('+
                    dataset_sql+') virtual_table GROUP BY project_id, user_id ORDER BY actual_hours DESC LIMIT 1000').fetchall()
                if sum(float(row[2]) for row in sorted_rows) != 1250000.0:
                    raise RuntimeError('Sorted Superset SQL result differs')
                try:
                    connection.execute('SELECT SUM("plannedHours") FROM "WorkItems"').fetchall()
                except psycopg.Error as error:
                    if 'scope' not in str(error).lower():raise RuntimeError('SQL model denial was not an authorization check') from None
                else:raise RuntimeError('Shared BI SQL identity read a protected model')
            member = load(token('user-000'))
            assert all(r['TimeLogs.userId'] == 'user-000' for r in member['data'])
            assert sum(float(r['TimeLogs.hours']) for r in member['data']) == 4166.25
            access_tokens = [token(f'user-{i:03d}') for i in range(20)]
            # Warm individual scopes before measuring concurrent requests.
            for value in access_tokens: load(value)
            def timed(value):
                start = time.perf_counter(); load(value); return time.perf_counter()-start
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
                delays = list(pool.map(timed, access_tokens * 5))
            p95 = sorted(delays)[int(len(delays)*.95)-1]
            # Record-level drill-down deliberately uses the normal configuration,
            # where raw queries are allowed; the load test above required a rollup.
            api_port = free_port()
            raw_env = dict(env, PORT=str(api_port), CUBEJS_PG_SQL_PORT=str(free_port()), CUBEJS_ROLLUP_ONLY='false')
            raw_cube = subprocess.Popen([node, '-e', bootstrap], cwd=Path(__file__).with_name('cube'),
                                        env=raw_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(90):
                if raw_cube.poll() is not None: raise RuntimeError('Drill-down server failed')
                try:
                    request('meta', admin_token); break
                except (urllib.error.URLError, TimeoutError): time.sleep(1)
            else: raise RuntimeError('Drill-down readiness timed out')
            detail_query = {'measures': ['TimeLogs.hours'], 'dimensions': ['TimeLogs.id', 'TimeLogs.userId', 'TimeLogs.projectId'],
                            'ungrouped': True, 'limit': 5}
            detail = request('load', token('user-000'), detail_query)
            if detail.get('error'): raise RuntimeError('Drill-down query did not finish')
            assert len(detail['data']) == 5
            assert all(r['TimeLogs.userId'] == 'user-000' and float(r['TimeLogs.hours']) == 1.25 for r in detail['data'])
            assert len({r['TimeLogs.id'] for r in detail['data']}) == 5
            output = {'cube': '1.6.75', 'postgres': pg_version, 'rows': 1000000, 'users': 20,
                      'requests': len(delays), 'cache': 'warm', 'p95_seconds': round(p95, 4),
                      'cold_first_cube_query_seconds': round(cold_seconds, 4),
                      'pre_aggregations': used, 'rollup_only': True, 'queue_cache_driver': 'memory',
                      'member_scope': 'passed', 'expected_hours': 1250000.0,
                      'superset_sql_dataset': 'passed',
                      'superset_sorted_sql': 'passed', 'sql_push_down': False,
                      'sql_protected_models_denied':True,
                      'drill_down': 'passed', 'machine': platform.machine(), 'cpu_count': os.cpu_count(),
                      'node': subprocess.check_output([node, '--version'], text=True).strip(),
                      'threshold_seconds': 3, 'passed': p95 <= 3,
                      'container_stack_verified': False, 'measured_at': datetime.now(timezone.utc).isoformat()}
            root = Path(__file__).resolve().parents[2]
            source_names = ['reports/pilots/check_cube.py', 'reports/pilots/db.py', 'reports/pilots/cube/cube.js',
                            'reports/pilots/cube/dataset.sql', 'reports/pilots/cube/model/TimeLogs.js']
            source_names += ['reports/pilots/star.py','reports/pilots/cube/access.js']
            source_names += [str(p.relative_to(root)) for p in Path(__file__).with_name('cube').rglob('*.js') if p.is_file() and 'node_modules' not in p.parts and str(p.relative_to(root)) not in source_names]
            output['source_sha256'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in source_names}
            if args.record: artifact.write_text(json.dumps(output, indent=2)+'\n')
            print(json.dumps(output))
            if p95 > 3: return 1
        finally:
            if raw_cube:
                raw_cube.terminate()
                try: raw_cube.wait(timeout=15)
                except subprocess.TimeoutExpired: raw_cube.kill(); raw_cube.wait()
            if cube:
                cube.terminate()
                try: cube.wait(timeout=15)
                except subprocess.TimeoutExpired: cube.kill(); cube.wait()
            server.cleanup()
            keys.shutdown(); keys.server_close()
    return 0


if __name__ == '__main__': sys.exit(main())
