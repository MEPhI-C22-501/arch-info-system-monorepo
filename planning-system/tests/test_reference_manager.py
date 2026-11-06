import copy
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from server import storage as db
from server.auth import DEMO_PORTFOLIO as PORT, DEMO_PROJECT as PID
from server.reference_manager import (COLLECTIONS, ReferenceManagerClient, ReferenceManagerError,
                                      cache_status, hr_required, refresh_cache, validate_new_allocations)
from server.seed import stable
from test_application import activate, call, confirm, draft, plan


def source_row(identifier=1, **changes):
    return {'id': identifier, 'revision': 1, 'is_deleted': False, **changes}


def employee(identifier=1, **changes):
    row = source_row(identifier, family_name='Иванов', given_name='Иван', middle_name='Иванович',
                      username=f'user-{identifier}', personnel_number=str(identifier), hire_date='2024-01-01',
                      employment_state='EMPLOYED', account_state='ENABLED', account_user_id=f'sub-{identifier}')
    return {**row, **changes}


def source():
    return {'employees': [employee()], 'assignments': [source_row(employee_id=1, org_unit_id=1, position_id=1,
            start_date='2024-01-01', end_date=None)], 'positions': [source_row(code='dev', name='Разработчик')],
            'org_units': [source_row(code='it', name='ИТ', kind='DEPARTMENT')],
            'absences': [source_row(employee_id=1, kind='VACATION', start_date='2026-12-01', end_date='2026-12-10')]}


class FixtureClient:
    def __init__(self, collections=None):
        self.collections = collections or source()

    def fetch(self, read_time=None):
        return {'readTime': read_time or db.now(), 'collections': copy.deepcopy(self.collections)}


def adapter(handler, **kwargs):
    return ReferenceManagerClient('https://rm.test/v1', 'secret-fixture', transport=httpx.MockTransport(handler), sleep=lambda _: None, **kwargs)


def test_reads_all_pages_and_five_collections_with_shared_read_time():
    called = []
    data = source()

    def handler(request):
        collection = request.url.path.split('/')[-2]
        assert request.method == 'GET' and collection in COLLECTIONS
        assert request.headers['Authorization'] == 'Bearer secret-fixture'
        assert request.url.params['allowDeleted'] == 'true'
        assert request.url.params['pageSize'] == '1'
        assert 'order_by' not in request.url.params
        assert request.url.params['readTime'] == '2026-11-07T00:00:00Z'
        called.append(collection)
        if collection == 'employees' and 'pageToken' not in request.url.params:
            return httpx.Response(200, json={collection: data[collection], 'nextPageToken': 'second'})
        if collection == 'employees':
            assert request.url.params['pageToken'] == 'second'
            return httpx.Response(200, json={collection: [employee(2)]})
        return httpx.Response(200, json={collection: data[collection]})

    snapshot = adapter(handler, page_size=1).fetch(read_time='2026-11-07T00:00:00Z')
    assert [row['id'] for row in snapshot['collections']['employees']] == [1, 2]
    assert len(called) == 6 and 'salaries' not in called


@pytest.mark.parametrize('fault', ['cycle', 'duplicate-id', 'duplicate-subject', 'date', 'identity'])
def test_rejects_incomplete_or_ambiguous_source(fault):
    def handler(request):
        collection = request.url.path.split('/')[-2]
        rows = copy.deepcopy(source()[collection])
        if collection == 'employees':
            if fault == 'cycle':return httpx.Response(200, json={'employees': [], 'nextPageToken': 'same'})
            if fault == 'duplicate-id':rows.append(copy.deepcopy(rows[0]))
            if fault == 'duplicate-subject':rows.append(employee(2, account_user_id='sub-1'))
            if fault == 'identity':rows[0]['id'] = 'employees/1'
        if collection == 'absences' and fault == 'date':rows[0]['start_date'] = '2026-02-30'
        return httpx.Response(200, json={collection: rows})

    with pytest.raises(ReferenceManagerError):adapter(handler).fetch()


