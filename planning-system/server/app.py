import base64
import copy
import hashlib
import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import storage as db
from .auth import actor, DEMO_PORTFOLIO, DEMO_PROJECT
from .domain import fail, validate_draft, check_resources, forecast, hours

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT/'docs/contracts/openapi.json').read_text())
CURSOR_KEY = os.environ.get('CURSOR_SECRET','development-only-cursor-key').encode()

@asynccontextmanager
async def lifespan(app):
    if os.environ.get('AUTH_MODE','oidc')=='demo' and os.environ.get('APP_ENV')!='development':
        raise RuntimeError('Demo auth requires development')
    if os.environ.get('APP_ENV')!='development' and len(CURSOR_KEY)<32:
        raise RuntimeError('CURSOR_SECRET must contain at least 32 characters')
    if os.environ.get('AUTH_MODE','oidc')=='oidc':
        issuer=os.environ['OIDC_ISSUER'].rstrip('/')
        if not issuer.startswith('https://'):raise RuntimeError('HTTPS issuer required')
        with httpx.Client(timeout=10) as client:
            r=client.get(issuer+'/.well-known/openid-configuration');r.raise_for_status()
        app.state.oidc=r.json()
        if app.state.oidc['issuer']!=issuer:raise RuntimeError('Issuer mismatch')
        app.state.jwks=jwt.PyJWKClient(app.state.oidc['jwks_uri'],cache_keys=True)
    db.migrate()
    if os.environ.get('DEMO_SEED')=='true':
        if os.environ.get('APP_ENV')!='development':raise RuntimeError('Synthetic seed requires development')
        from .seed import seed
        seed()
    yield

app=FastAPI(title='Planning System',lifespan=lifespan)
app.openapi=lambda:{**SPEC,'paths':{**SPEC['paths'],**json.loads((ROOT/'docs/contracts/runtime.openapi.json').read_text())['paths']}}

@app.middleware('http')
async def protections(req, call_next):
    req.state.correlation=db.uid()
    if req.method not in {'GET','HEAD','OPTIONS'}:
        origin=req.headers.get('Origin')
        permitted=set(os.environ.get('ALLOWED_ORIGINS','http://localhost:8080,http://127.0.0.1:8080').split(','))
        if origin and origin not in permitted:
            return error(403,'Запрос из чужого origin отклонён',req)
        if int(req.headers.get('content-length','0')) > 21*1024*1024:
            return error(413,'Тело запроса слишком большое',req)
    r=await call_next(req)
    issuer_url=urlparse(os.environ.get('OIDC_ISSUER',''))
    issuer=f'{issuer_url.scheme}://{issuer_url.netloc}' if issuer_url.netloc else ''
    r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; connect-src 'self' "+issuer
    r.headers['Content-Security-Policy']=r.headers['Content-Security-Policy'].strip()
    r.headers['X-Content-Type-Options']='nosniff'
    r.headers['Referrer-Policy']='no-referrer'
    r.headers['X-Correlation-Id']=req.state.correlation
    r.headers['Cache-Control']='no-store'
    return r

def error(code,message,req):
    return JSONResponse({'code':{400:'INVALID_REQUEST',401:'UNAUTHORIZED',403:'FORBIDDEN',404:'NOT_FOUND',409:'CONFLICT',412:'REVISION_CONFLICT',422:'VALIDATION_ERROR',503:'DEPENDENCY_UNAVAILABLE'}.get(code,'ERROR'),
       'message':message,'correlationId':getattr(req.state,'correlation',db.uid()),'details':[]},status_code=code)

@app.exception_handler(HTTPException)
async def http_error(req,exc):return error(exc.status_code,str(exc.detail),req)
@app.exception_handler(db.Conflict)
async def concurrency_error(req,exc):return error(412,str(exc),req)
@app.exception_handler(IntegrityError)
async def constraint_error(req,exc):return error(409,'Конфликт уникальности',req)

@app.get('/livez')
def livez():return {'status':'ok'}
@app.get('/readyz')
def readyz():
    try:
        with db.engine.connect() as c:
            expected=2 if db.engine.dialect.name=='postgresql' else 1
            c.execute(select(db.schema_versions).where(db.schema_versions.c.version==expected)).one()
        return {'status':'ready','schemaVersion':expected}
    except Exception:raise HTTPException(503,'БД или миграции недоступны') from None

