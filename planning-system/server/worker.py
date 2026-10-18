"""Durable publication delivery. Mock receipts are always marked as mock."""
import copy
import json
import logging
import os
import time
import httpx
from sqlalchemy import select
from . import storage as db

log=logging.getLogger('planning.worker')

def tt_payload(plan):
    """Candidate D-01 mapping: PS FEATURE -> planned TT TASK. Must be approved."""
    epics=[]
    for item in plan['items']:
        if item['type']!='EPIC':continue
        tasks=[{'externalId':x['logicalItemId'],'title':x['name'],'startDate':x['start'],'dueDate':x['finish'],'plannedHours':x['plannedHours']}
               for x in plan['items'] if x['type']=='FEATURE' and x['parentItemId']==item['id']]
        epics.append({'externalId':item['logicalItemId'],'title':item['name'],'startDate':item['start'],'dueDate':item['finish'],'tasks':tasks})
    return {'version':plan['versionNumber'],'title':plan['name'],'startDate':plan['horizonStart'],'dueDate':plan['horizonEnd'],'epics':epics}

def deliver(pub,transport=None):
    if os.environ.get('INTEGRATION_MODE','real')=='mock':
        if os.environ.get('APP_ENV')!='development':raise RuntimeError('Mock requires development')
        return 'mock:'+pub['id']
    if os.environ.get('TT_MAPPING_APPROVED')!='true':raise RuntimeError('D-01 mapping not approved')
    base=os.environ['TT_BASE_URL'].rstrip('/')
    if not base.startswith('https://'):raise RuntimeError('TT TLS required')
    with httpx.Client(timeout=10,transport=transport) as client:
        r=client.put(base+'/planning/projects/'+pub['projectId'],json=tt_payload(pub['plan']),headers={'Authorization':'Bearer '+os.environ['TT_TOKEN'],'Idempotency-Key':pub['idempotencyKey']})
        r.raise_for_status();receipt=r.json()
    if receipt['externalProjectId']!=pub['projectId'] or receipt['version']!=pub['plan']['versionNumber'] or receipt['status'] not in {'applied','already-applied'}:
        raise RuntimeError('Unexpected TT receipt')
    return json.dumps(receipt,sort_keys=True)

def tick():
    with db.engine.begin() as c:
        c.execute(select(db.schema_versions).with_for_update()).all()
        for row in db.all_rows(c,'publication'):
            pub=copy.deepcopy(row['data'])
            if pub['status']!='PENDING' or pub.get('nextAttempt',0)>time.time():continue
            p=db.find(c,'project',pub['projectId'])
            if not p or p['data']['activePlanVersionId']!=pub['planVersionId']:
                pub.update(status='FAILED',lastError='SUPERSEDED');db.put(c,'publication',pub,row['portfolio_id'],row['project_id']);continue
            pub['attempts']+=1
            try:
                pub.update(externalReceipt=deliver(pub),status='SUCCEEDED',integrationMode=os.environ.get('INTEGRATION_MODE','real'),lastError=None)
            except Exception as exc:
                pub.update(status='FAILED' if pub['attempts']>=5 else 'PENDING',lastError=type(exc).__name__,nextAttempt=time.time()+min(2**pub['attempts'],60))
                log.warning('publication failed id=%s attempt=%s type=%s',pub['id'],pub['attempts'],type(exc).__name__)
            db.put(c,'publication',pub,row['portfolio_id'],row['project_id'])
        for row in db.all_rows(c,'operation'):
            op=copy.deepcopy(row['data'])
            if op['status']!='PENDING' or not op.get('resultId'):continue
            pub=db.find(c,'publication',op['resultId'])
            if pub and pub['data']['status'] in {'SUCCEEDED','FAILED'}:
                op.update(status=pub['data']['status'],errorCode=pub['data'].get('lastError'))
                db.put(c,'operation',op,row['portfolio_id'],row['project_id'])
        db.put(c,'worker_health',{'id':'worker','lastTick':db.now()},'technical')

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO);db.migrate()
    while True:
        try:tick()
        except Exception:log.exception('worker tick failed')
        time.sleep(2)
