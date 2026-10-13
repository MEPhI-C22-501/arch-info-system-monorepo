"""UI/resource endpoints, isolated from the numbered external API contracts."""
import copy
import hashlib
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from contextlib import contextmanager
from sqlalchemy import select
from . import storage as db
from .auth import actor, DEMO_PROJECT, DEMO_PORTFOLIO
from .domain import fail, hours, check_resources


def register(app):
    from .app import allowed,get,project,version,save,changed,resource_inputs,money_filter,validate,ROOT

    @contextmanager
    def command_tx(req,a,b):
        key=req.headers.get('Idempotency-Key')
        if not key:fail(400,'Нужен Idempotency-Key')
        request_id=hashlib.sha256((a.subject+req.method+req.url.path+key).encode()).hexdigest()
        fingerprint=hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest()
        with db.engine.begin() as c:
            c.execute(select(db.schema_versions).with_for_update()).all()
            prior=c.execute(select(db.requests).where(db.requests.c.id==request_id)).mappings().first()
            if prior:
                if prior['portfolio_id'] not in a.portfolios:fail(404,'Объект не найден')
                if prior['project_id']:get(c,'project',prior['project_id'],a)
                if prior['fingerprint']!=fingerprint:fail(409,'Ключ использован с другим телом')
                yield c,JSONResponse(prior['body'],status_code=prior['status']),None
                return
            def complete(body,portfolio,project_id=None,status=200):
                c.execute(db.requests.insert().values(id=request_id,fingerprint=fingerprint,status=status,body=body,portfolio_id=portfolio,project_id=project_id))
                c.execute(db.audit.insert().values(id=db.uid(),subject=a.subject,project_id=project_id,action=req.url.path,occurred_at=db.now(),details={'correlationId':req.state.correlation}))
                return body
            yield c,None,complete

    @app.get('/api/v1/me')
    def identity(req:Request):
        a=actor(req)
        return {'subject':a.subject,'roles':sorted(a.roles),'portfolios':sorted(a.portfolios),'projects':sorted(a.projects),'scopes':sorted(a.scopes)}

    @app.get('/api/v1/workspace')
    def workspace(req:Request):
        a=actor(req)
        with db.engine.begin() as c:
            pid=req.query_params.get('projectId',DEMO_PROJECT)
            p=get(c,'project',pid,a)
            if 'R-05' in a.roles:
                v=get(c,'plan',p['activePlanVersionId'],a) if p['activePlanVersionId'] else None
                allocations=[x for x in v['allocations'] if x['employeeId'] in a.employees and x['status']=='CONFIRMED'] if v else []
                if v and not allocations:fail(404,'Нет собственных назначений')
                return {'projectId':pid,'name':p['name'],'goal':p['goal'],'role':next(iter(a.roles)),'allocations':allocations,'status':v['status'] if v else 'DRAFT','version':v['versionNumber'] if v else 0,'baseline':None,'attachment':False,'events':[]}
            pubs=[r['data'] for r in db.all_rows(c,'publication',project=pid)]
            if 'R-06' in a.roles:
                return {'projectId':pid,'name':'Журнал обмена','role':'R-06','status':'ACTIVE','version':0,'publication':pubs[-1]['status'] if pubs else 'PENDING',
                        'publicationId':pubs[-1]['id'] if pubs else None,'baseline':{'version':0} if pubs else None,'events':[f"{x['publicationId']} · {x['status']}" for x in pubs],'attachment':False}
            allowed(a,['R-01','R-02','R-03','R-04'])
            plans=[r['data'] for r in db.all_rows(c,'plan',project=pid)]
            v=max(plans,key=lambda x:x['versionNumber']) if plans else None
            av=[r['data'] for r in db.all_rows(c,'availability',p['portfolioId']) if r['data']['employeeId'] in a.employees]
            base=db.find(c,'plan',p['activePlanVersionId']) if p['activePlanVersionId'] else None
            base=base['data'] if base else None
            tasks=[r['data'] for r in db.all_rows(c,'task',project=pid)]
            fcs=[r['data'] for r in db.all_rows(c,'forecast',project=pid)]
            at=[r['data'] for r in db.all_rows(c,'attachment',project=pid) if r['data']['status']=='AVAILABLE']
            events=[r['action'] for r in c.execute(select(db.audit).where(db.audit.c.project_id==pid).order_by(db.audit.c.occurred_at)).mappings()]
            allocation=next((x for x in v['allocations'] if x['employeeId']=='employees/demo-1'),{}) if v else {}
            availability=next((x for x in av if x['employeeId']=='employees/demo-1' and x['date']=='2026-10-05'),{})
            response={'projectId':pid,'portfolioId':p['portfolioId'],'projectRevision':p['revision'],'finalApprover':get(c,'portfolio',p['portfolioId'],a).get('ownerSubject'),'name':p['name'],'goal':p['goal'],'role':next(iter(a.roles)),
                'versionId':v['id'] if v else None,'version':v['versionNumber'] if v else 0,'revision':v['revision'] if v else 0,
                'contentRevision':v['contentRevision'] if v else 0,'reviewRound':v['reviewRound'] if v else 0,'status':v['status'] if v else 'DRAFT',
                'scenario':v['kind']=='SCENARIO' if v else False,'demand':sum(x['hours'] for x in v['demands']) if v else 0,
                'allocation':allocation.get('hours',0),'availability':availability.get('availableHours',0),
                'confirmed':all(x['status']=='CONFIRMED' for x in v['allocations']) if v and v['allocations'] else False,
                'date':next((x['finish'] for x in v['items'] if x['type']=='MILESTONE'),'2026-10-09') if v else '2026-10-09',
                'baseline':{'version':base['versionNumber'],'demand':sum(x['hours'] for x in base['demands']),'allocation':sum(x['hours'] for x in base['allocations'] if x['employeeId']=='employees/demo-1'),'date':next((x['finish'] for x in base['items'] if x['type']=='MILESTONE'),'2026-10-09')} if base else None,
                'publication':pubs[-1]['status'] if pubs else 'PENDING','publicationId':pubs[-1]['id'] if pubs else None,
                'attachment':bool(at),'attachments':at,'events':events[-20:],
                'actualHours':sum(x['actualHours'] for x in tasks if not x['isDeleted']),
                'forecast':max([f for f in fcs if v and f['planVersionId']==v['id']],key=lambda x:x['calculatedAt'],default=None),
                'availabilityId':availability.get('id'),'allocationId':allocation.get('id')}
            if 'R-04' in a.roles:
                response['attachments']=[];response['attachment']=False;response['forecast']=None;response['actualHours']=None;response['events']=[]
            return money_filter(response,a)

    @app.put('/api/v1/availability/{availabilityId}')
    async def availability(req:Request):
        a=actor(req);allowed(a,['R-04']);b=await req.json()
        validate(json.loads((ROOT/'docs/contracts/openapi.json').read_text())['components']['schemas']['Availability'],b)
        if b['id']!=req.path_params['availabilityId'] or b['employeeId'] not in a.employees:fail(403,'Чужой ресурс')
        if hours(b['nominalHours'])-hours(b['absenceHours'])!=hours(b['availableHours']):fail(422,'Норма минус отсутствие не равна доступности')
        if b['nominalHours']>24:fail(422,'Норма превышает 24 часа')
        with command_tx(req,a,b) as (c,cached,complete):
            if cached:return cached
            old=get(c,'availability',b['id'],a)
            if old['employeeId']!=b['employeeId'] or old['date']!=b['date']:fail(422,'ID относится к другому ресурсу/дате')
            match=req.headers.get('If-Match');row=db.find(c,'availability',b['id'])
            if match!=f'"{row["revision"]}"':fail(412,'Доступность изменилась')
            db.put(c,'availability',b,row['portfolio_id'],expected=row['revision'])
            for r in db.all_rows(c,'plan',row['portfolio_id']):
                v=copy.deepcopy(r['data'])
                if v['status'] not in {'DRAFT','ON_REVIEW'}:continue
                related=[x for x in v['allocations'] if x['employeeId']==b['employeeId'] and x['date']==b['date']]
                if not related:continue
                for x in related:x['status']='PROPOSED'
                v.update(status='DRAFT',revision=v['revision']+1,contentRevision=v['contentRevision']+1,decisions=[])
                db.put(c,'plan',v,r['portfolio_id'],r['project_id'])
            complete(b,row['portfolio_id'])
            return JSONResponse(b,headers={'ETag':f'"{row["revision"]+1}"'})

    @app.get('/api/v1/availability')
    def availability_list(req:Request):
        a=actor(req);allowed(a,['R-04'])
        with db.engine.begin() as c:
            return [{'data':r['data'],'revision':r['revision']} for r in db.all_rows(c,'availability') if r['portfolio_id'] in a.portfolios and r['data']['employeeId'] in a.employees]

    @app.post('/api/v1/versions/{versionId}/confirm-resources')
    def confirm_resources(req:Request):
        a=actor(req);allowed(a,['R-04'])
        with command_tx(req,a,{}) as (c,cached,complete):
            if cached:return cached
            v=version(c,req.path_params['versionId'],a,['R-04']);p=project(c,v['projectId'],a,['R-04'])
            if v['status']!='DRAFT':fail(409,'Подтверждается только черновик')
            for x in v['allocations']:
                if x['employeeId'] in a.employees:x['status']='CONFIRMED'
            check_resources(v,*resource_inputs(c,v))
            v['contentRevision']+=1;changed(c,'plan',v,req,a)
            return complete({'revision':v['revision'],'contentRevision':v['contentRevision'],'status':v['status']},p['portfolioId'],p['id'])

    @app.put('/api/v1/versions/{versionId}/forecast-inputs')
    async def forecast_inputs(req:Request):
        a=actor(req);allowed(a,['R-02','R-03']);b=await req.json()
        if set(b)-{'etc','rate','currencyCode'}:fail(422,'Неизвестные поля')
        if any(not isinstance(b.get(k),(int,float)) or b[k]<0 for k in ['etc']):fail(422,'ETC >= 0')
        validate(json.loads((ROOT/'docs/contracts/runtime.openapi.json').read_text())['paths']['/api/v1/versions/{versionId}/forecast-inputs']['put']['requestBody']['content']['application/json']['schema'],b)
        if {'rate','currencyCode'} & set(b) and 'cost.write' not in a.scopes:fail(403,'Нужен cost.write')
        if 'rate' in b and (not isinstance(b['rate'],(int,float)) or b['rate']<0 or not b.get('currencyCode')):fail(422,'Ставка >= 0 и валюта обязательны')
        with command_tx(req,a,b) as (c,cached,complete):
            if cached:return cached
            v=version(c,req.path_params['versionId'],a);p=project(c,v['projectId'],a)
            old=db.find(c,'forecast_input',v['id'])
            inputs=old['data'] if old else {}
            save(c,'forecast_input',{**inputs,'id':v['id'],**b,'author':a.subject,'asOf':db.now()},a,p['portfolioId'],p['id'])
            return complete({'status':'saved'},p['portfolioId'],p['id'])

    @app.post('/api/v1/integrations/task-events')
    async def task_events(req:Request):
        a=actor(req);allowed(a,['S-03'])
        if 'facts.write' not in a.scopes:fail(403,'Нужен facts.write')
        b=await req.json();name=b.get('eventType')
        if name not in {'TaskCreated','TaskChanged','TimeLogged','TaskDeleted'}:fail(422,'Неверный тип события')
        schema=json.loads((ROOT/f'docs/contracts/events/{name}.schema.json').read_text());validate(schema,b)
        fingerprint=hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest()
        with command_tx(req,a,b) as (c,cached,complete):
            if cached:return cached
            p=project(c,b['projectId'],a,['S-03'])
            previous=db.find(c,'inbox',b['eventId'])
            if previous:
                if previous['data']['hash']!=fingerprint:fail(409,'Повтор eventId с другим payload')
                return complete({'status':'duplicate'},p['portfolioId'],p['id'])
            t=b['payload'];identifier=hashlib.sha256(t['externalTaskId'].encode()).hexdigest()[:32]
            old=db.find(c,'task',identifier)
            if old and old['project_id']!=p['id']:fail(409,'Задача уже связана с другим проектом')
            if old and old['data']['sourceRevision']==t['sourceRevision'] and {k:v for k,v in old['data'].items() if k!='id'}!=t:fail(409,'Та же sourceRevision с другим срезом')
            if not old or t['sourceRevision']>old['data']['sourceRevision']:
                save(c,'task',{'id':identifier,**t},a,p['portfolioId'],p['id'])
            save(c,'inbox',{'id':b['eventId'],'hash':fingerprint},a,p['portfolioId'],p['id'])
            return complete({'status':'accepted'},p['portfolioId'],p['id'])

    @app.get('/api/v1/portfolios')
    def portfolios(req:Request):
        a=actor(req);allowed(a,['R-01','R-02','R-03'])
        with db.engine.begin() as c:return [r['data'] for r in db.all_rows(c,'portfolio') if r['id'] in a.portfolios]

    @app.post('/api/v1/portfolios/{portfolioId}/programs',status_code=201)
    async def create_program(req:Request):
        a=actor(req);allowed(a,['R-01']);b=await req.json()
        if set(b)!={'code','name','goal'} or any(not isinstance(x,str) or not x.strip() for x in b.values()):fail(422,'Нужны code/name/goal')
        with command_tx(req,a,b) as (c,cached,complete):
            if cached:return cached
            pid=req.path_params['portfolioId'];get(c,'portfolio',pid,a)
            if any(r['data']['code']==b['code'] for r in db.all_rows(c,'program',pid)):fail(409,'Код программы занят')
            return complete(save(c,'program',{'id':db.uid(),'portfolioId':pid,'revision':1,'status':'ACTIVE',**b},a,pid),pid,status=201)
