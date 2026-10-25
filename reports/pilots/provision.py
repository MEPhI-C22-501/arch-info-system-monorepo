"""Configure disposable local services; credentials are kept in memory only."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import psycopg
from psycopg import sql
from db import Database


def main():
    db = Database(os.environ['REPORTS_DATABASE_URL']); db.initialize(); db.close()
    with psycopg.connect(os.environ['REPORTS_DATABASE_URL'], autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname='superset'").fetchone():
            connection.execute('CREATE DATABASE superset OWNER reports_owner')
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='reports_cube'").fetchone():
            connection.execute(sql.SQL('CREATE ROLE reports_cube LOGIN PASSWORD {}').format(sql.Literal(os.environ['REPORTS_CUBE_DB_PASSWORD'])))
        connection.execute(sql.SQL('ALTER ROLE reports_cube PASSWORD {}').format(sql.Literal(os.environ['REPORTS_CUBE_DB_PASSWORD'])))
        connection.execute('GRANT USAGE ON SCHEMA dwh TO reports_cube')
        # Newly added raw HR/history tables must not become BI data sources.
        with connection.transaction():
            connection.execute('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA dwh FROM reports_cube')
            connection.execute('GRANT SELECT ON dwh.report_time_log TO reports_cube')
            from star import CUBE_VIEWS
            for view in CUBE_VIEWS:
                connection.execute(sql.SQL('GRANT SELECT ON dwh.{} TO reports_cube').format(sql.Identifier(view)))
            if connection.execute("SELECT has_table_privilege('reports_cube','dwh.fact_time_log','SELECT')").fetchone()[0]:
                raise RuntimeError('Cube must not read raw fact tables directly')
        connection.execute('CREATE SCHEMA IF NOT EXISTS reports_preaggregations AUTHORIZATION reports_cube')
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='reports_app'").fetchone():
            connection.execute(sql.SQL('CREATE ROLE reports_app LOGIN NOINHERIT PASSWORD {}').format(sql.Literal(os.environ['REPORTS_APP_DB_PASSWORD'])))
        connection.execute(sql.SQL('ALTER ROLE reports_app PASSWORD {}').format(sql.Literal(os.environ['REPORTS_APP_DB_PASSWORD'])))
        connection.execute('GRANT USAGE ON SCHEMA app,dwh,etl TO reports_app')
        connection.execute('GRANT SELECT ON ALL TABLES IN SCHEMA dwh,etl,app TO reports_app')
        connection.execute('GRANT INSERT,UPDATE,DELETE ON app.saved_view,app.export_job,app.subscription,app.delivery,app.notification TO reports_app')
        connection.execute('GRANT INSERT ON app.audit_log TO reports_app')
        connection.execute('GRANT INSERT ON etl.outbox TO reports_app')
        connection.execute('GRANT INSERT(subject,roles,token_scope,valid_until),UPDATE(roles,token_scope,valid_until) ON app.principal TO reports_app')
    base = 'http://keycloak:8080'
    token = None
    body = urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli', 'username': 'pilot-admin',
                                   'password': os.environ['REPORTS_KC_ADMIN_PASSWORD']}).encode()
    for _ in range(90):
        try:
            request = urllib.request.Request(base+'/realms/master/protocol/openid-connect/token', data=body)
            with urllib.request.urlopen(request, timeout=3) as response: token = json.load(response)['access_token']
            break
        except (urllib.error.URLError, TimeoutError): time.sleep(2)
    if token is None: raise RuntimeError('Keycloak not ready')

    def request(path, payload=None, method=None):
        headers = {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}
        req = urllib.request.Request(base+'/admin/realms'+path, data=None if payload is None else json.dumps(payload).encode(), headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            if error.code == 409: return None
            raise RuntimeError('Keycloak provisioning HTTP '+str(error.code)) from None

    realm = '/reports-pilot'
    request('', {'realm': 'reports-pilot', 'enabled': True, 'registrationAllowed': False})
    request(realm+'/clients', {'clientId': 'reports', 'enabled': True, 'bearerOnly': True})
    reports_id = request(realm+'/clients?clientId=reports')[0]['id']
    for role in ['reports-admin','reports-member','reports-analyst','reports-project-manager','reports-team-lead','reports-qa-lead']:
        request(realm+'/clients/'+reports_id+'/roles', {'name': role})
    client = {'clientId': 'reports-superset', 'enabled': True, 'publicClient': False, 'standardFlowEnabled': True,
              'secret': os.environ['REPORTS_SUPERSET_CLIENT_SECRET'],
              'redirectUris': ['http://localhost:8088/oauth-authorized/keycloak'], 'webOrigins': ['http://localhost:8088'],
              'protocolMappers': [{'name': 'reports-audience', 'protocol': 'openid-connect', 'protocolMapper': 'oidc-audience-mapper',
                                   'config': {'included.client.audience': 'reports', 'access.token.claim': 'true', 'id.token.claim': 'false'}}]}
    request(realm+'/clients', client)
    superset_id = request(realm+'/clients?clientId=reports-superset')[0]['id']
    request(realm+'/clients/'+superset_id, client, 'PUT')
    ui_client = {'clientId': 'reports-ui', 'enabled': True, 'publicClient': True,
                 'standardFlowEnabled': True, 'directAccessGrantsEnabled': False,
                 'attributes': {'pkce.code.challenge.method': 'S256', 'post.logout.redirect.uris': 'http://localhost:8081/ui/'},
                 'redirectUris': ['http://localhost:8081/ui/callback'], 'webOrigins': ['http://localhost:8081'],
                 'protocolMappers': client['protocolMappers']}
    request(realm+'/clients', ui_client)
    ui_id = request(realm+'/clients?clientId=reports-ui')[0]['id']
    request(realm+'/clients/'+ui_id, ui_client, 'PUT')
    subjects = {}
    roles = {r['name']: r for r in request(realm+'/clients/'+reports_id+'/roles')}
    for name in ['member1', 'member2', 'admin', 'noaccess']:
        request(realm+'/users', {'username': name, 'enabled': True, 'emailVerified': True,
                                'firstName': 'Synthetic', 'lastName': name, 'email': name+'@example.invalid'})
        user_id = request(realm+'/users?username='+name+'&exact=true')[0]['id']
        password_key = 'REPORTS_DEMO_ADMIN_PASSWORD' if name == 'admin' else 'REPORTS_DEMO_MEMBER_PASSWORD'
        request(realm+'/users/'+user_id+'/reset-password', {'type': 'password', 'temporary': False, 'value': os.environ[password_key]}, 'PUT')
        if name != 'noaccess':
            request(realm+'/users/'+user_id+'/role-mappings/clients/'+reports_id, [roles['reports-admin' if name == 'admin' else 'reports-member']])
        if name == 'admin':
            request(realm+'/users/'+user_id+'/role-mappings/clients/'+reports_id, [roles['reports-analyst']])
        subjects[name] = user_id
    # The synthetic Tracker fixture deliberately uses these returned IDs.
    # Never derive real identity bindings from HR names or coincident IDs.
    with psycopg.connect(os.environ['REPORTS_DATABASE_URL']) as connection:
        for name in ['member1', 'member2']:
            subject = subjects[name]
            connection.execute('''INSERT INTO app.subject_binding VALUES (%s,%s)
                ON CONFLICT(subject) DO UPDATE SET tracker_user_id=excluded.tracker_user_id''', (subject, subject))
    Path('/demo/subjects.json').write_text(json.dumps(subjects))  # Nonsecret IDs only.
    print('Local realm, role bindings and database initialized')


if __name__ == '__main__': main()
