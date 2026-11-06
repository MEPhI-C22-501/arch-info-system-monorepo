"""Read-only Reference Manager 1.1 client and atomic current HR projection.

Source IDs/revisions are preserved. No salaries, working-hour assumptions or
approved plan snapshots are modified by a refresh.
"""
import copy
import hashlib
import json
import os
import time
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from . import storage as db
from .domain import fail

COLLECTIONS = ('employees', 'assignments', 'positions', 'org_units', 'absences')
SNAPSHOT_ID = 'reference-manager-current'


class ReferenceManagerError(RuntimeError):
    """Sanitized adapter failure; excludes tokens, response bodies and HR data."""


def hr_required():
    development = os.environ.get('APP_ENV') == 'development'
    mode = os.environ.get('HR_MODE', 'demo' if development else 'real')
    if mode not in {'demo', 'real'}:
        raise ReferenceManagerError('HR_MODE must be demo or real')
    if mode == 'demo' and not development:
        raise ReferenceManagerError('Demo HR requires development')
    return mode == 'real'


def checked_url(value):
    parsed = urlsplit(value)
    local = parsed.hostname in {'localhost', '127.0.0.1', '::1', 'reference-manager', 'rm-api', 'keycloak'}
    dev_http = os.environ.get('APP_ENV') == 'development' and os.environ.get('RM_LOCAL_HTTP') == 'true' and local
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and dev_http))):
        raise ReferenceManagerError('RM requires HTTPS; local HTTP needs explicit development configuration')
    return value.rstrip('/')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def source_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError()
    except (ValueError, AttributeError, TypeError):
        raise ReferenceManagerError('RM readTime must be RFC3339 UTC') from None
    return parsed.isoformat().replace('+00:00', 'Z')


def calendar_date(value):
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except (TypeError, ValueError):
        raise ReferenceManagerError('RM contains an invalid calendar date') from None


def positive_integer(value):
    return type(value) is int and value > 0


def validate_record(collection, row):
    if (not isinstance(row, dict) or not positive_integer(row.get('id'))
            or not positive_integer(row.get('revision')) or type(row.get('is_deleted')) is not bool):
        raise ReferenceManagerError('RM record requires numeric id/revision and is_deleted')
    if collection == 'employees':
        if (row.get('employment_state') not in {'EMPLOYED', 'DISMISSED'}
                or row.get('account_state') not in {'PENDING', 'ENABLED', 'DISABLED'}
                or not all(isinstance(row.get(k), str) and row[k].strip() for k in ('family_name', 'given_name', 'username'))):
            raise ReferenceManagerError('RM employee state or identity is invalid')
        subject = row.get('account_user_id')
        if subject is not None and not isinstance(subject, str):
            raise ReferenceManagerError('RM account subject is invalid')
        if row['account_state'] == 'ENABLED' and (not subject or not subject.strip()):
            raise ReferenceManagerError('RM enabled account has no subject')
        calendar_date(row.get('hire_date'))
        if row.get('dismissal_date'):calendar_date(row['dismissal_date'])
    if collection in {'assignments', 'absences'}:
        if not positive_integer(row.get('employee_id')):
            raise ReferenceManagerError('RM employee reference is invalid')
        calendar_date(row.get('start_date'))
        if row.get('end_date'):
            calendar_date(row['end_date'])
            if row['end_date'] < row['start_date']:
                raise ReferenceManagerError('RM period ends before it starts')
        elif collection == 'absences':
            raise ReferenceManagerError('RM absence requires end_date')
    if collection == 'assignments' and not all(positive_integer(row.get(k)) for k in ('org_unit_id', 'position_id')):
        raise ReferenceManagerError('RM assignment reference is invalid')


