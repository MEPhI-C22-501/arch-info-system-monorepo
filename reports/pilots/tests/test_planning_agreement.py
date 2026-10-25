"""Planning System export batch as agreed in issue #147 (INT-05/INT-08, D-05)."""
import copy
import json
import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import Client, Rejected, export_key, export_slot, planning
from db import Database
from etl import complete_planning_requests, load, pending_planning_requests, planning_extract
from maintenance import reconcile

KINDS = ['plan', 'demand', 'availability', 'allocation', 'forecast']


def portfolio_rows(prefix, demands):
    """Rows shaped like Planning createExport: demand/allocation are repeated
    inside plan.data and as top-level rows."""
    item = {'id': prefix + '-item', 'logicalItemId': prefix + '-logical', 'parentItemId': None, 'type': 'TASK',
            'name': 'Work', 'start': '2026-10-05', 'finish': '2026-10-16', 'plannedHours': 80}
    demand = [{'id': d, 'planItemId': item['id'], 'roleCode': 'backend', 'gradeCode': 'middle',
               'periodStart': '2026-10-05', 'periodEnd': '2026-10-09', 'hours': 40} for d in demands]
    allocation = [{'id': d + '-alloc', 'demandId': d, 'employeeId': '17', 'date': '2026-10-06',
                   'hours': 8, 'status': 'CONFIRMED'} for d in demands]
    plan = {'id': prefix + '-plan', 'projectId': prefix + '-project', 'name': 'Plan', 'planningMode': 'ANNUAL',
            'horizonStart': '2026-10-01', 'horizonEnd': '2026-12-31', 'items': [item], 'dependencies': [],
            'demands': demand, 'allocations': allocation, 'versionNumber': 1, 'revision': 1, 'contentRevision': 1,
            'reviewRound': 1, 'kind': 'PLAN', 'baseVersionId': None, 'status': 'ACTIVE', 'dataAsOf': None}
    rows = [{'entityType': 'plan', 'entityId': plan['id'], 'data': plan}]
    rows += [{'entityType': 'demand', 'entityId': d['id'], 'data': d} for d in demand]
    rows += [{'entityType': 'allocation', 'entityId': a['id'], 'data': a} for a in allocation]
    return rows


class Owner:
    """In-memory Planning System: POST requires Idempotency-Key and replays
    the stored batch for the same key; each new key materialises a batch."""

    def __init__(self):
        self.data = {'A': portfolio_rows('a', ['d1', 'd2']), 'B': portfolio_rows('b', ['d3'])}
        self.batches, self.keys, self.posts = {}, {}, 0
        self.clock = datetime(2026, 10, 25, 2, 0, tzinfo=timezone.utc)

    def request(self, path, params=None, body=None, idempotency_key=None):
        if body is not None:
            self.posts += 1
            if not idempotency_key:
                raise Rejected('SOURCE_HTTP_400')
            if idempotency_key in self.keys:
                return copy.deepcopy(self.batches[self.keys[idempotency_key]]['manifest'])
            self.clock += timedelta(minutes=1)
            rows = copy.deepcopy(self.data[body['portfolioId']])
            batch_id = 'batch-%d' % (len(self.batches) + 1)
            manifest = {'batchId': batch_id, 'portfolioId': body['portfolioId'], 'dataAsOf': self.clock.isoformat(),
                        'schemaVersion': '1.0.0', 'status': 'READY',
                        'expiresAt': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                        'counts': [{'entityType': k, 'count': sum(r['entityType'] == k for r in rows)} for k in KINDS]}
            self.batches[batch_id] = {'manifest': manifest, 'rows': rows}
            self.keys[idempotency_key] = batch_id
            return copy.deepcopy(manifest)
        batch = self.batches[path.split('/')[4]]
        if path.endswith('/rows'):
            return {'batchId': batch['manifest']['batchId'], 'dataAsOf': batch['manifest']['dataAsOf'],
                    'items': copy.deepcopy(batch['rows']), 'nextCursor': None}
        return copy.deepcopy(batch['manifest'])


