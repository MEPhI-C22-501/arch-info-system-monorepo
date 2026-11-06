"""Local T-INT-08 contract regression with the actual Reports consumer.

The source is the Planning FastAPI application, not a fabricated batch owner.
Only the HTTP transport is in-process. Synthetic authorization and SQLite DWH
do not constitute acceptance of the shared OIDC/PostgreSQL/CronJob stand.
"""
import copy
import importlib
import io
import json
import urllib.error
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from server import storage as db
from server.auth import DEMO_PORTFOLIO as PORT, DEMO_PROJECT as PID
from server.seed import stable
from test_application import call


KINDS = ('plan', 'demand', 'availability', 'allocation', 'forecast')
COUNTS = {'plan': 2, 'demand': 4, 'availability': 10, 'allocation': 6, 'forecast': 2}
MONEY_FIELDS = {'baselineBudget', 'currencyCode', 'estimatedTotalCost', 'budgetAdjustment', 'rate'}


class InProcessHTTP:
    """Send the real urllib client's requests to the real ASGI source."""

    def __init__(self, source):
        self.source = source
        self.journal = []

    def open(self, request, timeout):
        url = urlsplit(request.full_url)
        response = self.source.request(request.get_method(), url.path + ('?' + url.query if url.query else ''),
                                       content=request.data, headers=dict(request.header_items()))
        self.journal.append((request.get_method(), url.path, response.status_code))
        if response.status_code >= 400:
            raise urllib.error.HTTPError(request.full_url, response.status_code, response.reason_phrase,
                                         response.headers, io.BytesIO(response.content))
        return io.BytesIO(response.content)


@pytest.fixture
def reports(monkeypatch):
    pilots = Path(__file__).resolve().parents[2] / 'reports' / 'pilots'
    monkeypatch.syspath_prepend(str(pilots))
    return {name: importlib.import_module(name) for name in ('adapters', 'etl', 'db')}


