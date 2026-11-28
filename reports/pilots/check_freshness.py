"""Measured freshness: a change at the neighbour's live service until it is visible in the Reports layer.

Each neighbour runs locally from its own compose file (as in check_live_sources.py).
The script changes one record in the neighbour's demo database at t0, runs the
Reports ETL with the stand's cadence and polls the reports engine every second
until the change is visible (t1); afterwards the change is reverted. For the
tracker the ETL runs every 60 s as etl-scheduler does and the change happens at
a random moment of the tick. Reference Manager, QA and Planning are loaded on a
schedule (1 h, 1 h, 24 h or 1 h after a Planning signal): waiting a whole tick
proves nothing, so the measured value is from the tick to visibility and the
promise is the tick plus that value.
"""
import argparse
import json
import random
import subprocess
import sys
import tempfile

import time
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from adapters import Client
from check_live_sources import client_token
from db import Database
from etl import catalog_extract, load, planning_extract, tracker_extract
from report_engine import AN, Engine

ANALYST = {'sub': 'freshness-analyst', 'exp': 0, 'scope': '', 'resource_access': {'reports': {'roles': [AN]}}}
PSQL = {'tracker': ['task-tracker-postgres-1', 'psql', '-U', 'task_tracker', '-d', 'task_tracker'],
        'reference': ['reference_manager_database', 'psql', '-U', 'reference_manager', '-d', 'reference_manager'],
        'qa': ['qa-system-qa-db-1', 'psql', '-U', 'qa', '-d', 'qa'],
        'planning': ['planning-system-postgres-1', 'sh', '-c', 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"', 'psql']}
# One record changed and reverted in the neighbour's demo database, and how the change shows in Reports.
CHANGES = {
    'tracker': ("UPDATE time_log_entry SET hours=hours+0.25 WHERE id=(SELECT min(id::text)::uuid FROM time_log_entry)",
                "UPDATE time_log_entry SET hours=hours-0.25 WHERE id=(SELECT min(id::text)::uuid FROM time_log_entry)",
                'R-01 total hours'),
    'reference': ("UPDATE employees SET family_name=family_name||'-свежесть' WHERE id=(SELECT min(id) FROM employees)",
                  "UPDATE employees SET family_name=replace(family_name,'-свежесть','') WHERE id=(SELECT min(id) FROM employees)",
                  'employee name in report labels'),
    # The changed result is marked in its comment, so the revert returns exactly that one.
    'qa': ("UPDATE run_result SET status='FAILED',comment='reports-freshness' WHERE id=(SELECT min(id::text)::uuid FROM run_result WHERE status='PASSED' AND comment IS NULL)",
           "UPDATE run_result SET status='PASSED',comment=NULL WHERE comment='reports-freshness'", 'R-07 failed results'),
    'planning': ("UPDATE records SET data=jsonb_set(data,'{availableHours}',to_jsonb((data->>'availableHours')::numeric+1)) "
                 "WHERE id=(SELECT min(id) FROM records WHERE kind='availability')",
                 "UPDATE records SET data=jsonb_set(data,'{availableHours}',to_jsonb((data->>'availableHours')::numeric-1)) "
                 "WHERE id=(SELECT min(id) FROM records WHERE kind='availability')",
                 'available hours of the plan'),
}
PROMISE = {'tracker': ('до 2 мин', 60), 'reference': ('1 ч (ежечасный List)', 3600), 'qa': ('1 ч', 3600),
           'planning': ('24 ч; 1 ч после сигнала Planning', 3600)}


def sql(source, statement):
    result = subprocess.run(['docker', 'exec', '-i', *PSQL[source], '-At', '-v', 'ON_ERROR_STOP=1', '-c', statement],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode: raise SystemExit(f'{source}: {result.stderr.strip()[:300]}')
    return result.stdout.strip()


def observe(source, db):
    engine = Engine(db)
    if source == 'tracker':
        rows = db.execute('SELECT MIN(logged_date),MAX(logged_date) FROM dwh.fact_time_log').fetchone()
        if not rows[0]: return None
        return engine.query('R-01', ANALYST, {'params': {'periodFrom': rows[0], 'periodTo': rows[1]}, 'slice': ['project']})['totals']['M-01']
    if source == 'reference': return sorted(engine.names('employee').values())
    if source == 'qa':
        year = {'periodFrom': date.today().replace(month=1, day=1).isoformat(), 'periodTo': date.today().isoformat()}
        return engine.query('R-07', ANALYST, {'params': year, 'slice': ['project']})['totals'].get('failed')
    return sum(float(r.get('availableHours') or 0) for r in engine.planning_rows('availability'))


def measure(source, args, values):
    if source == 'tracker':
        client = Client(args.tracker_url, client_token(args.tracker_issuer, 'reports-client', values['REPORTS_TRACKER_CLIENT_SECRET']), allow_http=True)
        extract = lambda: tracker_extract(client)
    elif source == 'reference':
        client = Client(args.reference_url, client_token(args.reference_issuer, 'reports-client', values['REPORTS_REFERENCE_CLIENT_SECRET']), allow_http=True)
        extract = lambda: catalog_extract(client, 'reference')
    elif source == 'qa':
        client = Client(args.qa_url, 'demo-qa-reports-reader', allow_http=True)
        extract = lambda: catalog_extract(client, 'qa')
    else:
        client = Client(args.planning_url, 'demo-S-06', allow_http=True)
        extract = lambda: planning_extract(client, args.planning_portfolio, 'fresh-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
    scope = args.planning_portfolio if source == 'planning' else None
    with tempfile.TemporaryDirectory(prefix='reports-fresh-', ignore_cleanup_errors=True) as tmp:
        db = Database('sqlite:'+str(Path(tmp)/'fresh.sqlite')); db.initialize()

        try:
            load(db, source, extract, scope=scope)
            before = observe(source, db)
            # etl-scheduler in one thread (SQLite connections stay in their thread): a load every tick;
            # the change happens at a random moment of the tick, the report is polled every second.
            tick = 60 if source == 'tracker' else None
            next_load = time.monotonic()+(tick or 0)
            if tick: time.sleep(random.uniform(1, tick-1))
            started = time.monotonic(); sql(source, CHANGES[source][0])
            if not tick: next_load = started
            seen = None
            while time.monotonic()-started < (tick or 0)+120:
                if time.monotonic() >= next_load:
                    load(db, source, extract, scope=scope)
                    next_load += tick or 3600
                if observe(source, db) != before: seen = time.monotonic()-started; break
                time.sleep(1)
        finally:
            if CHANGES[source][1]: sql(source, CHANGES[source][1])
            db.close()
    return seen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=list(CHANGES), action='append', required=True)
    parser.add_argument('--runs', type=int, default=1, help='Repeat the measurement; the tracker phase is random each time')
    parser.add_argument('--tracker-url', default='http://localhost:8080')
    parser.add_argument('--tracker-issuer', default='http://localhost:8081/realms/arch-info-system')
    parser.add_argument('--reference-url', default='http://localhost:8083')
    parser.add_argument('--reference-issuer', default='http://localhost:8183/realms/arch-info-system')
    parser.add_argument('--qa-url', default='http://localhost:8090')
    parser.add_argument('--planning-url', default='http://localhost:8080')
    parser.add_argument('--planning-portfolio', default='10000000-0000-4000-8000-000000000001')
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    values = dotenv_values(Path.home()/'secrets.env')
    target = Path(__file__).with_name('artifacts')/'freshness-verification.json'
    previous = json.loads(target.read_text(encoding='utf-8')) if args.record and target.is_file() else {}
    rows = {r['source']: r for r in previous.get('measurements', [])}
    for source in args.source:
        samples = [measure(source, args, values) for _ in range(args.runs)]
        promise, tick = PROMISE[source]
        rows[source] = {'source': source, 'promised': promise, 'tick_seconds': tick, 'what_changed': CHANGES[source][2],
                        'samples_seconds': [round(s, 1) if s is not None else None for s in samples],
                        'scheduled_tick_included': source == 'tracker',
                        'measured_at_utc': datetime.now(timezone.utc).isoformat(),
                        'within_promise': all(s is not None and (s if source == 'tracker' else s+tick) <= {'tracker': 120}.get(source, tick+120) for s in samples)}
    output = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'measurements': sorted(rows.values(), key=lambda r: r['source']),
              'passed': all(r['within_promise'] for r in rows.values()),
              'method': 'neighbour demo database changed at t0; Reports ETL at the stand cadence; reports engine polled every second'}
    if args.record: target.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False))
    return 0 if output['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
