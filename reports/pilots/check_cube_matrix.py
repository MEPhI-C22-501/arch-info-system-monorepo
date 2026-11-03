"""Per-cube Cube/PostgreSQL timings: cold and warm, with and without pre-aggregations.

Synthetic volume in a temporary PostgreSQL. Every cube and mode gets a fresh
Cube process that loads only that cube's model: as committed, or with its
preAggregations block removed. Cold is the first query, including the build of
that cube's own pre-aggregation. Each warm request adds a unique harmless filter
(projectId <> bench-N), so it is executed instead of served from the result
cache. Ephemeral keys and passwords stay in memory; nothing is logged.
"""
import argparse
import concurrent.futures
import json
import os
import platform
import shutil
import subprocess
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
from check_cube import free_port
from db import Database

CUBE_DIR = Path(__file__).with_name('cube')
OCTOBER = ['2026-10-01', '2026-10-31']
# name, query, served by a pre-aggregation in the committed model
QUERIES = [
    ('TimeLogs', {'measures': ['TimeLogs.hours'], 'dimensions': ['TimeLogs.projectId'],
                  'timeDimensions': [{'dimension': 'TimeLogs.loggedDate', 'granularity': 'month', 'dateRange': OCTOBER}]}, True),
    ('WorkItems', {'measures': ['WorkItems.plannedHours', 'WorkItems.remainingHours', 'WorkItems.completionPercent'],
                   'dimensions': ['WorkItems.projectId']}, True),
    ('Defects', {'measures': ['Defects.opened', 'Defects.remaining'], 'dimensions': ['Defects.projectId'],
                 'timeDimensions': [{'dimension': 'Defects.createdAt', 'dateRange': OCTOBER}]}, True),
    ('TestResults', {'measures': ['TestResults.passPercent', 'TestResults.executed'], 'dimensions': ['TestResults.projectId'],
                     'timeDimensions': [{'dimension': 'TestResults.recordedAt', 'dateRange': OCTOBER}]}, True),
    ('TestRuns', {'measures': ['TestRuns.passPercent', 'TestRuns.executionPercent'], 'dimensions': ['TestRuns.projectId'],
                  'timeDimensions': [{'dimension': 'TestRuns.finishedAt', 'dateRange': OCTOBER}]}, True),
    ('Quality', {'measures': ['Quality.candidateDefectDensity'], 'dimensions': ['Quality.projectId']}, True),
    ('Resources', {'measures': ['Resources.utilizationPercent'], 'dimensions': ['Resources.projectId'],
                   'timeDimensions': [{'dimension': 'Resources.day', 'dateRange': OCTOBER}]}, True),
    ('WorkItems: медианы', {'measures': ['WorkItems.cycleMedian', 'WorkItems.leadMedian'], 'dimensions': ['WorkItems.projectId']}, False),
    ('DefectFlow', {'measures': ['DefectFlow.closed', 'DefectFlow.reopenPercent'], 'dimensions': ['DefectFlow.projectId'],
                    'timeDimensions': [{'dimension': 'DefectFlow.changedAt', 'dateRange': OCTOBER}]}, False),
    ('StatusFlow', {'measures': ['StatusFlow.averageWip'], 'dimensions': ['StatusFlow.projectId'],
                    'timeDimensions': [{'dimension': 'StatusFlow.day', 'dateRange': ['2026-10-01', '2026-10-07']}]}, False),
    ('Forecasts', {'measures': ['Forecasts.forecastFinish'], 'dimensions': ['Forecasts.projectId']}, False),
    ('PlanFact', {'measures': ['PlanFact.hours', 'PlanFact.plannedHours', 'PlanFact.overrun'], 'dimensions': ['PlanFact.projectId'],
                  'timeDimensions': [{'dimension': 'PlanFact.period', 'dateRange': OCTOBER}]}, False),
]
VOLUME = {'time_logs': 1000000, 'work_items': 10000, 'status_transitions': 20000, 'defects': 20000,
          'defect_transitions': 40000, 'test_runs': 2000, 'test_results': 200000, 'demands': 2000,
          'allocations': 20000, 'availability': 20000, 'forecasts': 50}


