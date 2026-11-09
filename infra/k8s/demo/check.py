#!/usr/bin/env python3
"""Live checks: fail on any broken HTTP, database, Kafka, IAM or restart path."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = 'http://127.0.0.1:18080/'
TEAMS = ['planning-system', 'task-tracker', 'reference-manager', 'qa', 'reports']
KUBECTL = str(Path.home() / '.local/bin/kubectl')
if not Path(KUBECTL).exists():
    KUBECTL = 'kubectl'


def k(*args):
    return subprocess.check_output([KUBECTL, '--context=arch-demo', *args], text=True)


def request(team, path, body=None, bearer=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if bearer:
        headers['Authorization'] = 'Bearer ' + bearer
    req = urllib.request.Request(BASE + team + '/api/' + path, data=data,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def main():
    report = {'mockApplications': True, 'checks': []}
    secrets = dict(line.split('=', 1) for line in (Path(os.environ['DEMO_STATE']) / 'secrets.env').read_text().splitlines())
    form = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': 'example-caller',
                                   'client_secret': secrets['KC_EXAMPLE_CALLER_SECRET']}).encode()
    with urllib.request.urlopen('http://127.0.0.1:18081/realms/arch-info-system/protocol/openid-connect/token',
                                data=form, timeout=30) as response:
        bearer = json.load(response)['access_token']
    for team in TEAMS:
        info = request(team, 'info')
        assert info['team'] == team and info['database'] == 'ok', info
        created = request(team, 'records', {'message': 'check-' + str(uuid.uuid4())})
        assert any(row['id'] == created['id'] for row in request(team, 'records')['rows'])
        services = request(team, 'checks', {})
        assert services['postgres'] == 'ok' and services['s3']['status'] == 'ok', services
        assert services['s3']['foreignBucket'] == 'denied', services
        assert services['keycloak']['status'] == 'ok' and services['otlp'] == 'accepted', services
        peer = request(team, 'peer')
        assert peer['response']['team'] != team and peer['response']['database'] == 'ok'
        assert request(team, 'protected', bearer=bearer)['subject']
        for invalid in [None, 'invalid-token']:
            try:
                request(team, 'protected', bearer=invalid)
            except urllib.error.HTTPError as error:
                assert error.code == 401
            else:
                raise AssertionError('Unauthenticated request accepted')
        report['checks'].append({'team': team, 'http': 'ok', 'postgres': 'ok',
            's3': 'ok', 'keycloak': 'ok', 'unauthenticated': 401, 'otlp': 'accepted', 'peer': 'ok'})
        print(f'PASS {team}: HTTP, PostgreSQL, S3, Keycloak, 401, OTLP, cross-namespace HTTP', flush=True)
    event = request('task-tracker', 'events', {'message': 'Kafka live check'})
    received = request('reports', 'consume', {'eventId': event['eventId']})
    assert received['event']['eventId'] == event['eventId'] and received['consumer'] == 'reports'
    print('PASS Kafka: Task Tracker mock -> SASL_SSL broker -> Reports mock', flush=True)
    report['kafka'] = received
    # Exercise the exact CronJob command once without waiting five minutes.
    job = 'demo-etl-check-' + uuid.uuid4().hex[:8]
    k('-n', 'arch-reports', 'create', 'job', job, '--from=cronjob/demo-etl')
    k('-n', 'arch-reports', 'wait', '--for=condition=complete', 'job/' + job, '--timeout=120s')
    etl = json.loads(k('-n', 'arch-reports', 'logs', 'job/' + job).strip())
    assert etl['loaded'] > 0
    assert any(row['message'].startswith('ETL from tracker: ') for row in request('reports', 'records')['rows'])
    report['etl'] = etl
    print('PASS ETL Job: Task Tracker REST -> Reports PostgreSQL', flush=True)
    k('-n', 'arch-reports', 'delete', 'job', job)
    recovery = k('-n', 'arch-infra', 'exec', 'reports-db-replica-0', '--',
                 'psql', '-U', 'reports', '-d', 'reports', '-tAc', 'SELECT pg_is_in_recovery()').strip()
    streaming = k('-n', 'arch-infra', 'exec', 'reports-db-0', '--',
                  'psql', '-U', 'reports', '-d', 'reports', '-tAc',
                  "SELECT count(*) FROM pg_stat_replication WHERE state='streaming'").strip()
    assert recovery == 't' and int(streaming) > 0
    report['readReplica'] = {'recovery': True, 'streaming': True}
    print('PASS Reports replica: standby recovery + streaming replication', flush=True)
    if '--restart' in sys.argv:
        before = request('task-tracker', 'info')['pod']
        marker = request('task-tracker', 'records', {'message': 'must survive pod replacement'})
        k('-n', 'arch-task-tracker', 'delete', 'pod', before, '--wait=true')
        k('-n', 'arch-task-tracker', 'rollout', 'status', 'deployment/backend', '--timeout=180s')
        for attempt in range(45):
            try:
                after = request('task-tracker', 'info')['pod']
                if after != before:
                    break
            except urllib.error.URLError:
                pass
            time.sleep(1)
        else:
            raise AssertionError('Backend was not replaced')
        assert after != before
        assert any(row['id'] == marker['id'] for row in request('task-tracker', 'records')['rows'])
        # Replace PostgreSQL too: the same PVC must retain the marker.
        k('-n', 'arch-task-tracker', 'delete', 'pod', 'postgres-0', '--wait=true')
        k('-n', 'arch-task-tracker', 'rollout', 'status', 'statefulset/postgres', '--timeout=180s')
        for attempt in range(30):
            try:
                assert any(row['id'] == marker['id'] for row in request('task-tracker', 'records')['rows'])
                break
            except (urllib.error.URLError, AssertionError):
                time.sleep(1)
        else:
            raise AssertionError('PostgreSQL PVC persistence check failed')
        report['replacement'] = {'before': before, 'after': after, 'recordRetained': marker['id'], 'postgresPVC': 'ok'}
        print('PASS Kubernetes: backend replaced, PostgreSQL pod replaced, database row retained', flush=True)
    state = Path(os.environ['DEMO_STATE'])
    state.mkdir(parents=True, exist_ok=True)
    (state / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('All live checks passed. Evidence:', state / 'verification.json')


if __name__ == '__main__':
    main()
