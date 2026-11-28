"""ETL against the neighbours' real services started locally from their own compose files.

Each service runs alone: the check proves that the Reports adapters read the
owner's live API, validate it against the owner's contract and load it twice
without double counting. It does not prove cross-system consistency: every
service has its own demo data. Service credentials come only from
~/secrets.env; tokens stay in memory and nothing secret is printed or recorded.
"""
import argparse
import hashlib
import json
import sys
import tempfile
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from dotenv import dotenv_values
from adapters import Client, Rejected
from contracts import tracker_validator
from db import Database
from etl import load, planning_extract, tracker_extract
from report_engine import AN, Engine

SERVICES = {'tracker': 'task-tracker/compose.yaml, its own Keycloak realm arch-info-system',
            'planning': 'planning-system/compose.yaml, AUTH_MODE=demo, DEMO_SEED=true',
            'reference': 'reference-manager/deployments/docker-compose.yaml with its seed, its own Keycloak realm arch-info-system',
            'qa': 'qa/compose.yaml, AUTH_MODE=demo with its seed'}
CONTRACTS = {'tracker': 'api/openapi/task-tracker/v1/openapi.yaml',
             'planning': 'api/openapi/planning-system/v1/openapi.json',
             'reference': 'api/openapi/reference-manager/{employee,org_unit,position,project_role,grade,profile}/openapi.yaml',
             'qa': 'api/openapi/qa/v1/openapi.yaml'}
REFERENCE_SCHEMAS = {'employees': ('employee', 'ExpandedEmployee'), 'org_units': ('org_unit', 'ExpandedOrgUnit'),
                     'positions': ('position', 'ExpandedPosition'), 'project_roles': ('project_role', 'ExpandedProjectRole'),
                     'grades': ('grade', 'ExpandedGrade'), 'profiles': ('profile', 'Profile')}


def client_token(issuer, client_id, secret):
    body = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': client_id,
                                   'client_secret': secret}).encode()
    with urllib.request.urlopen(issuer+'/protocol/openid-connect/token', data=body, timeout=15) as response:
        return json.load(response)['access_token']


