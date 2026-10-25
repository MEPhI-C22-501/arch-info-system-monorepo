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
from product_store import remember


class KeycloakDirectory:
    def __init__(self,db):
        self.db=db;self.base='http://keycloak:8080';self.token=None;self.expires=0;self.client=None

    def request(self,path):
        if self.expires<=time.monotonic():
            data=urllib.parse.urlencode({'grant_type':'password','client_id':'admin-cli','username':'pilot-admin',
                 'password':os.environ['REPORTS_KC_ADMIN_PASSWORD']}).encode()
            with urllib.request.urlopen(self.base+'/realms/master/protocol/openid-connect/token',data=data,timeout=5) as response:
                value=json.load(response)
            self.token=value['access_token'];self.expires=time.monotonic()+value['expires_in']-10
        request=urllib.request.Request(self.base+'/admin/realms/reports-pilot'+path,headers={'Authorization':'Bearer '+self.token})
        with urllib.request.urlopen(request,timeout=5) as response: return json.load(response)

    def __call__(self,subject):
        from product_service import identity
        identity(subject)
        try:
            if self.client is None: self.client=self.request('/clients?clientId=reports')[0]['id']
            user=self.request('/users/'+subject)
            if not user.get('enabled'): raise PermissionError()
            mappings=self.request('/users/'+subject+'/role-mappings/clients/'+self.client+'/composite')
            names=[r['name'] for r in mappings]
            claims={'sub':subject,'exp':int(time.time())+60,'scope':'cost.read' if 'cost.read' in names else '',
                    'resource_access':{'reports':{'roles':names}}}
            remember(self.db,claims)
            return claims
        except (urllib.error.URLError,TimeoutError,KeyError,IndexError,ValueError):
            raise PermissionError('Current authorization unavailable') from None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stop.set())
    while not stop.is_set():
        db=Database(os.environ['REPORTS_DATABASE_URL'])
        try:
            resolver=KeycloakDirectory(db) if os.getenv('REPORTS_PRODUCT_DIRECTORY')=='keycloak' else None
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