def fill(db):
    """Synthetic October 2026 facts for 50 projects and 300 users; no personal data."""
    v = VOLUME
    day = "(date '2026-10-01'+(n % 28)::int)::text"
    stamp = "'2026-10-31T00:00:00+00:00'"
    statements = [
        f"""INSERT INTO dwh.fact_time_log(id,user_id,project_id,work_item_id,logged_date,hours_cents)
            SELECT 'tl-'||n,'tracker-user-'||lpad((n%300)::text,3,'0'),'project-'||(n%50),'wi-'||(n%{v['work_items']}),{day},125
            FROM generate_series(1,{v['time_logs']}) n""",
        """INSERT INTO app.subject_binding SELECT 'user-'||lpad(n::text,3,'0'),'tracker-user-'||lpad(n::text,3,'0') FROM generate_series(0,299) n""",
        f"""INSERT INTO dwh.fact_work_item_daily(id,snapshot_date,work_item_id,project_id,user_id,planned_hours,actual_hours,remaining_hours,
              created_at,completed_at,category,is_overdue,cycle_days,lead_days,is_leaf,is_deleted,data_as_of,payload)
            SELECT 'wid-'||n,'2026-10-31','wi-'||n,'project-'||(n%50),'user-'||lpad((n%300)::text,3,'0'),8,(n%12),8-(n%12),
              {day}||'T09:00:00+00:00',CASE WHEN n%3=0 THEN (date '2026-10-01'+(n%28)::int+3)::text||'T18:00:00+00:00' END,
              CASE WHEN n%3=0 THEN 'COMPLETED' WHEN n%3=1 THEN 'WORKING' ELSE 'BACKLOG' END,(n%7=0)::int,
              CASE WHEN n%3=0 THEN 2+(n%5) END,CASE WHEN n%3=0 THEN 3+(n%5) END,1,0,{stamp},'{{}}'
            FROM generate_series(1,{v['work_items']}) n""",
        f"""INSERT INTO dwh.fact_status_transition(id,work_item_id,project_id,user_id,category,changed_at,data_as_of,payload)
            SELECT 'st-'||n,'wi-'||(n%{v['work_items']}),'project-'||(n%50),'user-'||lpad((n%300)::text,3,'0'),
              CASE WHEN n%2=0 THEN 'WORKING' ELSE 'COMPLETED' END,{day}||'T12:00:00+00:00',{stamp},'{{}}'
            FROM generate_series(1,{v['status_transitions']}) n""",
        f"""INSERT INTO dwh.fact_defect_daily(id,snapshot_date,defect_id,project_id,user_id,status_code,created_at,first_closed_at,close_days,
              history_known,is_open,reopen_count,is_deleted,data_as_of,payload)
            SELECT 'dd-'||n,'2026-10-31','d-'||n,'project-'||(n%50),'user-'||lpad((n%300)::text,3,'0'),
              CASE WHEN n%2=0 THEN 'CLOSED' ELSE 'OPEN' END,{day}||'T10:00:00+00:00',
              CASE WHEN n%2=0 THEN (date '2026-10-01'+(n%28)::int+2)::text||'T10:00:00+00:00' END,CASE WHEN n%2=0 THEN 2 END,
              1,(n%2),(n%5=0)::int,0,{stamp},'{{}}'
            FROM generate_series(1,{v['defects']}) n""",
        f"""INSERT INTO dwh.fact_defect_transition(id,defect_id,project_id,user_id,severity,to_status,changed_at,is_reopen,data_as_of,payload)
            SELECT 'dt-'||n,'d-'||(n%{v['defects']}),'project-'||(n%50),'user-'||lpad((n%300)::text,3,'0'),'MAJOR',
              CASE WHEN n%2=0 THEN 'CLOSED' ELSE 'REOPENED' END,{day}||'T15:00:00+00:00',(n%2),{stamp},'{{}}'
            FROM generate_series(1,{v['defect_transitions']}) n""",
        f"""INSERT INTO dwh.fact_test_run(id,run_id,project_id,user_id,status,finished_at,case_count,passed,failed,blocked,skipped,data_as_of,payload)
            SELECT 'tr-'||n,'run-'||n,'project-'||(n%50),'user-'||lpad((n%300)::text,3,'0'),'FINISHED',{day}||'T20:00:00+00:00',
              100,80,10,5,5,{stamp},'{{}}'
            FROM generate_series(1,{v['test_runs']}) n""",
        f"""INSERT INTO dwh.fact_test_result(id,result_id,run_id,case_id,project_id,user_id,result,recorded_at,data_as_of,payload)
            SELECT 'res-'||n,'res-'||n,'run-'||(n%{v['test_runs']}),'case-'||(n%5000),'project-'||(n%50),'user-'||lpad((n%300)::text,3,'0'),
              (ARRAY['PASSED','PASSED','PASSED','FAILED','BLOCKED','SKIPPED'])[1+n%6],{day}||'T19:00:00+00:00',{stamp},'{{}}'
            FROM generate_series(1,{v['test_results']}) n""",
        """INSERT INTO dwh.dim_date SELECT to_char(d,'YYYYMMDD')::int,d::date::text,to_char(d,'IYYY-"W"IW'),to_char(d,'YYYY-MM'),4,2026
            FROM generate_series(date '2026-10-01',date '2026-10-31',interval '1 day') d ON CONFLICT DO NOTHING""",
        f"""INSERT INTO dwh.fact_demand(id,demand_id,project_id,role_code,period_start,period_end,required_hours,data_as_of,payload)
            SELECT 'dem-'||n,'dem-'||n,'project-'||(n%50),'developer','2026-10-01',
              CASE WHEN n%2=0 THEN '2026-10-15' ELSE '2026-10-31' END,40,{stamp},'{{}}'
            FROM generate_series(1,{v['demands']}) n""",
        f"""INSERT INTO dwh.fact_allocation(id,demand_id,project_id,user_id,role_code,date_key,allocated_hours,status,data_as_of,payload)
            SELECT 'al-'||n,'dem-'||(n%{v['demands']}),'project-'||(n%50),'user-'||lpad((n%300)::text,3,'0'),'developer',
              to_char(date '2026-10-01'+(n%28)::int,'YYYYMMDD')::int,4,'CONFIRMED',{stamp},'{{}}'
            FROM generate_series(1,{v['allocations']}) n""",
        f"""INSERT INTO dwh.fact_availability(id,user_id,project_id,available_hours,status,day,data_as_of,payload)
            SELECT 'av-'||n,'user-'||lpad((n%300)::text,3,'0'),'project-'||(n%50),8,'CONFIRMED',{day},{stamp},'{{}}'
            FROM generate_series(1,{v['availability']}) n""",
        f"""INSERT INTO dwh.fact_forecast(id,project_id,forecast_finish,calculated_at,quality,data_as_of,payload)
            SELECT 'fc-'||n,'project-'||(n%50),'2026-12-01',{stamp},'COMPLETE',{stamp},'{{}}' FROM generate_series(1,{v['forecasts']}) n""",
    ]
    with db.transaction():
        for statement in statements:
            db.execute(statement)
        db.execute('ANALYZE')


