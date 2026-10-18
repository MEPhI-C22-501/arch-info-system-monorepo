import copy
import json
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import select
from server.auth import DEMO_PROJECT as PID, DEMO_PORTFOLIO as PORT
from server import storage as db
from server.seed import stable,seed
from server.domain import validate_draft,forecast

VID=stable('plan')
def headers(role='R-02',revision=None,key=None):
    h={'Authorization':'Bearer demo-'+role,'Idempotency-Key':key or str(uuid4())}
    if revision:h['If-Match']=f'"{revision}"'
    return h

def call(client,method,path,body=None,role='R-02',revision=None,expected=200,key=None):
    r=client.request(method,'/api/v1/'+path,json=body,headers=headers(role,revision,key))
    assert r.status_code==expected,r.text
    return r.json()

def plan(client):return call(client,'GET','versions/'+VID)
def draft(v):return {k:copy.deepcopy(v[k]) for k in ['name','planningMode','horizonStart','horizonEnd','items','dependencies','demands','allocations']}

def confirm(client,vid=VID):
    rows=call(client,'GET','availability',role='R-04');row=next(x for x in rows if x['data']['employeeId']=='employees/demo-1' and x['data']['date']=='2026-10-05')
    data={**row['data'],'availableHours':6,'nominalHours':10}
    call(client,'PUT','availability/'+data['id'],data,role='R-04',revision=row['revision'])
    with db.engine.connect() as c:revision=db.find(c,'plan',vid)['data']['revision']
    call(client,'POST','versions/'+vid+'/confirm-resources',{},role='R-04',revision=revision)

def activate(client,vid=VID):
    confirm(client,vid)
    v=call(client,'GET','versions/'+vid)
    v=call(client,'POST','versions/'+vid+'/submit',{'reviewers':[{'subject':'demo-R-01','role':'FINAL_APPROVER','resourceScope':[]}]},revision=v['revision'])
    v=call(client,'POST','versions/'+vid+'/decisions',{'reviewRound':v['reviewRound'],'contentRevision':v['contentRevision'],'decision':'APPROVE','comment':None},role='R-01',revision=v['revision'])
    p=call(client,'GET','projects/'+PID)
    return call(client,'POST','versions/'+vid+'/activate',{'projectRevision':p['revision']},role='R-01',revision=v['revision'])

def test_cycle_projection_batch_and_baseline(client):
    v=activate(client);assert v['status']=='ACTIVE'
    qa=call(client,'GET',f'projects/{PID}/release-context?planVersionId={VID}',role='S-07')
    assert qa['iterations'] is None and qa['quality']=='PARTIAL'
    assert qa==call(client,'GET',f'projects/{PID}/release-context',role='S-07')
    op=call(client,'POST',f'versions/{VID}/forecasts',{'contentRevision':v['contentRevision']},expected=202)
    status=call(client,'GET','operations/'+op['operationId']);assert status['status']=='SUCCEEDED'
    f=call(client,'GET','forecasts/'+op['resultId']);assert f['estimatedTotalCost']==20000 and f['budgetAdjustment']==2000
    projection=call(client,'GET','projects/'+PID+'/projection',role='S-06');assert 'estimatedTotalCost' not in projection['forecast']
    batch=call(client,'POST','exports',{'portfolioId':PORT},role='S-06',expected=202)
    rows=call(client,'GET','exports/'+batch['batchId']+'/rows?pageSize=1',role='S-06')
    assert len(rows['items'])==1 and rows['nextCursor']
    assert rows==call(client,'GET','exports/'+batch['batchId']+'/rows?pageSize=1',role='S-06')
    frozen=copy.deepcopy(rows)
    scenario=call(client,'POST',f'projects/{PID}/versions',{'baseVersionId':VID,'kind':'SCENARIO','name':'Новый сценарий'},expected=201)
    assert scenario['items'][0]['id']!=v['items'][0]['id']
    assert scenario['items'][0]['logicalItemId']==v['items'][0]['logicalItemId']
    assert call(client,'GET','versions/'+VID)==v
    assert call(client,'GET','exports/'+batch['batchId']+'/rows?pageSize=1',role='S-06')==frozen
    call(client,'PUT',f'versions/{VID}/draft',draft(v),revision=v['revision'],expected=409)
    call(client,'GET','exports/'+batch['batchId'],role='S-06')
    cursor=rows['nextCursor'];call(client,'GET','exports/'+batch['batchId']+'/rows?cursor='+cursor[:-1]+'x',role='S-06',expected=400)

