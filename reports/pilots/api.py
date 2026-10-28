"""Read-only R-01 pilot. This is not the complete Reports product API."""
import json
import os
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import jwt
from db import Database

GROUPS = {"project": "project_id", "employee": "user_id", "month": "substr(logged_date,1,7)", "record": "id"}


def freshness(db):
    state = db.execute("SELECT data_as_of,loaded_at FROM etl.source_state WHERE source='tracker'").fetchone()
    if state is None:
        return None, 'STALE'
    latest_failure = db.execute("SELECT MAX(completed_at) FROM etl.batch WHERE source='tracker' AND status='REJECTED'").fetchone()[0]
    age = (datetime.now(timezone.utc)-datetime.fromisoformat(state[0])).total_seconds()
    fresh = 0 <= age <= 3600 and (latest_failure is None or latest_failure <= state[1])
    return state[0], 'FRESH' if fresh else 'STALE'


def authorize(claims):
    subject = claims.get("sub")
    access = claims.get('resource_access')
    resource = access.get('reports') if isinstance(access, dict) else None
    roles = resource.get('roles') if isinstance(resource, dict) else None
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        raise PermissionError('invalid roles')
    roles = set(roles)
    if not isinstance(subject, str) or not subject or len(subject) > 128:
        raise PermissionError("invalid subject")
    if "reports-admin" in roles or "reports-analyst" in roles:
        return None
    if "reports-member" in roles:
        return subject
    raise PermissionError("unsupported role")


def report(db, claims, group="project", limit=1000, offset=0, start_date=None, end_date=None):
    subject = authorize(claims)
    if group not in GROUPS or type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or offset < 0:
        raise ValueError("Unsupported group")
    if (start_date is None) != (end_date is None):
        raise ValueError('Both period boundaries required')
    if start_date is not None:
        start_date, end_date = date.fromisoformat(start_date).isoformat(), date.fromisoformat(end_date).isoformat()
        if start_date > end_date: raise ValueError('Invalid period')
    field = GROUPS[group]
    base = ' FROM dwh.report_time_log'
    filters, params = [], []
    if subject is not None:
        binding = db.execute('SELECT tracker_user_id FROM app.subject_binding WHERE subject=?', (subject,)).fetchone()
        if binding is None:
            raise PermissionError('Subject binding is not approved')
        filters.append('user_id=?'); params.append(subject)
    if start_date:
        filters.append('logged_date >= ? AND logged_date <= ?'); params.extend([start_date, end_date])
    if filters: base += ' WHERE '+' AND '.join(filters)
    grouped = base+f' GROUP BY {field}'
    total = db.execute(f'SELECT COUNT(*) FROM (SELECT {field}'+grouped+') report_groups', tuple(params)).fetchone()[0]
    sql = f'SELECT {field} AS dimension,SUM(hours_cents),COUNT(*)'+grouped+f' ORDER BY {field} LIMIT ? OFFSET ?'
    # PostgreSQL SUM(bigint) is Decimal. Integral cents keep JSON numeric.
    data = [{"dimension": row[0], "hours": int(row[1])/100, "records": row[2]} for row in db.execute(sql, tuple(params+[limit, offset]))]
    stamp, state = freshness(db)
    return {"reportId": "R-01", "group": group, "data": data, "dataAsOf": stamp,
            "freshness": state, 'period': {'startDate': start_date, 'endDate': end_date},
            'pagination': {'limit': limit, 'offset': offset, 'totalGroups': total, 'hasMore': offset+len(data) < total}}


class Handler(BaseHTTPRequestHandler):
    jwks = None

    def log_message(self, *args):
        pass  # Authorization and source payloads must not enter access logs.

    def send_json(self, status, data):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 405:
            self.send_header('Allow', 'GET')
        self.end_headers()
        self.wfile.write(raw)

    def method_not_allowed(self):
        from product_http import handle
        if handle(self): return
        self.send_json(405, {'error': 'read-only API'})

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = method_not_allowed

    def do_GET(self):
        from product_ui import serve
        if serve(self): return
        from product_http import handle
        if handle(self): return
        path = urlsplit(self.path)
        status, data = 404, {"error": "not found"}
        if path.path in {"/health", "/livez"}:
            status, data = 200, {"status": "ok"}
        elif path.path == '/readyz':
            try:
                db = Database(os.environ['REPORTS_DATABASE_URL'])
                try:
                    _, state = freshness(db)
                    status, data = (200, {'status': 'ready'}) if state == 'FRESH' else (503, {'status': 'not ready'})
                finally:
                    db.close()
            except Exception:
                status, data = 503, {'status': 'not ready'}
        elif path.path == "/pilot/reports/time-logs":
            token = self.headers.get("Authorization", "")
            try:
                if not token.startswith("Bearer "):
                    raise jwt.InvalidTokenError()
                token = token[7:]
                key = self.jwks.get_signing_key_from_jwt(token).key
                claims = jwt.decode(token, key, algorithms=["RS256"], audience="reports",
                                    issuer=os.environ["REPORTS_OIDC_ISSUER"],
                                    options={"require": ["exp", "iat", "sub", "iss", "aud"]})
                # The legacy helper predates 070. Never expose its historical
                # admin shortcut through HTTP; business-wide access is analyst.
                from report_engine import roles as client_roles
                from report_engine import Problem
                try:
                    permitted = client_roles(claims)-{'reports-admin'}
                except Problem:
                    raise PermissionError('invalid roles') from None
                claims = dict(claims, resource_access={'reports': {'roles': sorted(permitted)}})
                db = Database(os.environ["REPORTS_DATABASE_URL"])
                try:
                    query = parse_qs(path.query, keep_blank_values=True)
                    if set(query)-{'group', 'limit', 'offset', 'startDate', 'endDate'} or any(len(v) != 1 for v in query.values()):
                        raise ValueError('Unknown or repeated parameter')
                    data = report(db, claims, query.get('group', ['project'])[0],
                                  int(query.get('limit', ['1000'])[0]), int(query.get('offset', ['0'])[0]),
                                  query.get('startDate', [None])[0], query.get('endDate', [None])[0])
                    status = 200
                finally:
                    db.close()
            except jwt.PyJWKClientConnectionError:
                status, data = 503, {"error": "identity provider unavailable"}
            except (jwt.InvalidTokenError, jwt.PyJWKClientError):
                status, data = 401, {"error": "unauthorized"}
            except PermissionError:
                status, data = 403, {"error": "forbidden"}
            except ValueError:
                status, data = 422, {"error": "invalid query"}
            except Exception:
                status, data = 503, {"error": "dependency unavailable"}
        self.send_json(status, data)


if __name__ == "__main__":
    Handler.jwks = jwt.PyJWKClient(os.environ["REPORTS_OIDC_JWKS_URL"])
    ThreadingHTTPServer((os.getenv("REPORTS_BIND", "127.0.0.1"), 8081), Handler).serve_forever()