@pytest.mark.parametrize('status, attempts', [(401, 1), (403, 1), (429, 3), (503, 3)])
def test_bounded_retries_do_not_expose_tokens_or_response_body(status, attempts):
    called = []

    def handler(request):
        called.append(request)
        return httpx.Response(status, text='private HR data and secret-fixture')

    with pytest.raises(ReferenceManagerError) as error:adapter(handler).fetch()
    assert len(called) == attempts
    assert 'private' not in str(error.value) and 'secret-fixture' not in str(error.value)


def test_failure_after_first_collection_preserves_whole_cache(client):
    refresh_cache(FixtureClient())
    with db.engine.connect() as c:before = list(db.all_rows(c, 'employee')) + list(db.all_rows(c, 'hr_snapshot'))

    def handler(request):
        if request.url.path.endswith('/employees/'):
            return httpx.Response(200, json={'employees': [employee(family_name='Переименован', revision=2)]})
        return httpx.Response(503)

    with pytest.raises(ReferenceManagerError):refresh_cache(adapter(handler))
    with db.engine.connect() as c:after = list(db.all_rows(c, 'employee')) + list(db.all_rows(c, 'hr_snapshot'))
    assert before == after


def test_rename_and_dismissal_update_only_current_cache_not_baseline(client):
    activate(client)
    with db.engine.connect() as c:
        plans = copy.deepcopy([dict(r) for r in db.all_rows(c, 'plan')])
        availability = copy.deepcopy([dict(r) for r in db.all_rows(c, 'availability')])
    fixture = FixtureClient()
    refresh_cache(fixture)
    fixture.collections['employees'][0].update(family_name='Петров', revision=2)
    refresh_cache(fixture)
    with db.engine.connect() as c:
        person = db.find(c, 'employee', 'employees/1')['data']
        assert person['displayName'] == 'Петров Иван Иванович'
        assert person['sourceId'] == 1 and person['accountSubject'] == 'sub-1'
    fixture.collections['employees'][0].update(employment_state='DISMISSED', account_state='DISABLED', dismissal_date='2026-11-06', revision=3)
    refresh_cache(fixture)
    with db.engine.connect() as c:
        assert not db.find(c, 'employee', 'employees/1')['data']['eligibleForAssignment']
        assert [dict(r) for r in db.all_rows(c, 'plan')] == plans
        assert [dict(r) for r in db.all_rows(c, 'availability')] == availability


def test_replay_is_idempotent_and_regressed_or_conflicting_revision_rolls_back(client):
    fixture = FixtureClient()
    assert refresh_cache(fixture)['changed'] is True
    with db.engine.connect() as c:revision = db.find(c, 'employee', 'employees/1')['revision']
    assert refresh_cache(fixture)['changed'] is False
    with db.engine.connect() as c:assert db.find(c, 'employee', 'employees/1')['revision'] == revision
    fixture.collections['employees'][0]['family_name'] = 'Conflict without revision'
    with pytest.raises(ReferenceManagerError):refresh_cache(fixture)
    fixture.collections['employees'][0]['revision'] = 2
    refresh_cache(fixture)
    fixture.collections['employees'][0]['revision'] = 1
    with pytest.raises(ReferenceManagerError):refresh_cache(fixture)
    with db.engine.connect() as c:assert db.find(c, 'employee', 'employees/1')['data']['sourceRevision'] == 2


def test_missing_employee_becomes_unavailable_without_deleting_history(client):
    fixture = FixtureClient()
    refresh_cache(fixture)
    fixture.collections['employees'] = []
    refresh_cache(fixture)
    with db.engine.connect() as c:
        person = db.find(c, 'employee', 'employees/1')['data']
        assert person['sourceMissing'] and not person['eligibleForAssignment']
        assert person['sourceRevision'] == 1 and person['displayName']