FACT_INDEXES = ['star_work_item_latest', 'star_defect_latest', 'star_status_transition_item', 'star_availability_user']


def single_model(target, cube, rollups):
    """Only this cube's model; without rollups its preAggregations block (the last property) is removed."""
    target.mkdir()
    text = (CUBE_DIR/'model'/(cube+'.js')).read_text(encoding='utf-8').replace('\r\n', '\n')
    cut = text.find('\n  preAggregations:')
    if cut >= 0 and not rollups:
        text = text[:cut]+'\n});\n'
    (target/(cube+'.js')).write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--requests', type=int, default=100)
    parser.add_argument('--clients', type=int, default=20)
    parser.add_argument('--fact-indexes', choices=['on', 'off'], default='on',
                        help='off drops the fact lookup indexes to measure the state before them')
    args = parser.parse_args()
    artifact = Path(__file__).with_name('artifacts')/('cube-matrix-benchmark.json' if args.fact_indexes == 'on'
                                                      else 'cube-matrix-benchmark-no-indexes.json')
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='matrix-ephemeral', use='sig', alg='RS256')

    class Keys(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({'keys': [jwk]}).encode())

    keys = ThreadingHTTPServer(('127.0.0.1', 0), Keys)
    threading.Thread(target=keys.serve_forever, daemon=True).start()
    issuer = f'http://127.0.0.1:{keys.server_port}'
    node = os.getenv('NODE', 'node')
    stamp = int(time.time())
    token = jwt.encode({'iss': issuer, 'aud': 'reports', 'sub': 'matrix-analyst', 'iat': stamp, 'exp': stamp+3600,
                        'resource_access': {'reports': {'roles': ['reports-analyst']}}},
                       key, algorithm='RS256', headers={'kid': 'matrix-ephemeral'})
    bootstrap = """const Server=require('@cubejs-backend/server');
const config=require(process.env.REPORTS_CUBE_CONFIG);
config.schemaPath=process.env.REPORTS_MODEL_PATH;config.logger=()=>{};
new Server(config).listen().catch(()=>process.exit(1));"""
    models = Path(tempfile.mkdtemp(prefix='rm-', dir='/tmp'))
    with tempfile.TemporaryDirectory(prefix='rx-', dir='/tmp') as tmp:
        pgserver.PostgresServer.runtime_path = Path(tmp)/'run'
        pgserver.PostgresServer._lock = fasteners.InterProcessLock(Path(tmp)/'pg.lock')
        server = pgserver.get_server(Path(tmp)/'data', cleanup_mode='delete')
        cube = None
        try:
            uri = server.get_uri()
            db = Database(uri); db.initialize()
            started = time.perf_counter(); fill(db); fill_seconds = time.perf_counter()-started
            if args.fact_indexes == 'off':
                with db.transaction():
                    for index in FACT_INDEXES: db.execute('DROP INDEX dwh.'+index)
            pg_version = db.execute('SHOW server_version').fetchone()[0]
            db.close()
            parsed = urllib.parse.urlsplit(uri)
            host = urllib.parse.parse_qs(parsed.query).get('host', [parsed.hostname])[0]
            base_env = dict(os.environ, CUBEJS_DB_TYPE='postgres', CUBEJS_DB_HOST=host, CUBEJS_DB_NAME='postgres',
                            CUBEJS_DB_USER='postgres', CUBEJS_DEV_MODE='false', CUBEJS_CACHE_AND_QUEUE_DRIVER='memory',
                            CUBEJS_TELEMETRY='false', CUBEJS_PRE_AGGREGATIONS_BUILDER='true', CUBEJS_LOG_LEVEL='error',
                            CUBEJS_PRE_AGGREGATIONS_SCHEMA='reports_preaggregations',
                            REPORTS_OIDC_ISSUER=issuer, REPORTS_OIDC_JWKS_URL=issuer,
                            REPORTS_CUBE_CONFIG=str(CUBE_DIR/'cube.js'))
            results = []
            for (name, query, rollup), mode in [(q, m) for m in ('pre_aggregations', 'facts_only') for q in QUERIES]:
                cube_name = name.split(':')[0]
                model = models/(mode+'-'+cube_name.lower()+'-'+str(len(results)))
                single_model(model, cube_name, mode == 'pre_aggregations')
                port = free_port()
                cube = subprocess.Popen([node, '-e', bootstrap], cwd=CUBE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        env=dict(base_env, PORT=str(port), CUBEJS_PG_SQL_PORT=str(free_port()),
                                                 REPORTS_MODEL_PATH=os.path.relpath(model, CUBE_DIR)))

                def request(query):
                    url = f'http://127.0.0.1:{port}/cubejs-api/v1/load?'+urllib.parse.urlencode({'query': json.dumps(query)})
                    deadline = time.monotonic()+900
                    while time.monotonic() < deadline:
                        req = urllib.request.Request(url, headers={'Authorization': token})
                        try:
                            with urllib.request.urlopen(req, timeout=900) as response: result = json.load(response)
                        except urllib.error.HTTPError as error:
                            raise RuntimeError('Cube HTTP '+str(error.code)+': '+str(json.load(error).get('error', 'failed'))[:200]) from None
                        if result.get('error') == 'Continue wait': time.sleep(.1); continue
                        if result.get('error'): raise RuntimeError('Cube query failed')
                        return result['data']
                    raise RuntimeError('Cube query timed out')
                for _ in range(120):
                    if cube.poll() is not None: raise RuntimeError('Cube failed to start')
                    try:
                        urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/cubejs-api/v1/meta',
                                                                      headers={'Authorization': token}), timeout=5).read(); break
                    except (urllib.error.URLError, TimeoutError, ConnectionError): time.sleep(1)
                else: raise RuntimeError('Cube readiness timed out')
                start = time.perf_counter(); rows = request(query); cold = time.perf_counter()-start
                unique = iter(range(10**6))
                lock = threading.Lock()

                def varied():
                    # A different harmless filter per request defeats the result cache.
                    with lock: number = next(unique)
                    extra = {'member': cube_name+'.projectId', 'operator': 'notEquals', 'values': [f'bench-{number}']}
                    return dict(query, filters=[*query.get('filters', []), extra])

                def timed(_):
                    start = time.perf_counter(); request(varied()); return time.perf_counter()-start
                request(varied())
                # Cubes slower than 5 s cold get a short warm phase: 5 requests from 5 clients.
                total, clients = (args.requests, args.clients) if cold < 5 else (5, 5)
                with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as pool:
                    delays = sorted(pool.map(timed, range(total)))
                results.append({'cube': name, 'mode': mode, 'rollup_in_model': rollup and mode == 'pre_aggregations',
                                'rows': len(rows), 'cold_seconds': round(cold, 4), 'warm_requests': total, 'warm_clients': clients,
                                'warm_p50_seconds': round(delays[len(delays)//2], 4),
                                'warm_p95_seconds': round(delays[max(0, int(len(delays)*.95)-1)], 4)})
                print(json.dumps(results[-1], ensure_ascii=False), flush=True)
                cube.terminate(); cube.wait(timeout=30); cube = None
            output = {'cube': '1.6.75', 'postgres': pg_version, 'volume': VOLUME, 'fill_seconds': round(fill_seconds, 1),
                      'requests_per_query': args.requests, 'clients': args.clients,
                      'fact_indexes': args.fact_indexes == 'on',
                      'warm': 'unique harmless filter per request: executed each time, result cache bypassed; '
                              'cubes slower than 5 s cold get 5 requests from 5 clients',
                      'cold': 'first query on a fresh Cube process that loads only this cube; includes its own rollup build',
                      'queue_cache_driver': 'memory', 'pre_aggregation_storage': 'PostgreSQL (external: false)',
                      'runtime': 'Linux container: python:3.12.14-slim with Node from node:22.20.0-bookworm-slim',
                      'machine': platform.machine(), 'cpu_count': os.cpu_count(),
                      'node': subprocess.check_output([node, '--version'], text=True).strip(),
                      'results': results, 'measured_at': datetime.now(timezone.utc).isoformat()}
            if args.record: artifact.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps({k: v for k, v in output.items() if k != 'results'}, ensure_ascii=False))
        finally:
            if cube:
                cube.terminate()
                try: cube.wait(timeout=15)
                except subprocess.TimeoutExpired: cube.kill(); cube.wait()
            server.cleanup(); keys.shutdown(); keys.server_close()
            shutil.rmtree(models, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