class PlanningAgreement(unittest.TestCase):
    def setUp(self):
        self.db = Database('sqlite::memory:')
        self.db.initialize()
        self.owner = Owner()

    def tearDown(self):
        self.db.close()

    def load(self, portfolio, slot):
        return load(self.db, 'planning', lambda: planning_extract(self.owner, portfolio, slot), scope=portfolio)

    def ids(self, table, column='id'):
        return {r[0] for r in self.db.execute(f'SELECT {column} FROM dwh.{table}')}

    def test_key_is_deterministic_per_portfolio_and_hour(self):
        self.assertEqual(export_key('A', '2026-10-25T02'), export_key('A', '2026-10-25T02'))
        self.assertNotEqual(export_key('A', '2026-10-25T02'), export_key('A', '2026-10-25T03'))
        self.assertNotEqual(export_key('A', '2026-10-25T02'), export_key('B', '2026-10-25T02'))
        self.assertEqual(export_slot(datetime(2026, 10, 25, 2, 59, tzinfo=timezone.utc)), '2026-10-25T02')

    def test_same_slot_reuses_batch_new_slot_creates_one(self):
        first = planning(self.owner, 'A', '2026-10-25T02')[0]['batchId']
        again = planning(self.owner, 'A', '2026-10-25T02')[0]['batchId']
        later = planning(self.owner, 'A', '2026-10-25T03')[0]['batchId']
        self.assertEqual(first, again)
        self.assertNotEqual(first, later)
        self.assertEqual(len(self.owner.batches), 2)

    def test_nested_arrays_do_not_double_hours_and_version_is_derived(self):
        self.load('A', '2026-10-25T02')
        self.assertEqual(self.ids('fact_demand'), {'d1', 'd2'})
        self.assertEqual(self.db.execute('SELECT SUM(required_hours) FROM dwh.fact_demand').fetchone()[0], 80)
        self.assertEqual(self.db.execute('SELECT SUM(allocated_hours) FROM dwh.fact_allocation').fetchone()[0], 16)
        versions = {r[0] for r in self.db.execute(
            'SELECT plan_version_id FROM dwh.fact_demand UNION SELECT plan_version_id FROM dwh.fact_allocation')}
        self.assertEqual(versions, {'a-plan'})

    def test_repeated_load_of_same_batch_is_idempotent(self):
        for _ in range(2):
            self.load('A', '2026-10-25T02')
        self.assertEqual(self.db.execute('SELECT SUM(required_hours) FROM dwh.fact_demand').fetchone()[0], 80)
        self.assertEqual(len(self.owner.batches), 1)

    def test_full_snapshot_closes_missing_entity_only_in_own_portfolio(self):
        self.load('A', '2026-10-25T02')
        self.load('B', '2026-10-25T02')
        self.owner.data['A'] = portfolio_rows('a', ['d1'])
        self.load('A', '2026-10-25T03')
        self.assertEqual(self.ids('fact_demand'), {'d1', 'd3'})
        self.assertEqual(self.ids('fact_allocation'), {'d1-alloc', 'd3-alloc'})
        statuses = [r[0] for r in self.db.execute(
            "SELECT status FROM etl.reconciliation WHERE source='planning'")]
        self.assertTrue(statuses and all(s.endswith('_MATCH') for s in statuses), statuses)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM etl.reload_request").fetchone()[0], 0)

    def test_order_is_checked_per_portfolio(self):
        self.load('A', '2026-10-25T02')
        self.load('B', '2026-10-25T02')  # newer dataAsOf than A
        self.load('A', '2026-10-25T02')  # replay of A in the same slot is accepted
        checkpoint = json.loads(self.db.execute(
            "SELECT value FROM etl.checkpoint WHERE source='planning:A'").fetchone()[0])
        self.assertEqual(checkpoint['batchId'], 'batch-1')
        newer = self.load('A', '2026-10-25T03')
        stale = copy.deepcopy(self.owner.batches['batch-1'])
        with self.assertRaisesRegex(Rejected, 'OUT_OF_ORDER'):
            load(self.db, 'planning', lambda: ({k: [] for k in KINDS}, 'batch-1',
                                               stale['manifest']['dataAsOf'], None), scope='A')
        self.assertEqual(newer['status'], 'LOADED')

    def test_signal_is_completed_only_by_newer_batch(self):
        self.load('A', '2026-10-25T02')
        loaded = self.db.execute("SELECT value FROM etl.checkpoint WHERE source='planning:A'").fetchone()[0]
        as_of = json.loads(loaded)['dataAsOf']
        with self.db.transaction():
            self.db.execute("INSERT INTO etl.reload_request VALUES ('planning','a-project',?,'PlanActivated','PENDING')",
                            ('2026-10-25T01:30:00+00:00',))
            self.db.execute("INSERT INTO etl.reload_request VALUES ('planning','b-project',?,'PlanActivated','PENDING')",
                            ('2026-10-25T01:30:00+00:00',))
        complete_planning_requests(self.db, as_of, pending_planning_requests(self.db))
        state = dict(self.db.execute("SELECT aggregate_id,status FROM etl.reload_request").fetchall())
        self.assertEqual(state, {'a-project': 'COMPLETED', 'b-project': 'PENDING'})
        with self.db.transaction():
            self.db.execute("UPDATE etl.reload_request SET requested_at='2030-01-01T00:00:00+00:00' WHERE aggregate_id='b-project'")
        self.load('B', '2026-10-25T02')
        complete_planning_requests(self.db, as_of, pending_planning_requests(self.db))
        self.assertEqual(self.db.execute(
            "SELECT status FROM etl.reload_request WHERE aggregate_id='b-project'").fetchone()[0], 'PENDING')

    def test_only_active_plan_version_counts_in_current_figures(self):
        old, new = portfolio_rows('v1', ['old']), portfolio_rows('v2', ['new'])
        old[0]['data'].update(status='SUPERSEDED', projectId='p-1')
        new[0]['data'].update(projectId='p-1', versionNumber=2)
        self.owner.data['A'] = old + new
        self.load('A', '2026-10-25T02')
        # Both versions stay in the DWH for history ...
        self.assertEqual(self.ids('fact_demand'), {'old', 'new'})
        # ... but current planned and allocated hours come from ACTIVE only.
        rows = self.db.execute("SELECT id,required_hours,allocated_hours FROM dwh.cube_resources "
                               "WHERE id LIKE 'demand:%' OR id LIKE 'allocation:%' ORDER BY id").fetchall()
        self.assertEqual(rows, [('allocation:new-alloc', None, 8), ('demand:new', 40, None)])
        from report_engine import Engine
        engine = Engine(self.db)
        status = {r['record']: r['planStatus'] for r in engine.planning_rows('demand')}
        self.assertEqual(status, {'old': 'SUPERSEDED', 'new': 'ACTIVE'})

    def test_foreign_portfolio_batch_rejected(self):
        class Foreign(Owner):
            def request(self, path, params=None, body=None, idempotency_key=None):
                result = super().request(path, params, body, idempotency_key)
                if 'counts' in result:
                    result['portfolioId'] = 'B'
                return result
        with self.assertRaisesRegex(Rejected, 'FOREIGN_BATCH'):
            planning(Foreign(), 'A', '2026-10-25T02')