def test_return_stale_revision_and_idempotency(client):
    confirm(client);v=plan(client)
    b={'reviewers':[{'subject':'demo-R-01','role':'FINAL_APPROVER','resourceScope':[]}]};key=str(uuid4())
    submitted=call(client,'POST',f'versions/{VID}/submit',b,revision=v['revision'],key=key)
    assert submitted==call(client,'POST',f'versions/{VID}/submit',b,revision=v['revision'],key=key)
    call(client,'POST',f'versions/{VID}/submit',{'reviewers':[]},revision=v['revision'],key=key,expected=409)
    call(client,'POST',f'versions/{VID}/decisions',{'reviewRound':submitted['reviewRound'],'contentRevision':submitted['contentRevision'],'decision':'RETURN','comment':'Уточнить'},role='R-01',revision=v['revision'],expected=412)
    returned=call(client,'POST',f'versions/{VID}/decisions',{'reviewRound':submitted['reviewRound'],'contentRevision':submitted['contentRevision'],'decision':'RETURN','comment':'Уточнить'},role='R-01',revision=submitted['revision'])
    assert returned['status']=='DRAFT'
    d=draft(returned);d['name']='Редакция'
    saved=call(client,'PUT',f'versions/{VID}/draft',d,revision=returned['revision']);assert saved['contentRevision']>returned['contentRevision']
    call(client,'PUT',f'versions/{VID}/draft',d,revision=returned['revision'],expected=412)

def test_crud_filters_cursor_and_first_version(client):
    body={'portfolioId':PORT,'programId':None,'code':'NEW','name':'Проект 2','goal':'Цель','managerSubject':'demo-R-03'}
    p=call(client,'POST','projects',body,expected=201)
    result=call(client,'GET','projects?pageSize=1');assert result['nextCursor']
    nextpage=call(client,'GET','projects?pageSize=1&cursor='+result['nextCursor']);assert nextpage['items'][0]['id']!=result['items'][0]['id']
    assert len(call(client,'GET','projects?q=Проект')['items'])==1
    p=call(client,'PATCH','projects/'+p['id'],{'name':'Новое имя','goal':'Другая цель'},revision=p['revision']);assert p['name']=='Новое имя'
    v=call(client,'POST','projects/'+p['id']+'/versions',{'baseVersionId':None,'kind':'PLAN','name':'Первый план'},expected=201);assert v['baseVersionId'] is None
    p=call(client,'POST','projects/'+p['id']+'/archive',{'reason':'Завершён'},role='R-01',revision=p['revision']);assert p['status']=='ARCHIVED'

@pytest.mark.parametrize('role,path',[('R-06','projects'),('R-05','versions/'+VID),('R-04','projects/'+PID),('S-07','versions/'+VID),('S-06','versions/'+VID)])
def test_roles_cannot_read_full_business_objects(client,role,path):call(client,'GET',path,role=role,expected=403)

def test_foreign_scope_and_forged_auth(client):
    call(client,'GET','projects/'+str(uuid4()),expected=404)
    assert client.get('/api/v1/projects').status_code==401
    assert client.get('/api/v1/projects',headers={'Authorization':'Bearer forged'}).status_code==401
    call(client,'POST',f'versions/{VID}/activate',{'projectRevision':1},role='R-06',revision=1,expected=403)

def test_overload_invariants_and_event_dedup(client):
    call(client,'POST',f'versions/{VID}/submit',{'reviewers':[{'subject':'demo-R-01','role':'FINAL_APPROVER','resourceScope':[]}]},revision=1,expected=422)
    event=json.loads((Path(__file__).parents[1]/'docs/contracts/events/TaskChanged.example.json').read_text());event['projectId']=PID
    call(client,'POST','integrations/task-events',event,role='S-03')
    assert call(client,'POST','integrations/task-events',event,role='S-03')['status']=='duplicate'
    event['eventId']=str(uuid4());event['payload']['sourceRevision']=2;event['payload']['actualHours']=10
    call(client,'POST','integrations/task-events',event,role='S-03')
    old=copy.deepcopy(event);old['eventId']=str(uuid4());old['payload']['sourceRevision']=1
    call(client,'POST','integrations/task-events',old,role='S-03')
    with db.engine.connect() as c:
        task=next(r['data'] for r in db.all_rows(c,'task') if r['data']['externalTaskId']=='task-1');assert task['actualHours']==10
    changed=copy.deepcopy(event);changed['payload']['actualHours']=11
    call(client,'POST','integrations/task-events',changed,role='S-03',expected=409)

