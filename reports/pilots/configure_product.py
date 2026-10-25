"""Apply an operator-approved, nonsecret scope/link document to Reports only.

Run via launch.py run --rm -T --no-deps provision python configure_product.py
with a JSON document on stdin. No identity is inferred from names or equal IDs.
"""
import json
import os
import sys
from db import Database
from product_service import identity
from product_store import audit,packed
from report_engine import PM,TL,QA,Problem


def apply(db,payload):
    if not isinstance(payload,dict) or set(payload)-{'replaceScopesFor','scopes','links','disableSubjects','enableSubjects'}: raise ValueError('Invalid document')
    scopes=payload.get('scopes',[]);links=payload.get('links',[])
    if any(not isinstance(payload.get(k,[]),list) or len(payload.get(k,[]))>1000 for k in ['replaceScopesFor','scopes','links','disableSubjects','enableSubjects']): raise ValueError('Invalid list')
    for scope in scopes:
        if set(scope)-{'subject','role','projectId','employeeId'} or scope.get('role') not in {PM,TL,QA}: raise ValueError('Invalid scope')
        identity(scope['subject'])
        if not scope.get('projectId') and not scope.get('employeeId'): raise ValueError('Empty scope')
        if scope.get('projectId'): identity(scope['projectId'])
        if scope.get('employeeId'): identity(scope['employeeId'])
    for link in links:
        if set(link)!={'kind','sourceId','targetId'} or link['kind'] not in {'planning-project','planning-employee','hr-employee','tracker-status-category','employee-role'}: raise ValueError('Invalid link')
        if any(not isinstance(link[k],str) or not 1<=len(link[k])<=128 for k in ['sourceId','targetId']): raise ValueError('Invalid link identifier')
        if link['kind'] in {'planning-project','planning-employee','hr-employee'}: identity(link['targetId'])
        if link['kind']=='tracker-status-category' and link['targetId'] not in {'BACKLOG','WORKING','COMPLETED','ARCHIVED'}: raise ValueError('Invalid status category')
    for key in ['replaceScopesFor','disableSubjects','enableSubjects']:
        for subject in payload.get(key,[]): identity(subject)
    with db.transaction():
        for subject in payload.get('replaceScopesFor',[]): db.execute('DELETE FROM app.user_scope WHERE subject=?',(subject,))
        for scope in scopes:
            db.execute('INSERT INTO app.user_scope VALUES (?,?,?,?) ON CONFLICT DO NOTHING',(scope['subject'],scope['role'],scope.get('projectId',''),scope.get('employeeId','')))
        for link in links:
            db.execute('INSERT INTO app.entity_link VALUES (?,?,?) ON CONFLICT(kind,source_id) DO UPDATE SET target_id=excluded.target_id',(link['kind'],link['sourceId'],link['targetId']))
        for key,enabled in [('disableSubjects',0),('enableSubjects',1)]:
            for subject in payload.get(key,[]):
                db.execute("INSERT INTO app.principal VALUES (?,'[]','',0,?) ON CONFLICT(subject) DO UPDATE SET enabled=excluded.enabled",(subject,enabled))
        audit(db,'reports-operator','AUTHORIZATION_CONFIG',query=payload)
        if links:
            from star import refresh
            from product_store import stamp
            refresh(db,stamp())
    return {'scopes':len(scopes),'links':len(links),'disabled':len(payload.get('disableSubjects',[])),'enabled':len(payload.get('enableSubjects',[]))}


if __name__=='__main__':
    db=None
    try:
        raw=sys.stdin.buffer.read(262145)
        if len(raw)>262144: raise ValueError()
        payload=json.loads(raw)
        db=Database(os.environ['REPORTS_DATABASE_URL'])
        print(json.dumps({'passed':True,**apply(db,payload)}))
    except Exception:
        print(json.dumps({'passed':False,'error':'INVALID_CONFIG_OR_DATABASE_UNAVAILABLE'}));sys.exit(1)
    finally:
        if db: db.close()