@app.get('/auth/config')
def auth_config():
    demo=os.environ.get('AUTH_MODE')=='demo'
    return {'mode':'demo' if demo else 'oidc','clientId':os.environ.get('OIDC_CLIENT_ID','planning-web'),
        'authorizationEndpoint':None if demo else app.state.oidc['authorization_endpoint'],
        'tokenEndpoint':None if demo else app.state.oidc['token_endpoint']}

def allowed(a,roles):
    if not a.roles & set(roles):fail(403,'Операция недоступна роли')

def get(c,kind,identifier,a,roles=None):
    if roles:allowed(a,roles)
    row=db.find(c,kind,identifier)
    if not row:fail(404,'Объект не найден')
    if row['portfolio_id'] not in a.portfolios:fail(404,'Объект не найден')
    if 'R-03' in a.roles and row['project_id'] and row['project_id'] not in a.projects and not a.roles & {'R-01','R-02'}:
        own=db.find(c,'project',row['project_id'])
        if not own or own['data']['managerSubject']!=a.subject:fail(404,'Объект не найден')
    return copy.deepcopy(row['data'])

def money_filter(value,a):
    if isinstance(value,list):return [money_filter(x,a) for x in value]
    if isinstance(value,dict):return {k:money_filter(v,a) for k,v in value.items() if 'cost.read' in a.scopes or k not in {'baselineBudget','currencyCode','estimatedTotalCost','budgetAdjustment','rate'}}
    return value

def project(c,pid,a,roles=('R-01','R-02','R-03','R-04','S-03','S-06','S-07')):
    return get(c,'project',pid,a,roles)

def version(c,vid,a,roles=('R-01','R-02','R-03')):
    v=get(c,'plan',vid,a,roles);project(c,v['projectId'],a,roles);return v

def save(c,kind,data,a,portfolio,project_id=None):
    return db.put(c,kind,data,portfolio,project_id)

def changed(c,kind,data,req,a):
    row=db.find(c,kind,data['id'])
    match=req.headers.get('If-Match')
    if match is None:fail(400,'Нужен If-Match')
    if match!=f'"{row["revision"]}"':fail(412,'Объект изменился; перечитайте его')
    data['revision']=row['revision']+1
    db.put(c,kind,data,row['portfolio_id'],row['project_id'],expected=row['revision'])
    return data

def plan_public(v):
    return {k:v[k] for k in SPEC['components']['schemas']['Plan']['properties'] if k in v}

def validate(schema,data):
    errs=list(Draft202012Validator({**schema,'components':SPEC['components']},format_checker=FormatChecker()).iter_errors(data))
    if errs:fail(422,errs[0].message[:250])

def page(values,req,a,binding):
    size=int(req.query_params.get('pageSize','50'))
    if not 1<=size<=200:fail(422,'pageSize 1..200')
    scope=hashlib.sha256(json.dumps([binding,a.subject,sorted(a.portfolios),sorted(a.scopes)],sort_keys=True).encode()).hexdigest()
    after=None;cursor=req.query_params.get('cursor')
    if cursor:
        try:
            payload,sig=cursor.split('.')
            if not hmac.compare_digest(sig,hmac.new(CURSOR_KEY,payload.encode(),hashlib.sha256).hexdigest()):raise ValueError()
            decoded=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            if decoded['scope']!=scope:raise ValueError()
            after=decoded['after']
        except Exception:fail(400,'Недействительный cursor')
    if after is not None:values=[v for v in values if v['_key']>after]
    selected=values[:size];next_cursor=None
    if len(values)>size:
        payload=base64.urlsafe_b64encode(json.dumps({'scope':scope,'after':selected[-1]['_key']}).encode()).decode().rstrip('=')
        next_cursor=payload+'.'+hmac.new(CURSOR_KEY,payload.encode(),hashlib.sha256).hexdigest()
    return [{k:v for k,v in row.items() if k!='_key'} for row in selected],next_cursor