class IdempotentHttpRetry(unittest.TestCase):
    """The real Client: POST /exports carries the key and is retried with it."""

    def test_post_retried_with_same_key_after_503(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                seen.append(self.headers.get('Idempotency-Key'))
                status, body = (503, {}) if len(seen) == 1 else (202, {'batchId': 'b-1'})
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            client = Client('http://127.0.0.1:%d' % server.server_port, allow_http=True, interval=0)
            with patch('adapters.time.sleep'):
                result = client.request('/api/v1/exports', body={'portfolioId': 'A'},
                                        idempotency_key=export_key('A', '2026-10-25T02'))
            self.assertEqual(result, {'batchId': 'b-1'})
            self.assertEqual(len(seen), 2)
            self.assertEqual(seen[0], seen[1])
            self.assertEqual(seen[0], export_key('A', '2026-10-25T02'))
        finally:
            server.shutdown()
            server.server_close()

    def test_post_without_key_is_not_retried(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                calls.append(1)
                self.send_response(503)
                self.send_header('Content-Length', '0')
                self.end_headers()

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            client = Client('http://127.0.0.1:%d' % server.server_port, allow_http=True, interval=0)
            with patch('adapters.time.sleep'), self.assertRaisesRegex(Rejected, 'SOURCE_HTTP_503'):
                client.request('/api/v1/exports', body={'portfolioId': 'A'})
            self.assertEqual(len(calls), 1)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