def status_without_token(url, method='GET'):
    request = urllib.request.Request(url, method=method, data=b'{}' if method == 'POST' else None,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response: return response.status
    except urllib.error.HTTPError as error: return error.code


def load_twice(db, source, extract, scope=None):
    results = []
    for run in (1, 2):
        try: result = load(db, source, extract, scope=scope)
        except Rejected as error: raise SystemExit(f'{source} load {run} rejected: {error}') from None
        if result['status'] != 'LOADED': raise SystemExit(f'{source} load {run}: {result}')
        results.append(result)
    if results[0]['rows'] != results[1]['rows']: raise SystemExit(f'{source} repeated load changed the row count')
    counts = {entity: n for entity, n in db.execute(
        'SELECT entity, COUNT(*) FROM dwh.source_record WHERE source=? GROUP BY entity ORDER BY entity', (source,))}
    drift = db.execute("SELECT COUNT(*) FROM etl.reconciliation WHERE source=? AND status LIKE '%DRIFT'", (source,)).fetchone()[0]
    if drift: raise SystemExit(f'{source} reconciliation found drift')
    return results, counts


def tracker(args, values, db, checks):
    secret = values.get('REPORTS_TRACKER_CLIENT_SECRET')
    if not secret: raise SystemExit('Missing REPORTS_TRACKER_CLIENT_SECRET in ~/secrets.env')
    denied = status_without_token(args.tracker_url+'/api/v1/reports/work-items?page=1&pageSize=1')
    if denied not in {401, 403}: raise SystemExit(f'Tracker answered {denied} without a token')
    checks.append({'source': 'tracker', 'check': 'no_token_denied', 'http_status': denied, 'passed': True})
    client = Client(args.tracker_url, client_token(args.tracker_issuer, 'reports-client', secret), allow_http=True)
    try:
        results, counts = load_twice(db, 'tracker', lambda: tracker_extract(client))
    except SystemExit as stop:
        # The adapter keeps the owner's contract strictly; record where the live service departs from it.
        checks.append({'source': 'tracker', 'check': 'live_api_matches_owner_contract', 'passed': False,
                       'rejected': str(stop), 'findings': tracker_findings(client)})
        return
    hours = db.execute('SELECT COALESCE(SUM(hours_cents),0) FROM dwh.fact_time_log').fetchone()[0]/100
    analyst = {'sub': 'live-check-analyst', 'exp': 0, 'scope': '', 'resource_access': {'reports': {'roles': [AN]}}}
    period = {'periodFrom': date.today().replace(day=1).isoformat(), 'periodTo': date.today().isoformat()}
    report = Engine(db).query('R-01', analyst, {'params': period, 'slice': ['project']})
    checks.append({'source': 'tracker', 'check': 'live_etl_twice_without_double_count', 'records': counts,
                   'rows_per_load': [r['rows'] for r in results], 'time_log_hours': hours,
                   'r01_hours_current_month': report['totals']['M-01'], 'passed': True})


def tracker_findings(client):
    findings = []
    for resource, schema in [('work-items', 'ReportWorkItem'), ('time-logs', 'TimeLog'), ('iterations', 'ReportIteration'), ('history', 'History')]:
        page = client.request('/api/v1/reports/'+resource, {'page': 1, 'pageSize': 100})
        missing = [field for field in ['items', 'page', 'pageSize', 'total', 'totalPages'] if field not in page]
        if missing: findings.append({'resource': resource, 'page_fields_missing': missing})
        errors = sorted({('/'.join(map(str, e.absolute_path)) or 'item')+': '+e.message
                         for item in page.get('items', []) for e in tracker_validator(schema).iter_errors(item)})
        if errors: findings.append({'resource': resource, 'schema': schema, 'item_errors': errors})
    return findings


def reference_validator(spec, schema):
    """An OpenAPI 3.0 schema of Reference Manager as JSON Schema: nullable becomes a null type."""
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
    def convert(value):
        if isinstance(value, list): return [convert(v) for v in value]
        if not isinstance(value, dict): return value
        result = {k: convert(v) for k, v in value.items() if k != 'nullable'}
        if value.get('nullable') and 'type' in result: result['type'] = [result['type'], 'null']
        if value.get('nullable') and '$ref' in result: result = {'anyOf': [{'$ref': result.pop('$ref')}, {'type': 'null'}], **result}
        return result
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root/f'api/openapi/reference-manager/{spec}/openapi.yaml').read_text(encoding='utf-8'))
    return Draft202012Validator(convert({'$ref': '#/components/schemas/'+schema, 'components': document['components']}),
                                format_checker=FormatChecker())