def test_attachments_security_origin_and_no_injection(client):
    files={'file':('justification.txt',b'hello','text/plain')}
    r=client.post('/api/v1/attachments',headers=headers(),data={'ownerType':'PROJECT','ownerId':PID},files=files);assert r.status_code==201,r.text
    a=r.json();assert a['status']=='AVAILABLE'
    call(client,'GET','attachments/'+a['id'])
    content=client.get('/api/v1/attachments/'+a['id']+'/content',headers=headers());assert content.content==b'hello'
    call(client,'GET','attachments/'+a['id'],role='R-06',expected=403)
    call(client,'DELETE','attachments/'+a['id'],revision=1,expected=202)
    assert client.post('/api/v1/attachments',headers=headers(),data={'ownerType':'PROJECT','ownerId':PID},files={'file':('bad.pdf',b'hello','application/pdf')}).status_code==422
    h=headers(revision=1);h['Origin']='https://attacker.invalid'
    assert client.patch('/api/v1/projects/'+PID,headers=h,json={'name':'pwned','goal':'x'}).status_code==403
    p=call(client,'PATCH','projects/'+PID,{'name':'<script>alert(1)</script>','goal':"' OR 1=1 --"},revision=1)
    assert p['name']=='<script>alert(1)</script>'
    assert call(client,'GET','projects?q=%27%20OR%201=1')['items']==[]
    response=client.get('/');assert "script-src 'self'" in response.headers['Content-Security-Policy']

def test_publication_receipt_retry(client):
    activate(client)
    workspace=call(client,'GET','workspace',role='R-06');pubid=workspace['publicationId']
    pub=call(client,'GET','publications/'+pubid,role='S-03')
    retry=call(client,'POST','publications/'+pubid+'/retry',{'reason':'Retry'},role='R-06',expected=202)
    receipt={'publicationId':pubid,'projectId':PID,'planVersionId':VID,'status':'APPLIED','externalReceipt':'test-receipt','sourceRevision':1}
    call(client,'POST','publications/'+pubid+'/receipt',receipt,role='S-03')
    assert pub['plan']['id']==VID
    with db.engine.connect() as c:assert db.find(c,'publication',pubid)['data']['status']=='SUCCEEDED'

def test_seed_idempotent(client):
    with db.engine.connect() as c:before=len(c.execute(select(db.records)).all())
    seed()
    with db.engine.connect() as c:assert len(c.execute(select(db.records)).all())==before

def test_domain_cycles_money_missing():
    assert forecast([{'actualHours':12,'isDeleted':False}],8,1000,18000)['estimatedTotalCost']==20000
    assert forecast([],None)['quality']=='PARTIAL'

def test_oidc_signature_issuer_audience_expiry(client,monkeypatch):
    import time
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from server.app import app
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    class Keys:
        def get_signing_key_from_jwt(self,token):
            class Key: key=private.public_key()
            return Key()
    monkeypatch.setattr(app.state,'jwks',Keys(),raising=False)
    monkeypatch.setenv('AUTH_MODE','oidc');monkeypatch.setenv('OIDC_ISSUER','https://issuer.test/realm');monkeypatch.setenv('OIDC_AUDIENCE','planning-api')
    claims={'sub':'test-planner','iat':int(time.time()),'exp':int(time.time())+60,'iss':'https://issuer.test/realm','aud':'planning-api',
            'realm_access':{'roles':['PLANNER']},'portfolio_ids':[PORT],'project_ids':[PID]}
    def request(value,key=private):
        token=jwt.encode(value,key,algorithm='RS256');return client.get('/api/v1/projects/'+PID,headers={'Authorization':'Bearer '+token})
    assert request(claims).status_code==200
    monkeypatch.setenv('OIDC_ISSUER','https://issuer.test/realm/')
    assert request(claims).status_code==200
    for field,value in [('iss','https://other.test'),('aud','other-api'),('exp',int(time.time())-60)]:assert request({**claims,field:value}).status_code==401
    assert request(claims,rsa.generate_private_key(public_exponent=65537,key_size=2048)).status_code==401

def test_postgres_baseline_trigger(client):
    if db.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL trigger test')
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError
    activate(client)
    with db.engine.connect() as c:v=copy.deepcopy(db.find(c,'plan',VID)['data'])
    v['name']='illegal'
    with pytest.raises(DBAPIError):
        with db.engine.begin() as c:c.execute(update(db.records).where(db.records.c.id==VID,db.records.c.kind=='plan').values(data=v))
    assert plan(client)['name']!='illegal'

