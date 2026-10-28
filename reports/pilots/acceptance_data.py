"""Fixed synthetic acceptance data; seed is a version label, no randomness.

300 logs = 150 x 1.25 + 150 x 2.50 = 562.50 hours.
Each of 3 projects has 50 logs per member: 62.50 + 125.00 = 187.50.
These expected values are stored literally, independently of ETL/report code.
"""
import copy
import json
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from demo import MEMBER_1, MEMBER_2, fixture

SEED = 'reports-acceptance-v1'
EXPECTED = {'logs': 300, 'tasks': 40, 'iterations': 2, 'projects': 3,
            'runs': 2, 'defects': 15, 'total_hours': 562.5,
            'member1_hours': 187.5, 'member2_hours': 375.0,
            'project_hours': 187.5, 'member1_project_hours': 62.5}
STAMP = '2026-10-01T00:00:00Z'


def uid(n): return str(uuid.UUID(int=10000+n))


def dataset():
    base = fixture()
    projects = [uid(i) for i in range(3)]
    iterations = [dict(base['iterations'][0], id=uid(10+i), name='Iteration '+str(i+1)) for i in range(2)]
    tasks = [dict(copy.deepcopy(base['work-items'][0]), id=uid(100+i), title='Task '+str(i+1),
                  projectId=projects[i % 3], iterationId=iterations[i % 2]['id']) for i in range(40)]
    logs = []
    for i in range(300):
        # Distribute exactly 100 logs per project over 39 tasks; task 40 has no logs.
        task = tasks[3*((i//3) % 13)+i % 3]
        logs.append(dict(base['time-logs'][i % 6], id=uid(1000+i), workItemId=task['id'],
                         userId=MEMBER_1 if i % 2 == 0 else MEMBER_2,
                         hours=1.25 if i % 2 == 0 else 2.5, loggedDate='2026-10-01'))
    for task in tasks:
        task['actualHours'] = sum(row['hours'] for row in logs if row['workItemId'] == task['id'])
        task['remainingHours'] = task['plannedHours']-task['actualHours']
    tracker = {'work-items': tasks, 'time-logs': logs, 'iterations': iterations,
               'statuses': base['statuses'],
               'history': [dict(base['history'][0], id=uid(2000+i), workItemId=task['id'])
                           for i, task in enumerate(tasks)]}
    qa = {
        'test-cases': [{'id': uid(3000+i), 'title': 'Case '+str(i+1)} for i in range(101)],
        'test-plans': [{'id': uid(3200), 'title': 'Acceptance plan'}],
        'test-runs': [{'id': uid(3300+i), 'status': 'FINISHED'} for i in range(2)],
        'test-results': [{'id': uid(3400+i), 'testCaseId': uid(3000+i), 'status': 'PASSED'} for i in range(4)],
        'defects': [{'id': uid(3500+i), 'status': 'REOPENED' if i < 3 else 'CLOSED',
                     'reopenCount': 1 if i < 3 else 0} for i in range(15)],
    }
    # The reporting endpoint's published items schema is an opaque object.
    # These are fixtures for that endpoint, not full QA write-domain objects.
    reference = {name: [{'id': 1, 'revision': 1, 'is_deleted': False}]
                 for name in ['org_units', 'positions', 'project_roles', 'grades']}
    reference['employees'] = [{'id': i+1, 'revision': 1, 'is_deleted': i == 100} for i in range(101)]
    plan_id, item_id = uid(4000), uid(4001)
    planning = [
        {'entityType': 'plan', 'entityId': plan_id, 'data': {
            'id': plan_id, 'name': 'Acceptance', 'projectId': projects[0], 'planningMode': 'ANNUAL',
            'horizonStart': '2026-10-01', 'horizonEnd': '2026-10-31', 'items': [], 'dependencies': [],
            'demands': [], 'allocations': [], 'versionNumber': 1, 'revision': 1, 'contentRevision': 1,
            'reviewRound': 0, 'kind': 'PLAN', 'baseVersionId': None, 'status': 'DRAFT', 'dataAsOf': STAMP}},
        {'entityType': 'demand', 'entityId': uid(4002), 'data': {
            'id': uid(4002), 'planItemId': item_id, 'roleCode': 'developer', 'gradeCode': 'middle',
            'periodStart': '2026-10-01', 'periodEnd': '2026-10-31', 'hours': 40}},
        {'entityType': 'availability', 'entityId': uid(4003), 'data': {
            'id': uid(4003), 'employeeId': 'employees/1', 'date': '2026-10-01', 'calendarCode': 'demo',
            'timeZone': 'Europe/Moscow', 'nominalHours': 8, 'absenceHours': 0, 'availableHours': 8, 'status': 'CONFIRMED'}},
        {'entityType': 'allocation', 'entityId': uid(4004), 'data': {
            'id': uid(4004), 'demandId': uid(4002), 'employeeId': 'employees/1',
            'date': '2026-10-01', 'hours': 4, 'status': 'CONFIRMED'}},
        {'entityType': 'forecast', 'entityId': uid(4005), 'data': {
            'id': uid(4005), 'planVersionId': plan_id, 'dataAsOf': STAMP, 'calculatedAt': STAMP,
            'quality': 'PARTIAL', 'missingInputs': ['RATE'], 'remainingHours': None, 'forecastFinish': None}},
    ]
    return {'tracker': tracker, 'qa': qa, 'reference': reference, 'planning': planning, 'projects': projects}


@contextmanager
def source_server(data, public_jwk=None):
    """HTTP fixtures only; never log headers, cookies or request payload values."""
    calls = []
    batch = uid(5000)
    manifest = {'batchId': batch, 'portfolioId': uid(5001), 'dataAsOf': STAMP, 'schemaVersion': '1.0.0',
                'status': 'READY', 'expiresAt': (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                'counts': [{'entityType': row['entityType'], 'count': 1} for row in data['planning']]}

    class Source(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def reply(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            path = urlsplit(self.path).path
            calls.append(('POST', path))
            if path == '/planning/api/v1/exports':
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                if body != {'portfolioId': uid(5001)}: return self.reply(422, {})
                return self.reply(202, manifest)
            self.reply(405, {})

        def do_GET(self):
            url = urlsplit(self.path); parts = url.path.strip('/').split('/'); query = parse_qs(url.query)
            calls.append(('GET', self.path))
            if url.path == '/jwks' and public_jwk is not None:
                return self.reply(200, {'keys': [public_jwk]})
            if parts[0] in {'tracker', 'qa'} and parts[1:4] == ['api', 'v1', 'reports']:
                source, resource = parts[0], parts[-1]
                rows = data[source][resource]
                if source == 'tracker' and resource == 'statuses': return self.reply(200, rows)
                page, size = int(query['page'][0]), int(query['pageSize'][0])
                result = {'items': rows[(page-1)*size:page*size], 'page': page, 'pageSize': size,
                          'totalPages': (len(rows)+size-1)//size}
                if source == 'tracker': result['total'] = len(rows)
                return self.reply(200, result)
            if parts[0] == 'reference' and parts[1] == 'v1':
                resource = parts[-1]; rows = data['reference'][resource]
                if query.get('allowDeleted') != ['true']: return self.reply(422, {})
                start = int(query.get('pageToken', ['0'])[0]); size = int(query['pageSize'][0])
                end = start+size
                return self.reply(200, {resource: rows[start:end], 'nextPageToken': str(end) if end < len(rows) else None})
            if url.path == '/planning/api/v1/exports/'+batch: return self.reply(200, manifest)
            if url.path == '/planning/api/v1/exports/'+batch+'/rows':
                # Short cursor pages exercise opaque pagination independently of pageSize.
                start = int(query.get('cursor', ['0'])[0]); end = start+2
                return self.reply(200, {'batchId': batch, 'dataAsOf': STAMP, 'items': data['planning'][start:end],
                                       'nextCursor': str(end) if end < len(data['planning']) else None})
            self.reply(404, {})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Source)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield 'http://127.0.0.1:'+str(server.server_port), calls, manifest
    finally: server.shutdown(); server.server_close(); thread.join()
