"""Run the Reports-owned queue. Keycloak is read only; failures deny delivery."""
import argparse
import json
import os
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from db import Database
from product_service import tick


class KeycloakDirectory:
    def __init__(self):
        from urllib.parse import urlsplit
        issuer = os.environ['REPORTS_OIDC_ISSUER'].rstrip('/')
        self.issuer = os.environ.get('REPORTS_OIDC_INTERNAL_ISSUER', issuer).rstrip('/')
        self.base, marker, self.realm = self.issuer.rpartition('/realms/')
        url = urlsplit(self.base)
        local = os.getenv('REPORTS_LOCAL_OIDC') == '1' and url.hostname in {'keycloak', 'localhost', '127.0.0.1'}
        if not marker or '/' in self.realm or not self.realm or url.username or url.password or not url.hostname:
            raise ValueError('Invalid Keycloak issuer')
        if url.scheme != 'https' and not (local and url.scheme == 'http'):
            raise ValueError('Keycloak requires HTTPS')
        self.secret = os.environ['REPORTS_DIRECTORY_CLIENT_SECRET']
        self.token = None
        self.expires = 0
        self.client = None

    def request(self, path):
        if self.expires <= time.monotonic():
            data = urllib.parse.urlencode({
                'grant_type': 'client_credentials', 'client_id': 'reports-directory',
                'client_secret': self.secret,
            }).encode()
            with urllib.request.urlopen(self.issuer + '/protocol/openid-connect/token', data=data, timeout=5) as response:
                value = json.load(response)
            self.token = value['access_token']
            self.expires = time.monotonic() + value['expires_in'] - 10
        endpoint = self.base + '/admin/realms/' + urllib.parse.quote(self.realm, safe='') + path
        request = urllib.request.Request(endpoint, headers={'Authorization': 'Bearer ' + self.token})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def __call__(self, subject):
        from product_service import identity
        identity(subject)
        try:
            if self.client is None:
                clients = self.request('/clients?clientId=reports')
                self.client = next(client['id'] for client in clients if client['clientId'] == 'reports')
            user = self.request('/users/' + subject)
            if user.get('id') != subject or user.get('enabled') is not True or user.get('serviceAccountClientId'):
                raise PermissionError('Account is not active')
            mappings = self.request('/users/' + subject + '/role-mappings/clients/' + self.client + '/composite')
            names = sorted({role['name'] for role in mappings})
            return {'sub': subject, 'scope': 'cost.read' if 'cost.read' in names else '',
                    'resource_access': {'reports': {'roles': names}}}
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, TypeError, StopIteration):
            raise PermissionError('Current authorization unavailable') from None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stop.set())
    resolver = KeycloakDirectory()
    while not stop.is_set():
        db=Database(os.environ['REPORTS_DATABASE_URL'])
        try:
            result=tick(db,resolver)
            print(json.dumps({'worker':'reports-product','status':'OK',**result}),flush=True)
        except Exception:
            print(json.dumps({'worker':'reports-product','status':'DEPENDENCY_UNAVAILABLE'}),flush=True)
            if args.once: return 1
        finally: db.close()
        if args.once: return 0
        stop.wait(10)
    return 0


if __name__=='__main__': raise SystemExit(main())