def reference(args, values, db, checks):
    # Reference Manager's local stand: its own realm with the consumers' service clients (#201).
    secret = values.get('REPORTS_REFERENCE_CLIENT_SECRET')
    if not secret: raise SystemExit('Missing REPORTS_REFERENCE_CLIENT_SECRET in ~/secrets.env')
    denied = status_without_token(args.reference_url+'/v1/employees/?pageSize=1')
    if denied not in {401, 403}: raise SystemExit(f'Reference Manager answered {denied} without a token')
    checks.append({'source': 'reference', 'check': 'no_token_denied', 'http_status': denied, 'passed': True})
    from etl import catalog_extract
    client = Client(args.reference_url, client_token(args.reference_issuer, 'reports-client', secret), allow_http=True)
    seen = {}

    def extract():
        entities, started, data_as_of, facts = catalog_extract(client, 'reference')
        seen.update(entities)
        return entities, started, data_as_of, facts
    try:
        results, counts = load_twice(db, 'reference', extract)
    except SystemExit as stop:
        checks.append({'source': 'reference', 'check': 'live_api_matches_owner_contract', 'passed': False, 'rejected': str(stop)})
        return
    errors = {}
    for entity, (spec, schema) in REFERENCE_SCHEMAS.items():
        validator = reference_validator(spec, schema)
        found = sorted({('/'.join(map(str, e.absolute_path)) or 'item')+': '+e.message
                        for row in seen.get(entity, []) for e in validator.iter_errors({k: v for k, v in row.items() if k not in {'profile_display_name'} and not (entity == 'profiles' and k == 'id')})})
        if found: errors[entity] = found[:10]
    employees = seen.get('employees', [])
    active = dict(db.execute("SELECT employee_id,is_active FROM dwh.dim_employee WHERE is_current=1 AND employee_key<>-1").fetchall())
    dismissed = [str(e['id']) for e in employees if e.get('employment_state') == 'DISMISSED']
    roles = {str(r.get('code')) for r in seen.get('project_roles', [])}
    linked = db.execute("SELECT COUNT(*) FROM dwh.dim_project_role WHERE project_role_key<>-1 AND role_code IN (%s)"
                        % ','.join('?'*len(roles)), tuple(roles)).fetchone()[0] if roles else 0
    checks.append({'source': 'reference', 'check': 'live_catalog_twice_without_double_count', 'records': counts,
                   'rows_per_load': [r['rows'] for r in results], 'contract_errors': errors,
                   'deleted_employees_included': sum(1 for e in employees if e.get('is_deleted')),
                   'dismissed_employees': len(dismissed), 'dismissed_marked_inactive': all(active.get(d) == 0 for d in dismissed),
                   'project_roles_keyed_by_code': linked == len(roles),
                   'passed': not errors and all(active.get(d) == 0 for d in dismissed) and linked == len(roles)})


def qa(args, db, checks):
    # QA's development mode issues role tokens "demo-<role>"; qa-reports-reader is the Reports role. Not a secret.
    denied = status_without_token(args.qa_url+'/api/v1/reports/defects?page=1&pageSize=1')
    if denied not in {401, 403}: raise SystemExit(f'QA answered {denied} without a token')
    checks.append({'source': 'qa', 'check': 'no_token_denied', 'http_status': denied, 'passed': True})
    other = urllib.request.Request(args.qa_url+'/api/v1/reports/defects?page=1&pageSize=1', headers={'Authorization': 'Bearer demo-qa-tester'})
    try:
        with urllib.request.urlopen(other, timeout=15) as response: wrong_role = response.status
    except urllib.error.HTTPError as error: wrong_role = error.code
    checks.append({'source': 'qa', 'check': 'other_role_denied', 'http_status': wrong_role, 'passed': wrong_role == 403})
    from etl import catalog_extract
    client = Client(args.qa_url, 'demo-qa-reports-reader', allow_http=True)
    try:
        results, counts = load_twice(db, 'qa', lambda: catalog_extract(client, 'qa'))
    except SystemExit as stop:
        checks.append({'source': 'qa', 'check': 'live_api_matches_owner_contract', 'passed': False, 'rejected': str(stop)})
        return
    analyst = {'sub': 'live-check-analyst', 'exp': 0, 'scope': '', 'resource_access': {'reports': {'roles': [AN]}}}
    year = {'periodFrom': date.today().replace(month=1, day=1).isoformat(), 'periodTo': date.today().isoformat()}
    r07 = Engine(db).query('R-07', analyst, {'params': year, 'slice': ['project']})['totals']
    checks.append({'source': 'qa', 'check': 'live_export_twice_without_double_count', 'records': counts,
                   'rows_per_load': [r['rows'] for r in results],
                   'r07_this_year': {k: r07.get(k) for k in ['M-14', 'M-15', 'passed', 'failed', 'blocked', 'skipped']}, 'passed': True})