@pytest.mark.parametrize('changes', [{'employment_state':'DISMISSED'}, {'is_deleted':True}, {'account_state':'PENDING'}, {'account_state':'DISABLED'}])
def test_current_hr_state_blocks_new_ui_and_bulk_assignments(client, changes):
    fixture = FixtureClient()
    fixture.collections['employees'][0].update(changes)
    refresh_cache(fixture)
    with db.engine.begin() as c:
        db.put(c, 'availability', {'id':'rm-availability','employeeId':'employees/1','date':'2026-10-05',
               'nominalHours':8,'absenceHours':0,'availableHours':8,'status':'CONFIRMED'}, PORT)
    options = call(client, 'GET', 'resource-options?projectId='+PID)
    person = next(x for x in options['employees'] if x['id'] == 'employees/1')
    assert person['name'] == 'Иванов Иван Иванович' and not person['eligibleForAssignment']
    assert options['hrCache']['source'] == 'ReferenceManager'
    body = {'demandId':stable('demand'),'employeeId':'employees/1','date':'2026-10-05','hours':2}
    call(client, 'POST', f'versions/{stable("plan")}/assignments', body, revision=1, expected=422)
    candidate = draft(plan(client));candidate['allocations'].append({'id':str(uuid4()), **body, 'status':'PROPOSED'})
    call(client, 'PUT', f'versions/{stable("plan")}/draft', candidate, revision=1, expected=422)


def test_cancellation_and_unchanged_history_remain_available(client):
    refresh_cache(FixtureClient())
    allocation = {'id':'old','employeeId':'employees/1','date':'2026-10-05','hours':2,'status':'PROPOSED'}
    fixture = FixtureClient();fixture.collections['employees'][0].update(employment_state='DISMISSED', revision=2)
    refresh_cache(fixture)
    with db.engine.begin() as c:
        validate_new_allocations(c, [allocation], [allocation])
        validate_new_allocations(c, [{**allocation, 'status':'CANCELLED'}], [allocation])
        with pytest.raises(HTTPException):validate_new_allocations(c, [{**allocation,'hours':3}], [allocation])


def test_real_mode_fails_closed_before_source_is_read(client, monkeypatch):
    monkeypatch.setenv('HR_MODE', 'real')
    with db.engine.begin() as c:
        assert cache_status(c)['quality'] == 'UNAVAILABLE'
        with pytest.raises(HTTPException):validate_new_allocations(c, [{'id':'x','employeeId':'employees/unknown','date':'2026-10-05','status':'PROPOSED'}])