def resource_inputs(c,v):
    availability={(r['data']['employeeId'],r['data']['date']):r['data'] for r in db.all_rows(c,'availability')}
    other=[]
    for row in db.all_rows(c,'plan'):
        p=row['data']
        if p['status']=='ACTIVE' and p['projectId']!=v['projectId']:other+=p['allocations']
    return availability,other

def resource_snapshot(c,v):
    pairs={(x['employeeId'],x['date']) for x in v['allocations'] if x['status']!='CANCELLED'}
    return sorted([{'data':r['data'],'revision':r['revision']} for r in db.all_rows(c,'availability') if (r['data']['employeeId'],r['data']['date']) in pairs],key=lambda r:r['data']['id'])

def check_batch(b,a):
    if b['scopeHash']!=hashlib.sha256(json.dumps(sorted(a.scopes)).encode()).hexdigest():fail(403,'Права партии изменились')
    if b['expiresAt']<=db.now():fail(409,'BATCH_EXPIRED')
    if b['status']!='READY':fail(409,'Партия не готова')

def dispatch(c,op,req,a,b):
    pp=req.path_params
    if op=='listProjects':
        allowed(a,['R-01','R-02','R-03'])
        rows=[]
        for r in db.all_rows(c,'project'):
            v=r['data']
            if r['portfolio_id'] not in a.portfolios or ('R-03' in a.roles and not a.roles & {'R-01','R-02'} and v['id'] not in a.projects and v['managerSubject']!=a.subject):continue
            if req.query_params.get('status') and v['status']!=req.query_params['status']:continue
            if req.query_params.get('portfolioId') and v['portfolioId']!=req.query_params['portfolioId']:continue
            if req.query_params.get('q','').casefold() not in v['name'].casefold():continue
            rows.append({**v,'_key':f'{v["priority"]:010d}:{v["id"]}'})
        rows.sort(key=lambda r:r['_key'])
        values,nxt=page(rows,req,a,['projects',dict(req.query_params.multi_items()) | {'cursor':None,'pageSize':None}])
        return {'items':values,'nextCursor':nxt}
    if op=='createProject':
        allowed(a,['R-01','R-02','R-03']);get(c,'portfolio',b['portfolioId'],a)
        if b['programId']:
            prog=get(c,'program',b['programId'],a)
            if prog['portfolioId']!=b['portfolioId']:fail(422,'Чужая программа')
        if 'R-03' in a.roles and b['managerSubject']!=a.subject:fail(403,'Руководитель назначает себя')
        if any(r['data']['code']==b['code'] for r in db.all_rows(c,'project',b['portfolioId'])):fail(409,'Код проекта занят')
        p={**b,'id':db.uid(),'revision':1,'priority':1,'status':'DRAFT','activePlanVersionId':None}
        return save(c,'project',p,a,p['portfolioId'],p['id'])
    if op in {'getProject','updateProject','archiveProject'}:
        p=project(c,pp['projectId'],a,['R-01','R-02','R-03'])
        if op=='getProject':return p
        allowed(a,['R-01','R-02','R-03'] if op=='updateProject' else ['R-01','R-03'])
        if p['status']=='ARCHIVED':fail(409,'Проект архивирован')
        p.update(b if op=='updateProject' else {'status':'ARCHIVED'})
        return changed(c,'project',p,req,a)
    if op=='createVersion':
        p=project(c,pp['projectId'],a,['R-02','R-03'])
        if p['status']=='ARCHIVED':fail(409,'Проект архивирован')
        if b['baseVersionId']:
            base=version(c,b['baseVersionId'],a,['R-02','R-03'])
            if base['projectId']!=p['id']:fail(422,'Чужая базовая версия')
            v=copy.deepcopy(base)
            mapping={i['id']:db.uid() for i in v['items']};dm={d['id']:db.uid() for d in v['demands']}
            for i in v['items']:i.update(id=mapping[i['id']],parentItemId=mapping.get(i['parentItemId']))
            for dep in v['dependencies']:dep.update(id=db.uid(),predecessorId=mapping[dep['predecessorId']],successorId=mapping[dep['successorId']])
            for d in v['demands']:d.update(id=dm[d['id']],planItemId=mapping[d['planItemId']])
            for al in v['allocations']:al.update(id=db.uid(),demandId=dm[al['demandId']],status='PROPOSED')
        else:
            v={'planningMode':'ANNUAL','horizonStart':'2026-10-05','horizonEnd':'2026-12-31','items':[],'dependencies':[],'demands':[],'allocations':[]}
        v.update(id=db.uid(),projectId=p['id'],name=b['name'],kind=b['kind'],baseVersionId=b['baseVersionId'],
          versionNumber=max([r['data']['versionNumber'] for r in db.all_rows(c,'plan',project=p['id'])]+[0])+1,
          revision=1,contentRevision=1,reviewRound=0,status='DRAFT',dataAsOf=None,reviewers=[],decisions=[])
        return save(c,'plan',v,a,p['portfolioId'],p['id'])
    if op in {'getVersion','saveDraft','submitReview','recordDecision','activatePlan','calculateForecast'}:
        v=version(c,pp['versionId'],a,['R-01','R-02','R-03','R-04'] if op=='recordDecision' else ['R-01','R-02','R-03']);p=project(c,v['projectId'],a)
        if op=='getVersion':return plan_public(v)
        if p['status']=='ARCHIVED':fail(409,'Проект архивирован')
        if op=='saveDraft':
            allowed(a,['R-02','R-03'])
            if v['status']!='DRAFT':fail(409,'Baseline неизменна; создайте сценарий')
            validate_draft(b)
            if 'R-03' in a.roles and b['allocations']!=v['allocations']:fail(403,'Изменение назначений недоступно R-03')
            old={x['id']:x for x in v['allocations']}
            for x in b['allocations']:
                prev=old.get(x['id'])
                if not prev or any(prev.get(k)!=x.get(k) for k in ['demandId','employeeId','date','hours']):x['status']='PROPOSED'
                elif x['status']!=prev['status']:fail(403,'Подтверждает только R-04')
            v.update(b);v['contentRevision']+=1
        if op=='submitReview':
            allowed(a,['R-02','R-03'])
            if v['status']!='DRAFT' or not v['items']:fail(409,'Нужен непустой черновик')
            validate_draft(v);check_resources(v,*resource_inputs(c,v))
            reviewers=b['reviewers']
            if not reviewers or not any(x['role']=='FINAL_APPROVER' for x in reviewers):fail(422,'Нужен финальный согласующий')
            owner=get(c,'portfolio',p['portfolioId'],a).get('ownerSubject')
            if not owner or any(x['role']=='FINAL_APPROVER' and x['subject']!=owner for x in reviewers):fail(422,'Финальный согласующий должен быть владельцем портфеля')
            if len({x['subject'] for x in reviewers})!=len(reviewers):fail(422,'Дубли согласующих')
            v.update(status='ON_REVIEW',reviewRound=v['reviewRound']+1,reviewers=reviewers,decisions=[],resourceSnapshot=resource_snapshot(c,v))
        if op=='recordDecision':
            allowed(a,['R-01','R-04'])
            if v['status']!='ON_REVIEW':fail(409,'Версия не на согласовании')
            if v.get('resourceSnapshot')!=resource_snapshot(c,v):fail(409,'Ресурсные входы изменились; нужно новое согласование')
            if b['reviewRound']!=v['reviewRound'] or b['contentRevision']!=v['contentRevision']:fail(409,'Решение по устаревшему раунду')
            rv=next((x for x in v['reviewers'] if x['subject']==a.subject),None)
            if not rv or (rv['role']=='FINAL_APPROVER' and 'R-01' not in a.roles) or (rv['role']=='RESOURCE_OWNER' and 'R-04' not in a.roles):fail(403,'Вы не согласующий этой версии')
            if any(x['subject']==a.subject for x in v['decisions']):fail(409,'Решение уже записано')
            if b['decision']=='RETURN' and not (b['comment'] or '').strip():fail(422,'Нужна причина возврата')
            v['decisions'].append({**b,'subject':a.subject})
            if b['decision']=='RETURN':v['status']='DRAFT'
            elif len(v['decisions'])==len(v['reviewers']):v.update(status='APPROVED',dataAsOf=db.now())
        if op=='activatePlan':
            allowed(a,['R-01'])
            if v['status']!='APPROVED':fail(409,'Нужна утверждённая версия')
            if v.get('resourceSnapshot')!=resource_snapshot(c,v):fail(409,'Ресурсные входы изменились после согласования')
            if b['projectRevision']!=p['revision']:fail(412,'Редакция проекта изменилась')
            check_resources(v,*resource_inputs(c,v))
            if p['activePlanVersionId']:
                old=version(c,p['activePlanVersionId'],a);old['status']='SUPERSEDED';old['revision']+=1
                save(c,'plan',old,a,p['portfolioId'],p['id'])
            v.update(status='ACTIVE',dataAsOf=db.now());p.update(status='ACTIVE',activePlanVersionId=v['id'],revision=p['revision']+1)
            save(c,'project',p,a,p['portfolioId'],p['id'])
            pub={'id':db.uid(),'publicationId':None,'projectId':p['id'],'planVersionId':v['id'],'idempotencyKey':p['id']+':'+v['id'],
                 'plan':plan_public(v),'status':'PENDING','attempts':0,'externalReceipt':None}
            pub['publicationId']=pub['id'];save(c,'publication',pub,a,p['portfolioId'],p['id'])
            save(c,'outbox',{'id':db.uid(),'eventType':'PlanActivated','projectId':p['id'],'planVersionId':v['id'],'status':'PENDING','occurredAt':db.now()},a,p['portfolioId'],p['id'])
        if op=='calculateForecast':
            allowed(a,['R-02','R-03'])
            if b['contentRevision']!=v['contentRevision']:fail(409,'Содержимое изменилось')
            inputs=db.find(c,'forecast_input',v['id']);inputs=inputs['data'] if inputs else {}
            tasks=[r['data'] for r in db.all_rows(c,'task',project=p['id'])]
            result=forecast(tasks,inputs.get('etc'),inputs.get('rate'),v.get('baselineBudget'))
            result.update(id=db.uid(),planVersionId=v['id'],calculatedAt=db.now(),dataAsOf=db.now(),forecastFinish=None,
                          currencyCode=inputs.get('currencyCode'),inputSnapshot=inputs)
            if not tasks:result['missingInputs'].append('TASK_FACTS')
            result['missingInputs'].append('WORKING_CALENDAR_FINISH');result['quality']='PARTIAL'
            save(c,'forecast',result,a,p['portfolioId'],p['id'])
            opdata={'id':db.uid(),'operationId':None,'status':'SUCCEEDED','resultId':result['id'],'errorCode':None}
            opdata['operationId']=opdata['id'];save(c,'operation',opdata,a,p['portfolioId'],p['id']);return opdata
        return changed(c,'plan',v,req,a)
    if op in {'getOperation','getForecast'}:
        kind='operation' if op=='getOperation' else 'forecast'
        return get(c,kind,pp['operationId' if kind=='operation' else 'forecastId'],a,['R-01','R-02','R-03'])
    if op in {'getReleaseContext','getReportProjection'}:
        role='S-07' if op=='getReleaseContext' else 'S-06';scope='qa.read' if role=='S-07' else 'reports.read'
        allowed(a,[role])
        if scope not in a.scopes:fail(403,'Нужна сервисная область')
        p=project(c,pp['projectId'],a,[role])
        vid=req.query_params.get('planVersionId') if role=='S-07' else p['activePlanVersionId']
        if not vid:fail(409,'Нет активного плана')
        v=version(c,vid,a,[role])
        if v['projectId']!=p['id'] or v['status'] not in {'APPROVED','ACTIVE','SUPERSEDED','ARCHIVED'}:fail(404,'Утверждённая версия не найдена')
        if role=='S-07':
            return {'projectId':p['id'],'planVersionId':vid,'dataAsOf':v['dataAsOf'],'quality':'PARTIAL','missingInputs':['TT_ITERATIONS_UNCONFIRMED'],
             'items':[x for x in v['items'] if x['type'] in {'RELEASE','MILESTONE','EPIC','FEATURE'}],'iterations':None}
        forecasts=[r['data'] for r in db.all_rows(c,'forecast',project=p['id']) if r['data']['planVersionId']==vid]
        latest=max(forecasts,key=lambda f:f['calculatedAt']) if forecasts else None
        return {'plan':plan_public(v),'forecast':latest,'dataAsOf':v['dataAsOf'],'quality':'PARTIAL' if not latest or latest['quality']=='PARTIAL' else 'COMPLETE'}
    if op=='createExport':
        allowed(a,['S-06'])
        if 'reports.export' not in a.scopes:fail(403,'Нужен reports.export')
        get(c,'portfolio',b['portfolioId'],a)
        rows=[]
        for r in db.all_rows(c,'plan',b['portfolioId']):
            v=r['data']
            if v['status'] not in {'ACTIVE','SUPERSEDED','APPROVED'}:continue
            rows.append({'entityType':'plan','entityId':v['id'],'data':plan_public(v)})
            for kind,field in [('demand','demands'),('allocation','allocations')]:
                for x in v[field]:rows.append({'entityType':kind,'entityId':x['id'],'data':x})
        for kind in ['availability','forecast']:
            for r in db.all_rows(c,kind,b['portfolioId']):rows.append({'entityType':kind,'entityId':r['id'],'data':r['data']})
        rows=money_filter(rows,a)
        batch={'id':db.uid(),'batchId':None,'portfolioId':b['portfolioId'],'dataAsOf':db.now(),'schemaVersion':'1.0.0','status':'READY',
           'expiresAt':(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat().replace('+00:00','Z'),
           'counts':[{'entityType':k,'count':sum(r['entityType']==k for r in rows)} for k in ['plan','demand','availability','allocation','forecast']],
           'rows':rows,'scopeHash':hashlib.sha256(json.dumps(sorted(a.scopes)).encode()).hexdigest()}
        batch['batchId']=batch['id'];save(c,'batch',batch,a,b['portfolioId']);return batch
    if op in {'getExport','exportRows'}:
        allowed(a,['S-06'])
        if 'reports.export' not in a.scopes:fail(403,'Нужен reports.export')
        batch=get(c,'batch',pp['batchId'],a);check_batch(batch,a)
        if op=='getExport':return batch
        rows=[{**r,'_key':f'{i:010d}'} for i,r in enumerate(batch['rows'])]
        values,nxt=page(rows,req,a,['batch',batch['id']])
        return {'batchId':batch['id'],'dataAsOf':batch['dataAsOf'],'items':values,'nextCursor':nxt}
    if op in {'getPublication','publicationReceipt','retryPublication'}:
        roles=['R-06'] if op=='retryPublication' else ['S-03']
        pub=get(c,'publication',pp['publicationId'],a,roles)
        if op=='getPublication':
            if 'publication.read' not in a.scopes:fail(403,'Нужен publication.read')
            return pub
        p=project(c,pub['projectId'],a,roles)
        if p['activePlanVersionId']!=pub['planVersionId']:fail(409,'Версия публикации замещена')
        if op=='publicationReceipt':
            if 'publication.ack' not in a.scopes:fail(403,'Нужен publication.ack')
            if any(b[k]!=pub[k] for k in ['publicationId','projectId','planVersionId']):fail(422,'Receipt другой публикации')
            pub.update(status='SUCCEEDED' if b['status']=='APPLIED' else 'FAILED',externalReceipt=b['externalReceipt'])
            save(c,'publication',pub,a,p['portfolioId'],p['id']);return b
        pub.update(status='PENDING');save(c,'publication',pub,a,p['portfolioId'],p['id'])
        operation={'id':db.uid(),'operationId':None,'status':'PENDING','resultId':pub['id'],'errorCode':None};operation['operationId']=operation['id'];save(c,'operation',operation,a,p['portfolioId'],p['id']);return operation
    if op in {'getAttachment','deleteAttachment','downloadAttachment'}:
        at=get(c,'attachment',pp['attachmentId'],a,['R-01','R-02','R-03'])
        if op=='getAttachment':return at
        if op=='deleteAttachment':
            row=db.find(c,'attachment',at['id'])
            if req.headers.get('If-Match')!=f'"{row["revision"]}"':fail(412,'Вложение изменилось')
            allowed(a,['R-02','R-03'])
            if at['planVersionId'] and version(c,at['planVersionId'],a)['status']!='DRAFT':fail(409,'Вложения baseline неизменны')
            from .integrations import delete_file
            delete_file(at['id']);at['status']='DELETED';save(c,'attachment',at,a,db.find(c,'attachment',at['id'])['portfolio_id'],at['projectId']);return at
        if at['status']!='AVAILABLE':fail(409,'Файл недоступен')
        from .integrations import read_file
        return Response(read_file(at['id']),media_type=at['contentType'],headers={'Content-Disposition':'attachment; filename="download"'})
    fail(404,'Операция не найдена')

def trim(schema,value):
    if value is None:return None
    if '$ref' in schema:schema=SPEC['components']['schemas'][schema['$ref'].split('/')[-1]]
    if 'oneOf' in schema:
        chosen=next((s for s in schema['oneOf'] if s.get('properties',{}).get('entityType',{}).get('const')==value.get('entityType')),schema['oneOf'][0]);return trim(chosen,value)
    if isinstance(value,dict) and 'properties' in schema:
        return {k:trim(schema['properties'][k],v) for k,v in value.items() if k in schema['properties']}
    if isinstance(value,list) and 'items' in schema:return [trim(schema['items'],v) for v in value]
    return value

async def contract_handler(req:Request,definition):
    a=actor(req);op=definition['operationId'];body={}
    for param in definition.get('parameters',[]):
        source={'path':req.path_params,'query':req.query_params,'header':req.headers}[param['in']]
        value=source.get(param['name'])
        if value is None:
            if param.get('required'):fail(400,'Нужен '+param['name'])
            continue
        if param['schema'].get('type')=='integer':
            try:value=int(value)
            except ValueError:fail(422,'Нужно целое число')
        validate(param['schema'],value)
    if 'requestBody' in definition and op!='uploadAttachment':
        try:body=await req.json()
        except Exception:fail(400,'Неверный JSON')
        validate(definition['requestBody']['content']['application/json']['schema'],body)
    if op=='uploadAttachment':
        form=await req.form();file=form.get('file')
        if not file or not hasattr(file,'read'):fail(422,'Нужен файл')
        raw=await file.read(20*1024*1024+1)
        body={'ownerType':form.get('ownerType'),'ownerId':form.get('ownerId'),'fileName':file.filename,'contentType':file.content_type,'checksum':hashlib.sha256(raw).hexdigest()}
    code=next(int(x) for x in definition['responses'] if x.startswith('2'))
    content=definition['responses'][str(code)].get('content',{})
    schema=next(iter(content.values()),{}).get('schema')
    with db.engine.begin() as c:
        # Serialize domain commands, including cross-project capacity and idempotency.
        # Reads use repeatable snapshots for the batch materialization.
        if req.method!='GET':c.execute(select(db.schema_versions).with_for_update()).all()
        request_key=None
        if req.method!='GET':
            token=req.headers.get('Idempotency-Key')
            if not token:fail(400,'Нужен Idempotency-Key')
            request_key=hashlib.sha256((a.subject+req.method+req.url.path+token).encode()).hexdigest()
            fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
            prior=c.execute(select(db.requests).where(db.requests.c.id==request_key)).mappings().first()
            if prior:
                roles = {'createProject':['R-01','R-02','R-03'],'updateProject':['R-01','R-02','R-03'],
                 'archiveProject':['R-01','R-03'],'createVersion':['R-02','R-03'],'saveDraft':['R-02','R-03'],
                 'submitReview':['R-02','R-03'],'recordDecision':['R-01','R-04'],'activatePlan':['R-01'],
                 'calculateForecast':['R-02','R-03'],'createExport':['S-06'],'publicationReceipt':['S-03'],
                 'retryPublication':['R-06'],'uploadAttachment':['R-02','R-03'],'deleteAttachment':['R-02','R-03']}
                allowed(a,roles[op])
                required={'createExport':'reports.export','publicationReceipt':'publication.ack'}.get(op)
                if required and required not in a.scopes:fail(403,'Право отозвано')
                if prior['portfolio_id'] not in a.portfolios:fail(404,'Объект не найден')
                if 'R-03' in a.roles and not a.roles & {'R-01','R-02'} and prior['project_id'] and prior['project_id'] not in a.projects:
                    own=db.find(c,'project',prior['project_id'])
                    if not own or own['data']['managerSubject']!=a.subject:fail(404,'Объект не найден')
                if prior['fingerprint']!=fingerprint:fail(409,'Ключ использован с другим телом')
                result=money_filter(copy.deepcopy(prior['body']),a)
                headers={'ETag':f'"{result["revision"]}"'} if 'revision' in result else {}
                return JSONResponse(result,status_code=prior['status'],headers=headers)
        if op=='uploadAttachment':
            allowed(a,['R-02','R-03'])
            if body['ownerType'] not in {'PROJECT','PLAN_VERSION'}:fail(422,'Неверный владелец')
            if body['ownerType']=='PROJECT':p=project(c,body['ownerId'],a);vid=None
            else:
                v=version(c,body['ownerId'],a);p=project(c,v['projectId'],a);vid=v['id']
                if v['status']!='DRAFT':fail(409,'Baseline неизменна')
            if not raw or len(raw)>20*1024*1024:fail(422,'Размер файла 1..20 MiB')
            if body['contentType'] not in {'text/plain','application/pdf','image/png','image/jpeg'}:fail(422,'Тип файла запрещён')
            if body['contentType']=='text/plain':
                try:raw.decode('utf-8')
                except UnicodeDecodeError:fail(422,'Нужен UTF-8')
            signatures={'application/pdf':b'%PDF-','image/png':b'\x89PNG\r\n\x1a\n','image/jpeg':b'\xff\xd8\xff'}
            if body['contentType'] in signatures and not raw.startswith(signatures[body['contentType']]):fail(422,'Содержимое не соответствует MIME')
            identifier=db.uid()
            from .integrations import write_file
            write_file(identifier,raw,body['contentType'])
            result={'id':identifier,'projectId':p['id'] if vid is None else None,'planVersionId':vid,'fileName':Path(body['fileName'] or 'upload').name[:200],
                    'contentType':body['contentType'],'sizeBytes':len(raw),'status':'AVAILABLE','checksum':body['checksum']}
            save(c,'attachment',result,a,p['portfolioId'],p['id'])
        else:result=dispatch(c,op,req,a,body)
        if isinstance(result,Response):return result
        result=money_filter(trim(schema,result),a)
        validate(schema,result)
        if request_key:
            scope_id=result.get('portfolioId'); object_project=result.get('projectId')
            if scope_id is None:
                identifier=result.get('id') or result.get('operationId') or result.get('publicationId')
                row=c.execute(select(db.records).where(db.records.c.id==identifier)).mappings().first()
                if row:scope_id=row['portfolio_id'];object_project=row['project_id']
            c.execute(db.requests.insert().values(id=request_key,fingerprint=fingerprint,status=code,body=result,portfolio_id=scope_id,project_id=object_project))
            c.execute(db.audit.insert().values(id=db.uid(),subject=a.subject,project_id=result.get('projectId'),action=op,occurred_at=db.now(),details={'objectId':result.get('id'),'correlationId':req.state.correlation}))
        headers={}
        if 'revision' in result:headers['ETag']=f'"{result["revision"]}"'
        elif op=='getAttachment':headers['ETag']=f'"{db.find(c,"attachment",result["id"])["revision"]}"'
        return JSONResponse(result,status_code=code,headers=headers)

for path,methods in SPEC['paths'].items():
    for method,definition in methods.items():
        def factory(d):
            async def endpoint(request:Request):return await contract_handler(request,d)
            return endpoint
        app.add_api_route(path,factory(definition),methods=[method.upper()],name=definition['operationId'],include_in_schema=False)

# Additional UI/resource contracts are specified in runtime.openapi.json.
from .runtime import register
register(app)
app.mount('/',StaticFiles(directory=ROOT/'ui/app',html=True),name='web')