class ReferenceManagerClient:
    def __init__(self, base_url, token, *, transport=None, page_size=100, sleep=time.sleep):
        self.base_url = checked_url(base_url)
        if not self.base_url.endswith('/v1') or not token or not 1 <= page_size <= 100:
            raise ReferenceManagerError('RM requires /v1 base URL, token and pageSize 1..100')
        self.token, self.transport, self.page_size, self.sleep = token, transport, page_size, sleep

    @classmethod
    def from_env(cls):
        base = os.environ.get('RM_BASE_URL', '')
        checked_url(base)
        token = os.environ.get('RM_TOKEN')
        if not token:
            endpoint = checked_url(os.environ.get('RM_TOKEN_URL', ''))
            client_id, secret = os.environ.get('RM_CLIENT_ID'), os.environ.get('RM_CLIENT_SECRET')
            if not client_id or not secret:
                raise ReferenceManagerError('Set RM_TOKEN or RM_TOKEN_URL/RM_CLIENT_ID/RM_CLIENT_SECRET')
            try:
                with httpx.Client(timeout=httpx.Timeout(10, connect=3), follow_redirects=False) as client:
                    response = client.post(endpoint, data={'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': secret})
                    response.raise_for_status()
                    token = response.json()['access_token']
            except (httpx.HTTPError, ValueError, KeyError):
                raise ReferenceManagerError('RM service token could not be obtained') from None
        return cls(base, token)

    def _get(self, client, collection, params):
        for attempt in range(3):
            try:
                response = client.get(self.base_url + '/' + collection + '/', params=params)
            except httpx.TransportError:
                if attempt == 2:raise ReferenceManagerError('RM network unavailable') from None
            else:
                if response.status_code == 200:
                    try:return response.json()
                    except ValueError:raise ReferenceManagerError('RM returned invalid JSON') from None
                if response.status_code not in {408, 429} and response.status_code < 500:
                    raise ReferenceManagerError(f'RM read refused with HTTP {response.status_code}')
                if attempt == 2:raise ReferenceManagerError('RM retry limit reached')
            self.sleep(2 ** attempt)

    def fetch(self, *, read_time=None):
        read_time = source_time(read_time or db.now())
        collections = {}
        with httpx.Client(headers={'Authorization': 'Bearer ' + self.token}, transport=self.transport,
                          timeout=httpx.Timeout(10, connect=3), follow_redirects=False) as client:
            for collection in COLLECTIONS:
                rows, identifiers, tokens = [], set(), set()
                token = None
                for _ in range(10000):
                    # RM sorts by ID by default, but explicitly rejects ID as order_by.
                    params = {'pageSize': self.page_size, 'allowDeleted': 'true', 'readTime': read_time}
                    if token:params['pageToken'] = token
                    body = self._get(client, collection, params)
                    if not isinstance(body, dict) or not isinstance(body.get(collection), list):
                        raise ReferenceManagerError('RM returned an invalid collection page')
                    for row in body[collection]:
                        validate_record(collection, row)
                        if row['id'] in identifiers:raise ReferenceManagerError('RM returned duplicate source IDs')
                        identifiers.add(row['id']);rows.append(row)
                    token = body.get('nextPageToken')
                    if token in (None, ''):break
                    if not isinstance(token, str) or token in tokens:
                        raise ReferenceManagerError('RM returned a repeated or invalid page token')
                    tokens.add(token)
                else:raise ReferenceManagerError('RM page limit reached')
                collections[collection] = sorted(rows, key=lambda r: r['id'])
        subjects = [r['account_user_id'] for r in collections['employees'] if r.get('account_user_id')]
        if len(subjects) != len(set(subjects)):
            raise ReferenceManagerError('RM returned duplicate account subjects')
        return {'readTime': read_time, 'collections': collections}


def snapshot_summary(snapshot):
    return {'source': 'ReferenceManager', 'contractVersion': '1.1.0', 'readTime': snapshot['readTime'],
            'counts': {k: len(v) for k, v in snapshot['collections'].items()},
            'sha256': hashlib.sha256(canonical(snapshot['collections']).encode()).hexdigest()}