@pytest.fixture
def export_fixture(client, monkeypatch, reports):
    """Issue #147 fixture: two weeks, historical/current versions and statuses.

    COMPLETE is an explicitly seeded contract sample. Production forecast
    calculation remains PARTIAL until its required sources are available.
    """
    with db.engine.begin() as connection:
        old = copy.deepcopy(db.find(connection, 'plan', stable('plan'))['data'])
        for item in old['items']:
            item['finish'] = '2026-10-16'
            if item['type'] == 'MILESTONE':
                item['start'] = item['finish']
        first = {**old['demands'][0], 'periodEnd': '2026-10-09', 'hours': 3}
        second = {**first, 'id': stable('etl-demand-week-2'),
                  'periodStart': '2026-10-12', 'periodEnd': '2026-10-16'}
        old['demands'] = [first, second]
        old['allocations'] = [
            {**old['allocations'][0], 'hours': 3, 'status': 'CONFIRMED'},
            {**old['allocations'][0], 'id': stable('etl-proposed'), 'demandId': second['id'],
             'date': '2026-10-12', 'hours': 3, 'status': 'PROPOSED'},
            {**old['allocations'][0], 'id': stable('etl-cancelled'), 'demandId': second['id'],
             'date': '2026-10-13', 'hours': 1, 'status': 'CANCELLED'},
        ]
        db.put(connection, 'plan', old, PORT, PID)

    # Use the producer's version cloning to exercise its real identifier mapping.
    active = call(client, 'POST', f'projects/{PID}/versions',
                  {'baseVersionId': old['id'], 'kind': 'SCENARIO', 'name': 'ETL current'}, expected=201)
    with db.engine.begin() as connection:
        old.update(status='SUPERSEDED', dataAsOf=db.now())
        active.update(status='ACTIVE', dataAsOf=db.now(), baselineBudget=18000, currencyCode='RUB')
        for allocation, status in zip(active['allocations'], ('CONFIRMED', 'PROPOSED', 'CANCELLED')):
            allocation['status'] = status
        db.put(connection, 'plan', old, PORT, PID)
        db.put(connection, 'plan', active, PORT, PID)
        project = copy.deepcopy(db.find(connection, 'project', PID)['data'])
        project.update(status='ACTIVE', activePlanVersionId=active['id'], revision=project['revision'] + 1)
        db.put(connection, 'project', project, PORT, PID)
        availability = copy.deepcopy(db.all_rows(connection, 'availability', PORT)[0]['data'])
        availability['status'] = 'DRAFT'
        db.put(connection, 'availability', availability, PORT)
        for number, quality in enumerate(('PARTIAL', 'COMPLETE')):
            forecast = {'id': stable('etl-forecast-' + quality), 'planVersionId': active['id'],
                        'calculatedAt': f'2026-10-29T0{number}:00:00Z', 'dataAsOf': db.now(),
                        'forecastFinish': None, 'remainingHours': 8,
                        'estimatedTotalCost': 20000 if quality == 'COMPLETE' else None,
                        'budgetAdjustment': 2000 if quality == 'COMPLETE' else None,
                        'currencyCode': 'RUB', 'quality': quality,
                        'missingInputs': ['TASK_FACTS'] if quality == 'PARTIAL' else []}
            db.put(connection, 'forecast', forecast, PORT, PID)

    app_module = importlib.import_module('server.app')
    original_actor = app_module.actor

    def synthetic_actor(request):
        token = request.headers.get('authorization', '')
        if token in {'Bearer fixture-reports', 'Bearer fixture-reports-cost'}:
            from server.auth import Actor
            return Actor(token, {'S-06'}, {'reports.read', 'reports.export'} |
                         ({'cost.read'} if token.endswith('-cost') else set()), {PORT}, {PID}, set())
        return original_actor(request)

    monkeypatch.setattr(app_module, 'actor', synthetic_actor)

    class Consumer(reports['adapters'].Client):
        def request(self, path, params=None, body=None, *, idempotency_key=None):
            if path.endswith('/rows'):
                params = {**(params or {}), 'pageSize': 2}
            return super().request(path, params, body, idempotency_key=idempotency_key)

    def consumer(cost=False):
        result = Consumer('http://planning.test', 'fixture-reports-cost' if cost else 'fixture-reports',
                          allow_http=True, interval=0)
        result.opener = InProcessHTTP(client)
        return result

    return active, consumer


