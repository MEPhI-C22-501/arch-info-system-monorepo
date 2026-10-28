"""Real PKCE -> Keycloak -> Reports API -> durable worker -> scoped files.

Only synthetic local reports-pilot users/objects are touched. Member2's role
is restored in finally; test subscriptions are completed. No codes or tokens
are printed, persisted in artifacts or passed on the command line.
"""
import argparse
import hashlib
import http.cookiejar
import io
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from dotenv import dotenv_values
from check_bi import CheckFailure,LoginForm,LocalPilotCookiePolicy

BASE='http://localhost:8081/api/v1/'
ISSUER='http://localhost:8180/realms/reports-pilot'
QUERY={'params':{'periodFrom':'2026-10-01','periodTo':'2026-10-31'},'slice':['project']}


class Callback(urllib.request.HTTPRedirectHandler):
    def __init__(self): self.url=None
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parsed=urllib.parse.urlsplit(newurl)
        if parsed.hostname=='localhost' and parsed.port==8081 and parsed.path=='/ui/callback':
            self.url=newurl;return None
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def login(name,password):
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    import base64
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    callback=Callback();opener=urllib.request.build_opener(callback,urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar(LocalPilotCookiePolicy())))
    auth=ISSUER+'/protocol/openid-connect/auth?'+urllib.parse.urlencode({'client_id':'reports-ui','redirect_uri':'http://localhost:8081/ui/callback',
        'response_type':'code','scope':'openid profile email','state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
    with opener.open(auth,timeout=15) as response: form=LoginForm();form.feed(response.read().decode())
    if not form.action or not form.action.startswith('http://localhost:8180/'): raise CheckFailure('Unexpected PKCE login form')
    try:
        with opener.open(form.action,data=urllib.parse.urlencode(dict(form.fields,username=name,password=password)).encode(),timeout=15) as response: response.read()
    except urllib.error.HTTPError as error:
        if error.code!=302 or not callback.url: raise CheckFailure('PKCE callback missing') from None
    query=urllib.parse.parse_qs(urllib.parse.urlsplit(callback.url or '').query)
    if query.get('state')!=[state] or not query.get('code'): raise CheckFailure('Invalid PKCE callback state')
    body=urllib.parse.urlencode({'grant_type':'authorization_code','client_id':'reports-ui','redirect_uri':'http://localhost:8081/ui/callback',
        'code':query['code'][0],'code_verifier':verifier}).encode()
    with urllib.request.urlopen(ISSUER+'/protocol/openid-connect/token',data=body,timeout=15) as response: return json.load(response)['access_token']


def call(token,path,method='GET',body=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,method=method,
                              headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try: response=urllib.request.urlopen(req,timeout=20)
    except urllib.error.HTTPError as error: response=error
    with response:
        raw=response.read()
        return response.status,(None if response.status==204 else json.loads(raw) if 'json' in response.headers.get('Content-Type','') else raw)


def expect(status,actual):
    if status!=actual[0]: raise CheckFailure('Reports API status '+str(actual[0])+' expected '+str(status))
    return actual[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',action='store_true');args=parser.parse_args()
    directory=Path(__file__).resolve().parent;artifact=directory/'artifacts/product-verification.json'
    if args.record: artifact.write_text(json.dumps({'passed':False,'state':'running'})+'\n')
    values=dotenv_values(Path.home()/'secrets.env');checks=[]
    print('Checking real public-client PKCE login',flush=True)
    tokens={name:login(name,values['REPORTS_DEMO_ADMIN_PASSWORD' if name=='admin' else 'REPORTS_DEMO_MEMBER_PASSWORD']) for name in ['admin','member1','member2']}
    checks.append('real_pkce_three_users')
    admin_token=None
    def kc(path,payload=None,method=None):
        nonlocal admin_token
        for attempt in range(2):
            if admin_token is None:
                data=urllib.parse.urlencode({'grant_type':'password','client_id':'admin-cli','username':'pilot-admin','password':values['REPORTS_KC_ADMIN_PASSWORD']}).encode()
                with urllib.request.urlopen('http://localhost:8180/realms/master/protocol/openid-connect/token',data=data,timeout=15) as response: admin_token=json.load(response)['access_token']
            req=urllib.request.Request('http://localhost:8180/admin/realms/reports-pilot'+path,data=json.dumps(payload).encode() if payload is not None else None,method=method,
                                       headers={'Authorization':'Bearer '+admin_token,'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=15) as response:
                    raw=response.read();return json.loads(raw) if raw else None
            except urllib.error.HTTPError as error:
                if error.code==401 and attempt==0: admin_token=None;continue
                raise CheckFailure('Local Keycloak operation failed') from None
    client=kc('/clients?clientId=reports')[0]['id']
    members={name:kc('/users?username='+name+'&exact=true')[0]['id'] for name in ['member1','member2']}
    member_path='/users/'+members['member2']+'/role-mappings/clients/'+client
    original=kc(member_path);member_role=[r for r in original if r['name']=='reports-member']
    if not member_role or any(r['name'] in {'reports-analyst','reports-admin'} for r in original): raise CheckFailure('Unexpected synthetic member2 roles')
    subscription=None;view=None
    try:
        catalog=expect(200,call(tokens['admin'],'reports'));assert len(catalog['items'])==11
        for n in range(1,12):
            result=expect(200,call(tokens['admin'],f'reports/R-{n:02d}/query','POST',QUERY))
            if result['reportId']!=f'R-{n:02d}': raise CheckFailure('Incorrect report identifier')
        checks.append('all_eleven_reports_real_app_role')
        result=expect(200,call(tokens['member1'],'reports/R-01/query','POST',QUERY));assert result['totals']['M-01']==3.75
        expect(403,call(tokens['member1'],'reports/R-02/query','POST',QUERY));checks.append('member_report_and_data_scope')
        view=expect(201,call(tokens['admin'],'views','POST',{'reportId':'R-01','name':'Local smoke verification','query':QUERY}))['viewId']
        expect(404,call(tokens['member1'],'views/'+view));checks.append('owned_views')
        print('Checking durable CSV/XLSX jobs and protected downloads',flush=True)
        for fmt in ['csv','xlsx']:
            job=expect(202,call(tokens['admin'],'exports','POST',{'reportId':'R-01','query':QUERY,'format':fmt}))
            end=time.monotonic()+40
            while expect(200,call(tokens['admin'],'exports/'+job['exportId']))['status']=='QUEUED' and time.monotonic()<end: time.sleep(1)
            file=expect(200,call(tokens['admin'],'exports/'+job['exportId']+'/file'))
            if fmt=='xlsx':
                with zipfile.ZipFile(io.BytesIO(file)) as z: assert 'xl/worksheets/sheet1.xml' in z.namelist()
            else: assert file.startswith(b'\xef\xbb\xbf')
            expect(404,call(tokens['member1'],'exports/'+job['exportId']+'/file'))
        checks.append('csv_xlsx_worker_and_owner_download')
        print('Checking scheduled delivery after live Keycloak role revocation',flush=True)
        kc(member_path,member_role,'DELETE')
        payload={'reportId':'R-01','query':QUERY,'schedule':'* * * * *','format':'csv','recipients':list(members.values())}
        subscription=expect(201,call(tokens['admin'],'subscriptions','POST',payload))['subscriptionId']
        end=time.monotonic()+85
        while time.monotonic()<end:
            delivery=expect(200,call(tokens['admin'],'subscriptions/'+subscription+'/deliveries'))
            if delivery['items']: break
            time.sleep(1)
        if not delivery['items']: raise CheckFailure('Scheduled delivery timed out')
        delivery=delivery['items'][0]
        if delivery['delivered']!=[members['member1']] or members['member2'] not in [r['recipient'] for r in delivery['skipped']]:
            raise CheckFailure('Live recipient role revocation did not constrain delivery')
        notifications=expect(200,call(tokens['member1'],'notifications'))
        files=[n['exportId'] for n in notifications['items'] if n['kind']=='SCHEDULED_REPORT_READY']
        if not files: raise CheckFailure('Scheduled notification missing')
        data=expect(200,call(tokens['member1'],'exports/'+files[0]+'/file'))
        if b'3.75' not in data or b'11.25' in data: raise CheckFailure('Scheduled export crossed recipient scope')
        checks.append('live_keycloak_recipient_revocation_and_scoped_delivery')
        expect(403,call(tokens['member1'],'audit'));events=expect(200,call(tokens['admin'],'audit'))
        if events['total']<11: raise CheckFailure('Audit events missing')
        checks.append('admin_only_audit')
        req=urllib.request.Request('http://localhost:8081/ui/')
        with urllib.request.urlopen(req) as response:
            if "script-src 'self'" not in response.headers.get('Content-Security-Policy',''): raise CheckFailure('UI CSP missing')
        checks.append('ui_static_csp')
    finally:
        kc(member_path,member_role,'POST')
        try:
            if subscription: expect(204,call(tokens['admin'],'subscriptions/'+subscription,'DELETE'))
        finally:
            if view: expect(204,call(tokens['admin'],'views/'+view,'DELETE'))
    root=directory.parents[1]
    files=['api.py','product_http.py','product_store.py','report_engine.py','product_service.py','product_jobs.py','delivery.py','product_ui.py','product_demo.py','product_fixture.py','provision.py','compose.yaml','check_product.py','ui/index.html','ui/app.js','ui/styles.css']
    result={'passed':True,'checked_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
            'real_keycloak':True,'real_reports_app_database_role':True,'real_worker':True,'browser_rendering_verified':False,
            'test_subscription_completed':True,'member_role_restored':True,'source_integrations':'synthetic local sources',
            'source_sha256':{str((directory/name).relative_to(root)):hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in files}}
    if args.record: artifact.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result));return 0


if __name__=='__main__':
    try: sys.exit(main())
    except Exception as error:
        print(json.dumps({'passed':False,'error_type':type(error).__name__,'check':str(error) if isinstance(error,CheckFailure) else 'See phase; private response details suppressed'}));sys.exit(1)
