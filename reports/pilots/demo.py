"""Synthetic, deterministic data. No personal data or authentication material."""
import json
import os
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

MEMBER_1 = "11111111-1111-4111-8111-111111111111"
MEMBER_2 = "22222222-2222-4222-8222-222222222222"
PROJECT = "33333333-3333-4333-8333-333333333333"
TASK = "44444444-4444-4444-8444-444444444444"


def fixture(subjects=None, size=6):
    subjects = subjects or {"member1": MEMBER_1, "member2": MEMBER_2}
    stamp = "2026-10-01T00:00:00Z"
    work = {"id": TASK, "type": "TASK", "title": "Synthetic task", "description": "Pilot data",
            "statusId": str(uuid.UUID(int=5)), "priorityId": str(uuid.UUID(int=6)),
            "plannedHours": 20, "actualHours": 15, "remainingHours": 5, "version": 1,
            "children": [], "projectId": PROJECT, "status": "IN_PROGRESS", "createdAt": stamp, "updatedAt": stamp}
    logs = [{"id": str(uuid.UUID(int=100+i)), "workItemId": TASK,
             "userId": subjects["member1" if i % 2 == 0 else "member2"],
             "loggedDate": f"2026-10-{1+i%28:02d}", "hours": 1.25 if i % 2 == 0 else 2.5,
             "comment": "Synthetic", "createdAt": stamp} for i in range(size)]
    work['actualHours'] = sum(row['hours'] for row in logs)
    work['remainingHours'] = work['plannedHours']-work['actualHours']
    iteration = {'id': str(uuid.UUID(int=7)), 'name': 'Synthetic iteration',
                 'startDate': '2026-10-01', 'endDate': '2026-10-31',
                 'state': 'ACTIVE', 'baseline': {}, 'result': {}}
    work['iterationId'] = iteration['id']
    status = {'id': work['statusId'], 'name': 'IN_PROGRESS', 'active': True,
              'boardOrder': 1, 'category': 'OPEN'}
    history = {'id': str(uuid.UUID(int=8)), 'workItemId': TASK, 'occurredAt': stamp,
               'actorId': subjects['member1'], 'changedFields': ['statusId'],
               'oldValues': {}, 'newValues': {'statusId': status['id']}}
    return {'work-items': [work], 'time-logs': logs, 'iterations': [iteration],
            'history': [history], 'statuses': [status]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/health":
            data, status = {"status": "ok"}, 200
        elif url.path.startswith("/api/v1/reports/"):
            resource = url.path.rsplit("/", 1)[1]
            subjects = None
            path = os.getenv("REPORTS_DEMO_SUBJECTS")
            if path:
                with open(path) as stream:
                    subjects = json.load(stream)
            if os.getenv('REPORTS_DEMO_PRODUCT') == '1':
                from product_fixture import business_fixture
                rows = business_fixture(subjects)['tracker'].get(resource)
            else:
                rows = fixture(subjects).get(resource)
            if rows is None:
                data, status = {"error": "not found"}, 404
            elif resource == 'statuses':
                data, status = rows, 200  # The owner's contract is an array, not a page.
            else:
                params = parse_qs(url.query)
                try:
                    page, size = int(params.get("page", [1])[0]), int(params.get("pageSize", [100])[0])
                    if page < 1 or not 1 <= size <= 500:
                        raise ValueError()
                    data = {"items": rows[(page-1)*size:page*size], "page": page, "pageSize": size,
                            "total": len(rows), "totalPages": (len(rows)+size-1)//size}
                    status = 200
                except ValueError:
                    data, status = {"error": "invalid page"}, 422
        else:
            data, status = {"error": "not found"}, 404
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    ThreadingHTTPServer((os.getenv("REPORTS_BIND", "127.0.0.1"), 8080), Handler).serve_forever()