def refresh_cache(client, *, read_time=None):
    # Every network call completes before opening the write transaction.
    snapshot = client.fetch(read_time=read_time)
    summary = snapshot_summary(snapshot)
    with db.engine.begin() as c:
        c.execute(select(db.schema_versions).with_for_update()).all()
        old = db.find(c, 'hr_snapshot', SNAPSHOT_ID)
        if old:
            previous = old['data']
            if datetime.fromisoformat(snapshot['readTime'].replace('Z', '+00:00')) < datetime.fromisoformat(previous['readTime'].replace('Z', '+00:00')):
                raise ReferenceManagerError('RM refresh would move the cache backwards')
            for name in COLLECTIONS:
                revisions = {r['id']: r for r in previous['collections'][name]}
                for row in snapshot['collections'][name]:
                    before = revisions.get(row['id'])
                    if before and (row['revision'] < before['revision'] or (row['revision'] == before['revision'] and row != before)):
                        raise ReferenceManagerError('RM source revision regressed or conflicts')
        if old and summary['sha256'] == old['data']['sha256']:
            old_data = copy.deepcopy(old['data']);old_data.update(readTime=snapshot['readTime'], fetchedAt=db.now())
            db.put(c, 'hr_snapshot', old_data, 'technical')
            return {**summary, 'changed': False}
        seen = set()
        for row in snapshot['collections']['employees']:
            identifier = 'employees/' + str(row['id']);seen.add(identifier)
            employee = {'id': identifier, 'source': 'ReferenceManager', 'sourceId': row['id'], 'sourceRevision': row['revision'],
                        'displayName': ' '.join(row[k].strip() for k in ('family_name', 'given_name', 'middle_name') if row.get(k)),
                        'accountSubject': row.get('account_user_id'), 'employmentState': row['employment_state'],
                        'accountState': row['account_state'], 'isDeleted': row['is_deleted'], 'sourceMissing': False,
                        'hireDate': row.get('hire_date'), 'dismissalDate': row.get('dismissal_date'),
                        'eligibleForAssignment': not row['is_deleted'] and row['employment_state'] == 'EMPLOYED'
                        and row['account_state'] == 'ENABLED' and bool(row.get('account_user_id'))}
            current = db.find(c, 'employee', identifier)
            if not current or current['data'] != employee:db.put(c, 'employee', employee, 'technical')
        for current in db.all_rows(c, 'employee'):
            if current['data'].get('source') == 'ReferenceManager' and current['id'] not in seen:
                employee = {**current['data'], 'sourceMissing': True, 'eligibleForAssignment': False}
                if employee != current['data']:db.put(c, 'employee', employee, 'technical')
        db.put(c, 'hr_snapshot', {'id': SNAPSHOT_ID, **snapshot, **summary, 'fetchedAt': db.now()}, 'technical')
    return {**summary, 'changed': True}


def validate_new_allocations(c, allocations, previous=()):
    """HR refresh never rewrites history; new/changed assignments use current HR."""
    before = {a['id']: a for a in previous}
    required = hr_required()
    for allocation in allocations:
        if allocation['status'] == 'CANCELLED' or allocation == before.get(allocation['id']):continue
        if required and cache_status(c)['quality'] != 'CURRENT':
            fail(422, 'Для нового назначения нужен актуальный кадровый справочник (не старше часа)')
        row = db.find(c, 'employee', allocation['employeeId'])
        if not row or row['data'].get('source') != 'ReferenceManager':
            if required:fail(422, 'Сначала обновите кадровый справочник сотрудника')
            continue
        employee = row['data']
        if (not employee['eligibleForAssignment'] or (employee.get('hireDate') and allocation['date'] < employee['hireDate'])
                or (employee.get('dismissalDate') and allocation['date'] > employee['dismissalDate'])):
            fail(422, 'Кадровый справочник запрещает новое назначение сотрудника')


def cache_status(c):
    row = db.find(c, 'hr_snapshot', SNAPSHOT_ID)
    required = hr_required()
    if not row:
        return {'source': 'ReferenceManager' if required else 'local-fixture',
                'quality': 'UNAVAILABLE' if required else 'DEMO', 'required': required, 'readTime': None, 'fetchedAt': None}
    data = row['data']
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(data['readTime'].replace('Z', '+00:00'))).total_seconds()
    return {'source': 'ReferenceManager', 'quality': 'CURRENT' if age <= 3600 else 'STALE', 'required': required,
            'readTime': data['readTime'], 'fetchedAt': data['fetchedAt']}
