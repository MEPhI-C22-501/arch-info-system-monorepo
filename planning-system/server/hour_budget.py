"""Exact budget arithmetic over the saved project and one plan version."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from .domain import fail, hours

BUDGET_ROLES = {'R-01', 'R-02', 'R-03'}
MAX_BUDGET = Decimal('9999999999.99')


def budget_cents(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        fail(422, 'Бюджет должен быть числом или null')
    amount = Decimal(value)
    if not amount.is_finite() or not 0 <= amount <= MAX_BUDGET or amount.as_tuple().exponent < -2:
        fail(422, 'Бюджет от 0 до 9 999 999 999,99 с точностью до сотых')
    return int(amount * 100)


def public_budget(project):
    cents = project.get('hourBudgetCents')
    return None if cents is None else float(Decimal(cents) / 100)


def summary_versions(plans):
    active = {}
    latest = {}
    for version in plans:
        project_id = version['projectId']
        if version['status'] == 'ACTIVE':
            active[version['id']] = version
        if version['kind'] == 'PLAN':
            current = latest.get(project_id)
            if current is None or version['versionNumber'] > current['versionNumber']:
                latest[project_id] = version
    return active, latest


def summary_version(project, versions):
    active, latest = versions
    return active.get(project['activePlanVersionId']) or latest.get(project['id'])


def leaf_hours(plan):
    parents = {item['parentItemId'] for item in plan['items'] if item['parentItemId']}
    leaves = {item['id']: item for item in plan['items']
              if item['id'] not in parents and item['type'] != 'MILESTONE'}
    totals = defaultdict(Decimal)
    for demand in plan['demands']:
        item = leaves.get(demand['planItemId'])
        if item and item['start'] <= demand['periodStart'] <= demand['periodEnd'] <= item['finish']:
            totals[item['id']] += hours(demand['hours'])
    return totals


def recalculate_items(plan):
    totals = leaf_hours(plan)
    children = defaultdict(list)
    for item in plan['items']:
        if item['parentItemId']:
            children[item['parentItemId']].append(item['id'])

    def total(identifier):
        if identifier not in totals:
            totals[identifier] = sum((total(child) for child in children[identifier]), Decimal(0))
        return totals[identifier]

    for item in plan['items']:
        item['plannedHours'] = float(total(item['id']))


def comparison(project, plan):
    cents = project.get('hourBudgetCents')
    budget = None if cents is None else Decimal(cents) / 100
    planned = None if plan is None else sum(leaf_hours(plan).values(), Decimal(0))
    result = {
        'projectId': project['id'], 'projectRevision': project['revision'],
        'planVersionId': plan['id'] if plan else None,
        'planVersionNumber': plan['versionNumber'] if plan else None,
        'planVersionName': plan['name'] if plan else None,
        'planVersionStatus': plan['status'] if plan else None,
        'planVersionRevision': plan['revision'] if plan else None,
        'hourBudget': None if budget is None else float(budget),
        'plannedHours': None if planned is None else float(planned),
        'remainingHours': None, 'exceededHours': None, 'usagePercent': None,
        'status': 'NOT_SET' if budget is None else None,
    }
    if budget is not None and planned is not None:
        result.update(
            remainingHours=float(max(budget - planned, 0)),
            exceededHours=float(max(planned - budget, 0)),
            usagePercent=float((planned * 100 / budget).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
            if budget else None,
            status='EXCEEDED' if planned > budget else 'AT_LIMIT' if planned == budget else 'WITHIN_BUDGET',
        )
    return result
