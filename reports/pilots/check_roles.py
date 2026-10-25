"""Temporarily revoke/restore a synthetic pilot role through real Keycloak.

Only localhost reports-pilot/member1 is touched. Credentials/tokens remain in
memory. The original assignment is restored in finally, including on failure.
"""
import argparse
import hashlib
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from dotenv import dotenv_values
import jwt
from check_bi import CheckFailure, Session


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    artifact = Path(__file__).with_name('artifacts')/'role-verification.json'
    if args.record: artifact.write_text(json.dumps({'passed': False, 'state': 'running'})+'\n')
    values = dotenv_values(Path.home()/'secrets.env')
    if not all(values.get(key) for key in ('REPORTS_KC_ADMIN_PASSWORD', 'REPORTS_DEMO_MEMBER_PASSWORD')):
        raise CheckFailure('Missing local pilot credentials')
    token = None
    def authenticate():
        data = urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli',
                'username': 'pilot-admin', 'password': values['REPORTS_KC_ADMIN_PASSWORD']}).encode()
        with urllib.request.urlopen('http://localhost:8180/realms/master/protocol/openid-connect/token', data=data, timeout=15) as response:
            return json.load(response)['access_token']
    def request(path, payload=None, method=None):
        nonlocal token
        for attempt in range(2):
            if token is None: token = authenticate()
            data = None if payload is None else json.dumps(payload).encode()
            req = urllib.request.Request('http://localhost:8180/admin/realms/reports-pilot'+path,
                data=data, method=method, headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    raw = response.read(); return json.loads(raw) if raw else None
            except urllib.error.HTTPError as error:
                if error.code == 401 and attempt == 0: token = None; continue
                raise CheckFailure('Local Keycloak role check HTTP '+str(error.code)) from None
    client = request('/clients?clientId=reports')[0]['id']
    user = request('/users?username=member1&exact=true')[0]['id']
    path = '/users/'+user+'/role-mappings/clients/'+client
    original = request(path)
    roles = [role for role in original if role['name'] == 'reports-member']
    if not roles or any(role['name'] == 'reports-admin' for role in original):
        raise CheckFailure('Synthetic member1 has unexpected initial roles')
    try:
        print('Checking revoked role', file=sys.stderr, flush=True)
        request(path, roles, 'DELETE')
        Session('http://localhost:8088').login('member1', values['REPORTS_DEMO_MEMBER_PASSWORD'], expect_denied=True)
    finally:
        request(path, roles, 'POST')
    Session('http://localhost:8088').login('member1', values['REPORTS_DEMO_MEMBER_PASSWORD'])
    # A disposable public test client avoids persisting an additional secret.
    # Password grant is enabled only on this temporary, local test client.
    nonce = secrets.token_hex(8)
    client_name, key_name = 'reports-rotation-'+nonce, 'reports-rotation-key-'+nonce
    before_key = request('/keys')['active']['RS256']
    def access_token():
        body = urllib.parse.urlencode({'grant_type': 'password', 'client_id': client_name,
            'username': 'member1', 'password': values['REPORTS_DEMO_MEMBER_PASSWORD']}).encode()
        with urllib.request.urlopen('http://localhost:8180/realms/reports-pilot/protocol/openid-connect/token', data=body, timeout=15) as response:
            return json.load(response)['access_token']
    def verify_readers(access):
        print('Checking API signature and scope', file=sys.stderr, flush=True)
        req = urllib.request.Request('http://localhost:8081/pilot/reports/time-logs?group=employee',
                                     headers={'Authorization': 'Bearer '+access})
        with urllib.request.urlopen(req, timeout=15) as response: data = json.load(response)['data']
        if sum(row['hours'] for row in data) != 3.75 or any(row['dimension'] != user for row in data):
            raise CheckFailure('API scope differs after key rotation')
        query = {'measures': ['TimeLogs.hours'], 'dimensions': ['TimeLogs.userId']}
        print('Checking Cube signature and scope', file=sys.stderr, flush=True)
        url = 'http://localhost:4000/cubejs-api/v1/load?'+urllib.parse.urlencode({'query': json.dumps(query)})
        for _ in range(60):
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': access}), timeout=15) as response:
                result = json.load(response)
            if result.get('error') == 'Continue wait': time.sleep(1); continue
            if result.get('error'): raise CheckFailure('Cube rotation query failed')
            data = result['data']
            if sum(float(row['TimeLogs.hours']) for row in data) != 3.75 or any(row['TimeLogs.userId'] != user for row in data):
                raise CheckFailure('Cube scope differs after key rotation')
            return
        raise CheckFailure('Cube rotation query timed out')
    try:
        request('/clients', {'clientId': client_name, 'enabled': True, 'protocol': 'openid-connect',
            'publicClient': True, 'standardFlowEnabled': False, 'directAccessGrantsEnabled': True,
            'protocolMappers': [{'name': 'reports-audience', 'protocol': 'openid-connect',
                'protocolMapper': 'oidc-audience-mapper', 'config': {'included.client.audience': 'reports',
                'access.token.claim': 'true', 'id.token.claim': 'false'}}]})
        original_access = access_token()
        verify_readers(original_access)
        realm_id = request('')['id']
        request('/components', {'name': key_name, 'parentId': realm_id, 'providerId': 'rsa-generated',
            'providerType': 'org.keycloak.keys.KeyProvider',
            'config': {'priority': ['10000'], 'enabled': ['true'], 'active': ['true'],
                       'algorithm': ['RS256'], 'keySize': ['2048']}})
        rotated_access = access_token()
        print('Checking newly activated key', file=sys.stderr, flush=True)
        if jwt.get_unverified_header(rotated_access)['kid'] == before_key:
            raise CheckFailure('Keycloak did not activate the new signing key')
        # Readers have already cached the old JWKS above; the new kid must
        # trigger a refresh without restarting API or Cube.
        rotation_started = time.monotonic()
        while True:
            try:
                verify_readers(rotated_access)
                break
            except urllib.error.HTTPError as error:
                # Unknown-kid refresh is rate limited by Cube, not immediate.
                # Only a newly activated key may be retried, for a bounded time.
                if error.code not in {401, 403} or time.monotonic()-rotation_started > 15:
                    raise
                time.sleep(1)
        rotation_seconds = round(time.monotonic()-rotation_started, 3)
        Session('http://localhost:8088').login('member1', values['REPORTS_DEMO_MEMBER_PASSWORD'])
    finally:
        try:
            for component in request('/components?name='+key_name):
                if component['name'] == key_name: request('/components/'+component['id'], method='DELETE')
        finally:
            for temporary in request('/clients?clientId='+client_name):
                if temporary['clientId'] == client_name: request('/clients/'+temporary['id'], method='DELETE')
    if request('/keys')['active']['RS256'] != before_key:
        raise CheckFailure('Original signing key was not restored')
    sources = ['reports/pilots/check_roles.py', 'reports/pilots/check_bi.py',
               'reports/pilots/superset/superset_config.py', 'reports/pilots/superset/session_policy.py',
               'reports/pilots/api.py', 'reports/pilots/cube/cube.js']
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': True,
              'rotation_refresh_seconds': rotation_seconds,
              'checks': ['new_login_denied_after_role_revocation', 'original_role_restored', 'new_login_allowed_after_restore',
                         'api_jwks_refresh_after_key_rotation', 'cube_jwks_refresh_after_key_rotation',
                         'superset_login_with_rotated_key', 'original_signing_key_restored', 'temporary_client_removed'],
              'limitation': 'Existing sessions end at verified access-token expiry; instant back-channel revocation is not implemented',
              'source_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources}}
    if args.record: artifact.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result)); return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'error_type': type(error).__name__,
                          'check': str(error) if isinstance(error, CheckFailure) else
                          ('Local HTTP '+str(error.code) if isinstance(error, urllib.error.HTTPError) else 'Unexpected local dependency response')}))
        sys.exit(1)
