from uuid import uuid4

import pytest

from server import storage as db
from server.auth import DEMO_PROJECT as PROJECT
from server.seed import stable
from test_application import activate, call, draft, plan


def set_budget(client, value, revision, role='R-01', expected=200, reason='Проверка лимита'):
    return call(client, 'PATCH', f'projects/{PROJECT}',
                {'hourBudget': value, 'hourBudgetReason': reason},
                role=role, revision=revision, expected=expected)


def test_budget_is_exact_and_compares_selected_plan_only(client):
    current = call(client, 'GET', f'projects/{PROJECT}')
    assert current['hourBudget'] is None
    assert current['hourBudgetComparison']['status'] == 'NOT_SET'
    project = set_budget(client, 6, current['revision'])
    summary = project['hourBudgetComparison']
    assert (summary['status'], summary['plannedHours'], summary['usagePercent']) == ('AT_LIMIT', 6, 100)

    variant = call(client, 'POST', f'projects/{PROJECT}/versions',
                   {'baseVersionId': stable('plan'), 'kind': 'SCENARIO', 'name': 'Вариант'},
                   expected=201)
    body = draft(variant)
    body['demands'][0]['hours'] = 8.29
    for item in body['items']:
        if item['type'] != 'MILESTONE':
            item['plannedHours'] = 999
    saved = call(client, 'PUT', f'versions/{variant["id"]}/draft', body, revision=variant['revision'])
    assert {x['plannedHours'] for x in saved['items']} == {0, 8.29}
    explicit = call(client, 'GET', f'versions/{variant["id"]}/hour-budget')
    assert explicit['plannedHours'] == 8.29
    assert explicit['exceededHours'] == 2.29
    assert call(client, 'GET', 'project-cards')['items'][0]['hourBudgetComparison'] == summary

    set_budget(client, 0.29, project['revision'])
    latest = call(client, 'GET', f'projects/{PROJECT}')
    assert latest['hourBudget'] == 0.29
    assert latest['hourBudgetComparison']['exceededHours'] == 5.71


def test_budget_permissions_conflict_unset_and_audit(client):
    baseline = activate(client)
    current = call(client, 'GET', f'projects/{PROJECT}')
    set_budget(client, 0, current['revision'], 'R-02', 403)
    set_budget(client, 0, current['revision'], 'R-06', 403)
    set_budget(client, 0, current['revision'], expected=422, reason=' ')
    project = set_budget(client, 0, current['revision'])
    assert project['hourBudgetComparison']['status'] == 'EXCEEDED'
    assert project['hourBudgetComparison']['exceededHours'] == 6
    assert project['hourBudgetComparison']['usagePercent'] is None
    set_budget(client, 10, current['revision'], expected=412)
    final = set_budget(client, None, project['revision'])
    assert final['hourBudgetComparison']['remainingHours'] is None
    assert final['hourBudgetComparison']['plannedHours'] == 6
    assert plan(client) == baseline
    with db.engine.connect() as connection:
        entries = connection.execute(db.audit.select().where(
            db.audit.c.action == 'ProjectHourBudgetChanged'
        ).order_by(db.audit.c.occurred_at)).mappings().all()
    assert [entry['details']['current'] for entry in entries] == [0, None]
    assert [entry['subject'] for entry in entries] == ['demo-R-01', 'demo-R-01']


@pytest.mark.parametrize('raw', ['-1', 'true', '"8"', '1.005', 'NaN', 'Infinity', '10000000000'])
def test_rejects_invalid_hour_budgets(client, raw):
    response = client.patch(
        f'/api/v1/projects/{PROJECT}', content='{"hourBudget":' + raw + ',"hourBudgetReason":"test"}',
        headers={'Authorization':'Bearer demo-R-01','If-Match':'"1"','Idempotency-Key':str(uuid4())},
    )
    assert response.status_code == 422