def activate_demo_plan(url):
    """Walk Planning's demo plan DRAFT -> ON_REVIEW -> APPROVED -> ACTIVE with its demo roles.

    Only ACTIVE, APPROVED and SUPERSEDED plans are exported to Reports; the seed
    leaves the plan in DRAFT. Every call goes through Planning's own API and rules.
    """
    version_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'planning-demo:plan'))

    def call(method, path, role, body=None, etag=None):
        headers = {'Authorization': 'Bearer demo-'+role, 'Content-Type': 'application/json', 'Idempotency-Key': str(uuid.uuid4())}
        if etag: headers['If-Match'] = etag
        request = urllib.request.Request(url+path, method=method, headers=headers,
                                         data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.load(response), response.headers.get('ETag')
        except urllib.error.HTTPError as error:
            message = json.loads(error.read() or b'{}').get('message', '')
            raise SystemExit(f'Planning {method} {path.rsplit("/", 1)[-1]} as {role}: HTTP {error.code} {message}') from None
    path = '/api/v1/versions/'+version_id
    version, etag = call('GET', path, 'R-03')
    steps = [version['status']]
    if version['status'] == 'DRAFT':
        # The seed allocates more hours than the employee has that day. Planning requires each
        # allocation to fit the day's availability and the demand period, and the allocations to
        # cover each demand exactly. As the resource planner (R-02) cut over-allocations and add
        # the deficit from other employees free inside the demand period; R-04 then confirms.
        free = {(r['data']['employeeId'], r['data']['date']): r['data']['availableHours']
                for r in call('GET', '/api/v1/availability', 'R-04')[0] if r['data']['status'] == 'CONFIRMED'}
        allocations = []
        for x in version['allocations']:
            hours = min(x['hours'], free.get((x['employeeId'], x['date']), 0))
            free[(x['employeeId'], x['date'])] = free.get((x['employeeId'], x['date']), 0)-hours
            allocations.append(dict(x, hours=hours))
        for demand in version['demands']:
            deficit = demand['hours']-sum(x['hours'] for x in allocations if x['demandId'] == demand['id'])
            for (employee, day), available in sorted(free.items()):
                if deficit <= 0: break
                if available > 0 and demand['periodStart'] <= day <= demand['periodEnd']:
                    hours = min(deficit, available); deficit -= hours; free[(employee, day)] -= hours
                    allocations.append({'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'reports-live:{demand["id"]}:{employee}:{day}')),
                                        'demandId': demand['id'], 'employeeId': employee, 'date': day,
                                        'hours': hours, 'status': 'PROPOSED'})
        if allocations != version['allocations']:
            draft = {k: version[k] for k in ['name', 'planningMode', 'horizonStart', 'horizonEnd', 'items', 'dependencies', 'demands']}
            etag = call('PUT', path+'/draft', 'R-02', dict(draft, allocations=allocations), etag)[1]
        call('POST', path+'/confirm-resources', 'R-04', {}, etag)
        version, etag = call('GET', path, 'R-03')
        reviewers = [{'subject': 'demo-R-01', 'role': 'FINAL_APPROVER', 'resourceScope': []}]
        version, etag = call('POST', path+'/submit', 'R-03', {'reviewers': reviewers}, etag)
        steps.append(version['status'])
    if version['status'] == 'ON_REVIEW':
        decision = {'reviewRound': version['reviewRound'], 'contentRevision': version['contentRevision'],
                    'decision': 'APPROVE', 'comment': 'Reports live ETL check'}
        version, etag = call('POST', path+'/decisions', 'R-01', decision, etag)
        steps.append(version['status'])
    if version['status'] == 'APPROVED':
        project, _ = call('GET', '/api/v1/projects/'+version['projectId'], 'R-01')
        version, etag = call('POST', path+'/activate', 'R-01', {'projectRevision': project['revision']}, etag)
        steps.append(version['status'])
    if version['status'] != 'ACTIVE': raise SystemExit('Planning demo plan is not ACTIVE: '+version['status'])
    return steps


def planning(args, db, checks):
    # Planning's development mode issues fixed role tokens: "demo-S-06" is the
    # export role with reports.export on the demo portfolio. It is not a secret.
    denied = status_without_token(args.planning_url+'/api/v1/exports', 'POST')
    if denied not in {401, 403}: raise SystemExit(f'Planning answered {denied} without a token')
    checks.append({'source': 'planning', 'check': 'no_token_denied', 'http_status': denied, 'passed': True})
    if args.planning_activate_demo_plan:
        checks.append({'source': 'planning', 'check': 'demo_plan_activated_through_planning_api',
                       'statuses': activate_demo_plan(args.planning_url), 'passed': True})
    client = Client(args.planning_url, 'demo-S-06', allow_http=True)
    # A fresh Idempotency-Key slot per run asks for a new batch (the hourly slot would replay an
    # older one); both loads of the run use it, so the second load replays the same batch.
    slot = 'live-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    planning_batches = []

    def extract():
        entities, batch_id, data_as_of, facts = planning_extract(client, args.planning_portfolio, slot)
        planning_batches.append(batch_id)
        return entities, batch_id, data_as_of, facts
    results, counts = load_twice(db, 'planning', extract, scope=args.planning_portfolio)
    batches = set(planning_batches)
    checks.append({'source': 'planning', 'check': 'live_export_batch_twice_without_double_count', 'records': counts,
                   'rows_per_load': [r['rows'] for r in results], 'same_batch_replayed': len(batches) == 1, 'passed': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['tracker', 'planning', 'reference', 'qa'], action='append',
                        help='Services to check; locally they share port 8080, so run them one at a time')
    parser.add_argument('--tracker-url', default='http://localhost:8080')
    parser.add_argument('--tracker-issuer', default='http://localhost:8081/realms/arch-info-system')
    parser.add_argument('--qa-url', default='http://localhost:8090')
    parser.add_argument('--reference-url', default='http://localhost:8083')
    parser.add_argument('--reference-issuer', default='http://localhost:8183/realms/arch-info-system')
    parser.add_argument('--planning-url', default='http://localhost:8080')
    parser.add_argument('--planning-portfolio', default='10000000-0000-4000-8000-000000000001')
    parser.add_argument('--planning-activate-demo-plan', action='store_true',
                        help='Local demo stand only: approve and activate the seeded plan through the Planning API first')
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    sources = args.source or ['tracker']
    values = dotenv_values(Path.home()/'secrets.env')
    checks = []
    with tempfile.TemporaryDirectory(prefix='reports-live-') as tmp:
        db = Database('sqlite:'+str(Path(tmp)/'live.sqlite')); db.initialize()
        try:
            for source in sources:
                {'tracker': lambda: tracker(args, values, db, checks), 'planning': lambda: planning(args, db, checks),
                 'reference': lambda: reference(args, values, db, checks), 'qa': lambda: qa(args, db, checks)}[source]()
        finally: db.close()
    target = Path(__file__).with_name('artifacts')/'live-sources-verification.json'
    # Each run replaces the records of its own sources, so services can be checked one after another.
    previous = json.loads(target.read_text(encoding='utf-8')) if args.record and target.is_file() else {}
    checked = sorted({*previous.get('sources', []), *sources})
    names = ['check_live_sources.py', 'adapters.py', 'etl.py', 'contracts.py', 'star.py']
    all_checks = [c for c in previous.get('checks', []) if c['source'] not in sources]+checks
    output = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'sources': checked,
              'passed': all(c['passed'] for c in all_checks), 'checks': all_checks,
              'services': {s: SERVICES[s] for s in checked}, 'contracts': {s: CONTRACTS[s] for s in checked},
              'not_checked': {s: reason for s, reason in {'qa': 'not started locally in this run', 'reference': 'not started locally in this run'}.items() if s not in checked},
              'cross_system_consistency': False,
              'source_sha256': {f'reports/pilots/{n}': hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in names}}
    if args.record: target.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False))
    return 0 if all(c['passed'] for c in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