def test_local_http_requires_explicit_development_flag(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('RM_LOCAL_HTTP', raising=False)
    with pytest.raises(ReferenceManagerError):ReferenceManagerClient('http://localhost:8083/v1', 'fixture')
    monkeypatch.setenv('RM_LOCAL_HTTP', 'true')
    ReferenceManagerClient('http://localhost:8083/v1', 'fixture')
    with pytest.raises(ReferenceManagerError):ReferenceManagerClient('http://external.test/v1', 'fixture')
    monkeypatch.setenv('APP_ENV', 'staging')
    with pytest.raises(ReferenceManagerError):ReferenceManagerClient('http://localhost:8083/v1', 'fixture')


def test_cache_freshness_uses_source_time_not_fetch_time(client):
    fixture = FixtureClient()
    refresh_cache(fixture, read_time='2026-01-01T00:00:00Z')
    with db.engine.connect() as c:assert cache_status(c)['quality'] == 'STALE'
    refresh_cache(fixture, read_time=datetime.now(timezone.utc).isoformat())
    with db.engine.connect() as c:assert cache_status(c)['quality'] == 'CURRENT'


def test_pending_account_without_subject_is_readable_but_not_assignable():
    def handler(request):
        collection = request.url.path.split('/')[-2]
        rows = source()[collection]
        if collection == 'employees':rows[0].update(account_state='PENDING', account_user_id='')
        return httpx.Response(200, json={collection: rows})
    result = adapter(handler).fetch()
    assert result['collections']['employees'][0]['account_state'] == 'PENDING'


def test_dismissal_blocks_confirmation_of_previously_proposed_allocation(client):
    with db.engine.begin() as c:
        db.put(c, 'employee', {'id':'employees/demo-1','source':'ReferenceManager','eligibleForAssignment':False,
               'employmentState':'DISMISSED'}, 'technical')
    call(client, 'POST', f'versions/{stable("plan")}/confirm-resources', {}, role='R-04', revision=1, expected=422)
    assert plan(client)['allocations'][0]['status'] == 'PROPOSED'


def test_real_mode_blocks_stale_cache_for_new_allocation(client, monkeypatch):
    refresh_cache(FixtureClient(), read_time='2026-01-01T00:00:00Z')
    monkeypatch.setenv('HR_MODE', 'real')
    with db.engine.begin() as c:
        with pytest.raises(HTTPException):
            validate_new_allocations(c, [{'id':'new','employeeId':'employees/1','date':'2026-10-05','status':'PROPOSED'}])


def dismissed_demo_employee():
    with db.engine.begin() as c:
        db.put(c, 'employee', {'id':'employees/demo-1','source':'ReferenceManager','eligibleForAssignment':False,
               'employmentState':'DISMISSED'}, 'technical')


def test_timeline_cannot_move_assignment_for_dismissed_employee(client):
    dismissed_demo_employee()
    before = plan(client)
    call(client, 'PATCH', f'versions/{stable("plan")}/timeline',
         {'itemId':stable('feature'),'start':'2026-10-06','finish':'2026-10-06'}, revision=before['revision'], expected=422)
    assert plan(client) == before


def test_submission_requires_current_hr_in_real_mode(client, monkeypatch):
    confirm(client)
    before = plan(client)
    monkeypatch.setenv('HR_MODE', 'real')
    call(client, 'POST', f'versions/{stable("plan")}/submit',
         {'reviewers':[{'subject':'demo-R-01','role':'FINAL_APPROVER','resourceScope':[]}]},
         revision=before['revision'], expected=422)
    assert plan(client) == before


def test_dismissal_after_approval_prevents_activation_without_changing_baseline(client):
    confirm(client)
    version = plan(client)
    version = call(client, 'POST', f'versions/{stable("plan")}/submit',
                   {'reviewers':[{'subject':'demo-R-01','role':'FINAL_APPROVER','resourceScope':[]}]}, revision=version['revision'])
    approved = call(client, 'POST', f'versions/{stable("plan")}/decisions',
                    {'reviewRound':version['reviewRound'],'contentRevision':version['contentRevision'],'decision':'APPROVE','comment':None},
                    role='R-01', revision=version['revision'])
    dismissed_demo_employee()
    project = call(client, 'GET', 'projects/'+PID)
    call(client, 'POST', f'versions/{stable("plan")}/activate', {'projectRevision':project['revision']},
         role='R-01', revision=approved['revision'], expected=422)
    assert plan(client) == approved
    assert call(client, 'GET', 'projects/'+PID) == project
    with db.engine.connect() as c:assert db.all_rows(c, 'publication') == []


def test_scenario_can_copy_historical_data_but_cannot_confirm_dismissed_employee(client):
    baseline = activate(client)
    dismissed_demo_employee()
    scenario = call(client, 'POST', f'projects/{PID}/versions',
                    {'baseVersionId':stable('plan'),'kind':'SCENARIO','name':'Заменить уволенного сотрудника'}, expected=201)
    assert scenario['allocations'][0]['status'] == 'PROPOSED'
    call(client, 'POST', f'versions/{scenario["id"]}/confirm-resources', {},
         role='R-04', revision=scenario['revision'], expected=422)
    assert plan(client) == baseline


def test_staging_defaults_to_real_hr_and_blocks_unread_employee(client, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'staging')
    monkeypatch.delenv('HR_MODE', raising=False)
    assert hr_required() is True
    with db.engine.begin() as c:
        assert cache_status(c)['required'] is True
        with pytest.raises(HTTPException):
            validate_new_allocations(c, [{'id':'new','employeeId':'employees/1','date':'2026-10-05','status':'PROPOSED'}])


@pytest.mark.parametrize('environment, mode', [('staging','demo'), ('production','demo'), ('development','unexpected')])
def test_invalid_hr_modes_are_rejected_before_app_start(monkeypatch, environment, mode):
    from fastapi.testclient import TestClient
    from server.app import app
    monkeypatch.setenv('APP_ENV', environment)
    monkeypatch.setenv('HR_MODE', mode)
    with pytest.raises(ReferenceManagerError):hr_required()
    with pytest.raises(ReferenceManagerError):
        with TestClient(app):pass