def money_fields(value):
    if isinstance(value, dict):
        return set(value).intersection(MONEY_FIELDS) | set().union(*(money_fields(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(money_fields(v) for v in value))
    return set()


@pytest.mark.parametrize('cost', [False, True])
def test_real_reports_consumer_counts_pages_replay_and_money(export_fixture, reports, cost):
    _, consumer = export_fixture
    source = consumer(cost)
    manifest, rows = reports['adapters'].planning(source, PORT, '2026-11-07T02')
    assert dict(Counter(r['entityType'] for r in rows)) == COUNTS
    assert {r['entityType']: r['count'] for r in manifest['counts']} == COUNTS
    pages = [entry for entry in source.opener.journal if entry[1].endswith('/rows')]
    assert len(pages) == 12
    assert len({(r['entityType'], r['entityId']) for r in rows}) == sum(COUNTS.values())
    assert reports['adapters'].planning(source, PORT, '2026-11-07T02') == (manifest, rows)
    page = source.request(f'/api/v1/exports/{manifest["batchId"]}/rows')
    assert source.request(f'/api/v1/exports/{manifest["batchId"]}/rows') == page
    assert bool(money_fields(rows)) is cost
    if cost:
        forecasts = [r['data'] for r in rows if r['entityType'] == 'forecast']
        assert {r['quality'] for r in forecasts} == {'PARTIAL', 'COMPLETE'}
        assert next(r for r in forecasts if r['quality'] == 'PARTIAL')['estimatedTotalCost'] is None
        assert next(r for r in forecasts if r['quality'] == 'COMPLETE')['estimatedTotalCost'] == 20000


def test_real_reports_load_replanning_and_archive_preserve_history(client, export_fixture, reports):
    active, consumer = export_fixture
    warehouse = reports['db'].Database('sqlite::memory:')
    warehouse.initialize()
    source = consumer()
    try:
        def load(slot):
            return reports['etl'].load(warehouse, 'planning',
                lambda: reports['etl'].planning_extract(source, PORT, slot), scope=PORT)

        assert load('2026-11-07T02')['rows'] == sum(COUNTS.values())
        assert load('2026-11-07T02')['rows'] == sum(COUNTS.values())
        assert warehouse.execute('SELECT SUM(required_hours) FROM dwh.fact_demand').fetchone()[0] == 12
        # Current cube reads only ACTIVE, counts no nested arrays or CANCELLED allocations.
        assert warehouse.execute('SELECT SUM(required_hours),SUM(allocated_hours) FROM dwh.cube_resources').fetchone() == (6, 6)
        assert warehouse.execute('SELECT COUNT(*) FROM dwh.cube_resources WHERE available_hours IS NOT NULL').fetchone()[0] == 9

        # A new approved version is cloned by the actual Planning API.
        successor = call(client, 'POST', f'projects/{PID}/versions',
            {'baseVersionId': active['id'], 'kind': 'SCENARIO', 'name': 'ETL replan'}, expected=201)
        with db.engine.begin() as connection:
            previous = copy.deepcopy(db.find(connection, 'plan', active['id'])['data'])
            previous['status'] = 'SUPERSEDED'
            db.put(connection, 'plan', previous, PORT, PID)
            successor.update(status='ACTIVE', dataAsOf=db.now())
            for allocation, original in zip(successor['allocations'], active['allocations']):
                allocation['status'] = original['status']
            db.put(connection, 'plan', successor, PORT, PID)
            project = copy.deepcopy(db.find(connection, 'project', PID)['data'])
            project['activePlanVersionId'] = successor['id']
            project['revision'] += 1
            db.put(connection, 'project', project, PORT, PID)
        assert load('2026-11-07T03')['rows'] == 30
        assert warehouse.execute('SELECT SUM(required_hours),SUM(allocated_hours) FROM dwh.cube_resources').fetchone() == (6, 6)
        checkpoint = json.loads(warehouse.execute('SELECT value FROM etl.checkpoint WHERE source=?', ('planning:' + PORT,)).fetchone()[0])
        assert checkpoint['batchId'] == reports['adapters'].planning(source, PORT, '2026-11-07T03')[0]['batchId']

        project = call(client, 'GET', 'projects/' + PID)
        call(client, 'POST', 'projects/' + PID + '/archive', {'reason': 'ETL archive'},
             role='R-01', revision=project['revision'])
        assert load('2026-11-07T04')['rows'] == 10  # portfolio availability remains
        assert warehouse.execute('SELECT COUNT(*) FROM dwh.plan_version').fetchone()[0] == 0
        assert warehouse.execute('SELECT COUNT(*) FROM dwh.fact_demand').fetchone()[0] == 0
        assert warehouse.execute("SELECT COUNT(*) FROM dwh.source_snapshot WHERE source='planning' AND entity='plan'").fetchone()[0] == 2
    finally:
        warehouse.close()


def test_expired_source_batch_cannot_advance_reports_checkpoint(export_fixture, reports):
    _, consumer = export_fixture
    source = consumer()
    warehouse = reports['db'].Database('sqlite::memory:')
    warehouse.initialize()
    try:
        extract = lambda: reports['etl'].planning_extract(source, PORT, '2026-11-07T02')
        reports['etl'].load(warehouse, 'planning', extract, scope=PORT)
        checkpoint = warehouse.execute('SELECT value FROM etl.checkpoint WHERE source=?', ('planning:' + PORT,)).fetchone()[0]
        expired, _ = reports['adapters'].planning(source, PORT, '2026-11-07T03')
        with db.engine.begin() as connection:
            batch = copy.deepcopy(db.find(connection, 'batch', expired['batchId'])['data'])
            batch['expiresAt'] = '2000-01-01T00:00:00Z'
            db.put(connection, 'batch', batch, PORT)
        for suffix in ('', '/rows'):
            response = source.opener.source.get(f'/api/v1/exports/{expired["batchId"]}' + suffix,
                                                headers={'Authorization': 'Bearer fixture-reports'})
            assert response.status_code == 409
            assert response.json()['message'] == 'BATCH_EXPIRED'
        with pytest.raises(reports['adapters'].Rejected, match='SOURCE_HTTP_409'):
            reports['etl'].load(warehouse, 'planning',
                lambda: reports['etl'].planning_extract(source, PORT, '2026-11-07T03'), scope=PORT)
        assert warehouse.execute('SELECT value FROM etl.checkpoint WHERE source=?', ('planning:' + PORT,)).fetchone()[0] == checkpoint
        assert warehouse.execute('SELECT SUM(required_hours) FROM dwh.cube_resources').fetchone()[0] == 6
    finally:
        warehouse.close()


def test_second_page_failure_is_atomic_and_same_batch_recovers(export_fixture, reports, monkeypatch):
    _, consumer = export_fixture
    source = consumer()
    warehouse = reports['db'].Database('sqlite::memory:')
    warehouse.initialize()
    real_open = source.opener.open
    failed_requests, waits = [], []
    unavailable = True

    def interrupt_second_page(request, timeout):
        url = urlsplit(request.full_url)
        if unavailable and url.path.endswith('/rows') and parse_qs(url.query).get('cursor'):
            failed_requests.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 503, 'Injected source outage', {}, io.BytesIO(b''))
        return real_open(request, timeout)

    monkeypatch.setattr(source.opener, 'open', interrupt_second_page)
    # Observe bounded backoff without delaying the suite or changing other modules' clocks.
    monkeypatch.setattr(reports['adapters'], 'time',
                        SimpleNamespace(monotonic=reports['adapters'].time.monotonic, sleep=waits.append))
    try:
        def load():
            return reports['etl'].load(warehouse, 'planning',
                lambda: reports['etl'].planning_extract(source, PORT, '2026-11-07T02'), scope=PORT)

        with pytest.raises(reports['adapters'].Rejected, match='SOURCE_HTTP_503'):
            load()
        assert len(failed_requests) == 4 and len(set(failed_requests)) == 1
        assert [delay for delay in waits if delay > 0] == [2, 4, 8]
        assert sum(path.endswith('/rows') for _, path, _ in source.opener.journal) == 1
        for table in ('etl.checkpoint', 'stg.record', 'dwh.source_record', 'dwh.source_snapshot',
                      'dwh.plan_version', 'dwh.fact_demand', 'dwh.fact_allocation', 'dwh.fact_availability'):
            assert warehouse.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
        assert warehouse.execute('SELECT status,error_code FROM etl.batch').fetchall() == [
            ('REJECTED', 'SOURCE_HTTP_503')]

        unavailable = False
        assert load()['rows'] == sum(COUNTS.values())
        assert warehouse.execute('SELECT COUNT(*) FROM dwh.source_record').fetchone()[0] == sum(COUNTS.values())
        assert warehouse.execute('SELECT SUM(required_hours),SUM(allocated_hours) FROM dwh.cube_resources').fetchone() == (6, 6)
        checkpoint = json.loads(warehouse.execute('SELECT value FROM etl.checkpoint WHERE source=?',
                                                  ('planning:' + PORT,)).fetchone()[0])
        with db.engine.connect() as connection:
            batches = db.all_rows(connection, 'batch', PORT)
        assert len(batches) == 1 and checkpoint['batchId'] == batches[0]['id']
        assert dict(Counter(row[0] for row in warehouse.execute('SELECT status FROM etl.batch'))) == {
            'REJECTED': 1, 'LOADED': 1}
    finally:
        warehouse.close()