def test_worker_adapter_and_mock_receipt(client,monkeypatch):
    import httpx
    from server.worker import tick,deliver
    monkeypatch.setenv('INTEGRATION_MODE','mock');activate(client);tick()
    with db.engine.connect() as c:pub=db.all_rows(c,'publication')[0]['data']
    assert pub['externalReceipt'].startswith('mock:') and pub['status']=='SUCCEEDED'
    monkeypatch.setenv('INTEGRATION_MODE','real');monkeypatch.setenv('TT_MAPPING_APPROVED','true');monkeypatch.setenv('TT_BASE_URL','https://tt.test/api/v1');monkeypatch.setenv('TT_TOKEN','fixture')
    def handler(request):
        assert request.url.path=='/api/v1/planning/projects/'+PID
        body=json.loads(request.content);assert body['version']==1 and body['epics'][0]['tasks'][0]['plannedHours']==6
        return httpx.Response(200,json={'id':str(uuid4()),'externalProjectId':PID,'version':1,'status':'applied'})
    assert 'applied' in deliver(pub,httpx.MockTransport(handler))

def test_draft_cycles_rollback_and_batch_expiry(client):
    v=plan(client);d=draft(v);d['items'][0]['parentItemId']=d['items'][1]['id']
    call(client,'PUT',f'versions/{VID}/draft',d,revision=v['revision'],expected=422);assert plan(client)==v
    activate(client);batch=call(client,'POST','exports',{'portfolioId':PORT},role='S-06',expected=202)
    with db.engine.begin() as c:
        row=db.find(c,'batch',batch['batchId']);value=copy.deepcopy(row['data']);value['expiresAt']='2000-01-01T00:00:00Z';db.put(c,'batch',value,PORT)
    call(client,'GET','exports/'+batch['batchId']+'/rows',role='S-06',expected=409)

def test_upload_exact_limit_and_rejection(client):
    limit=20*1024*1024
    files={'file':('limit.txt',b'a'*limit,'text/plain')}
    accepted=client.post('/api/v1/attachments',headers=headers(),data={'ownerType':'PROJECT','ownerId':PID},files=files)
    assert accepted.status_code==201,accepted.text
    rejected=client.post('/api/v1/attachments',headers=headers(),data={'ownerType':'PROJECT','ownerId':PID},files={'file':('too-large.txt',b'a'*(limit+1),'text/plain')})
    assert rejected.status_code==422,rejected.text

def test_resource_idempotency_and_audit(client):
    rows=call(client,'GET','availability',role='R-04');row=rows[0];key=str(uuid4())
    saved=call(client,'PUT','availability/'+row['data']['id'],row['data'],role='R-04',revision=row['revision'],key=key)
    repeated=call(client,'PUT','availability/'+row['data']['id'],row['data'],role='R-04',revision=row['revision'],key=key)
    assert saved==repeated
    with db.engine.connect() as c:
        assert len(list(c.execute(select(db.audit).where(db.audit.c.action.like('%availability%')))))==1


@pytest.mark.parametrize('path,role,method',[
    ('availability/'+stable('employees/demo-15'),'R-04','PUT'),
    ('versions/'+VID+'/forecast-inputs','R-02','PUT'),
    ('integrations/task-events','S-03','POST'),
    ('portfolios/'+PORT+'/programs','R-01','POST'),
])
def test_runtime_invalid_json_returns_structured_error(client,path,role,method):
    for body,expected in [('{',400),('[1,2]',422),('null',422)]:
        response=client.request(method,'/api/v1/'+path,content=body,
                                headers={**headers(role),'Content-Type':'application/json'})
        assert response.status_code==expected,response.text
        assert response.json()['correlationId']==response.headers['X-Correlation-Id']
        assert response.headers['X-Content-Type-Options']=='nosniff'


def test_bearer_scheme_and_security_headers_on_rejection(client):
    assert client.get('/api/v1/projects',headers={'Authorization':'demo-R-02'}).status_code==401
    assert client.get('/api/v1/projects',headers={'Authorization':'bearer demo-R-02'}).status_code==200
    response=client.patch('/api/v1/projects/'+PID,json={'name':'forged'},
                          headers={**headers(revision=1),'Origin':'https://attacker.invalid'})
    assert response.status_code==403
    assert response.headers['Cache-Control']=='no-store'
    assert response.headers['X-Content-Type-Options']=='nosniff'
    assert response.json()['correlationId']==response.headers['X-Correlation-Id']


def test_qa_default_version_and_historical_projection(client):
    call(client,'GET',f'projects/{PID}/release-context',role='S-07',expected=409)
    activate(client)
    active=call(client,'GET',f'projects/{PID}/release-context',role='S-07')
    scenario=call(client,'POST',f'projects/{PID}/versions',
                  {'baseVersionId':VID,'kind':'SCENARIO','name':'Ещё не утверждён'},expected=201)
    assert call(client,'GET',f'projects/{PID}/release-context',role='S-07')==active
    call(client,'GET',f'projects/{PID}/release-context?planVersionId='+scenario['id'],role='S-07',expected=404)
    assert call(client,'GET',f'projects/{PID}/release-context?planVersionId={VID}',role='S-07')==active
