"""Reports API application: owned objects, exports, schedules and append-only audit."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from delivery import encode, next_run, printable
from product_store import audit, local_principal, notify, packed, stamp
from report_engine import AD, AN, MB, PM, QA, TL, ACCESS, Engine, Problem, Scope, definition, instant, roles, validate_query


def identity(value):
    try:
        if str(uuid.UUID(value))!=value: raise ValueError()
        return value
    except (ValueError,TypeError,AttributeError): raise Problem(422,'INVALID_PARAMETER') from None


def page(rows,params):
    try:
        p=int(params.get('page','1')); size=int(params.get('pageSize','100'))
        if p<1 or not 1<=size<=200: raise ValueError()
    except (ValueError,TypeError): raise Problem(422,'INVALID_PARAMETER') from None
    return {'items':rows[(p-1)*size:p*size],'total':len(rows)}


class Service:
    def __init__(self,db,claims,correlation=None,resolver=None):
        self.db,self.claims=db,claims;self.subject=claims['sub'];self.roles=roles(claims)
        self.correlation=correlation or str(uuid.uuid4())
        if not self.roles & {PM,TL,QA,MB,AN,AD}: raise Problem(403,'FORBIDDEN')
        self.resolve=resolver or (lambda subject:local_principal(db,subject))
        principal=db.execute('SELECT enabled FROM app.principal WHERE subject=?',(self.subject,)).fetchone()
        if principal and not principal[0]: raise Problem(403,'FORBIDDEN')

    def owned(self,table,key,columns='*'):
        # table/columns are internal constants, never supplied by callers.
        row=self.db.execute(f'SELECT {columns} FROM app.{table} WHERE id=? AND owner_sub=?',(key,self.subject)).fetchone()
        if not row: raise Problem(404,'NOT_FOUND')
        return row

    def query(self,rid,payload):
        if payload.get('viewId'):
            row=self.owned('saved_view',identity(payload['viewId']),'report_id,query')
            if row[0]!=rid: raise Problem(422,'INVALID_PARAMETER')
            saved=json.loads(row[1]);saved.update({k:v for k,v in payload.items() if k!='viewId' and v!={}});payload=saved
        return Engine(self.db).query(rid,self.claims,payload)

    def export(self,key):
        row=self.owned('export_job',identity(key),'id,report_id,format,status,created_at,expires_at,row_count,error')
        return dict(zip(['exportId','reportId','format','status','createdAt','expiresAt','rowCount','error'],row))

    def create_export(self,rid,query,fmt,owner=None,ceiling=None,kind=None,subscription=None):
        if fmt not in {'csv','xlsx'}: raise Problem(422,'INVALID_PARAMETER')
        Scope(self.db,self.claims,rid); validate_query(rid,query)
        queued=self.db.execute("SELECT COUNT(*) FROM app.export_job WHERE owner_sub=? AND status='QUEUED'",(owner or self.subject,)).fetchone()[0]
        if queued>=20: raise Problem(429,'QUEUE_LIMIT')
        key=str(uuid.uuid4()); now=datetime.now(timezone.utc)
        stored=dict(query)
        if ceiling: stored['_ceilingOwner']=ceiling
        if kind: stored['_notificationKind']=kind
        if subscription: stored['_subscriptionId']=subscription
        self.db.execute('''INSERT INTO app.export_job(id,owner_sub,report_id,query,format,status,created_at,expires_at)
            VALUES (?,?,?,?,?,'QUEUED',?,?)''',(key,owner or self.subject,rid,packed(stored),fmt,now.isoformat(),(now+timedelta(hours=24)).isoformat()))
        return key

    def download(self,key):
        self.export(key)
        row=self.owned('export_job',key,'report_id,query,format,status,expires_at,fingerprint,file_data,checksum')
        rid,query,fmt,status,expires,fingerprint,data,checksum=row
        if instant(expires)<=datetime.now(timezone.utc): raise Problem(410,'GONE')
        if status!='COMPLETED' or data is None: raise Problem(409,'NOT_READY')
        scope=Scope(self.db,self.claims,rid); expected=scope.fingerprint()
        if fingerprint!=hashlib.sha256(expected.encode()).hexdigest(): raise Problem(403,'FORBIDDEN')
        raw=bytes(data)
        if hashlib.sha256(raw).hexdigest()!=checksum: raise Problem(503,'FILE_INTEGRITY_ERROR')
        mime='text/csv; charset=utf-8' if fmt=='csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return raw,{'Content-Type':mime,'Content-Disposition':f'attachment; filename="{rid}-{key}.{fmt}"'}

    def subscription(self,key,admin=False):
        identity(key)
        row=self.db.execute('SELECT owner_sub,payload,status,version,next_run_at FROM app.subscription WHERE id=?',(key,)).fetchone()
        if not row or (row[0]!=self.subject and not (admin and AD in self.roles)): raise Problem(404,'NOT_FOUND')
        return dict(json.loads(row[1]),subscriptionId=key,status=row[2],version=str(row[3]),nextRunAt=row[4])

    def validate_subscription(self,payload):
        if not self.roles & {PM,TL,QA,AN}: raise Problem(403,'FORBIDDEN')
        if not isinstance(payload,dict) or set(payload)-{'reportId','query','schedule','format','recipients','validUntil'}: raise Problem(422,'INVALID_PARAMETER')
        try:
            Scope(self.db,self.claims,payload['reportId']);validate_query(payload['reportId'],payload['query'])
            if payload['format'] not in {'csv','xlsx'}: raise ValueError()
            recipients=payload['recipients']
            if not isinstance(recipients,list) or not 1<=len(recipients)<=20 or len(set(recipients))!=len(recipients): raise ValueError()
            for recipient in recipients: identity(recipient)
            if payload.get('validUntil'):
                from datetime import date
                if date.fromisoformat(payload['validUntil']).isoformat()!=payload['validUntil']: raise ValueError()
            return next_run(payload['schedule'],datetime.now(timezone.utc))
        except (KeyError,TypeError,ValueError): raise Problem(422,'INVALID_PARAMETER') from None

    def db_page(self,table,where,args,columns,order,params):
        try:
            current=int(params.get('page','1'));size=int(params.get('pageSize','100'))
            if current<1 or not 1<=size<=200: raise ValueError()
        except (ValueError,TypeError): raise Problem(422,'INVALID_PARAMETER') from None
        count=self.db.execute(f'SELECT COUNT(*) FROM app.{table} WHERE '+where,args).fetchone()[0]
        rows=self.db.execute(f'SELECT {columns} FROM app.{table} WHERE '+where+f' ORDER BY {order} LIMIT ? OFFSET ?',tuple(args)+(size,(current-1)*size)).fetchall()
        return rows,count

    def route(self,method,path,body=None,params=None,headers=None):
        params=params or {};headers={k.lower():v for k,v in (headers or {}).items()};parts=path.strip('/').split('/')
        if set(params)-{'page','pageSize','reportId'}: raise Problem(422,'INVALID_PARAMETER')
        if parts==['reports'] and method=='GET':
            items=[definition(f'R-{n:02d}') for n in range(1,12) if self.roles & ACCESS[n] or AD in self.roles]
            return 200,{'items':items},{}
        if parts==['freshness'] and method=='GET':
            values=[]
            for source in ['tracker','planning','reference','qa']:
                row=self.db.execute('SELECT data_as_of FROM etl.source_state WHERE source=?',(source,)).fetchone()
                last_failure=self.db.execute("SELECT MAX(completed_at) FROM etl.batch WHERE source=? AND status='REJECTED'",(source,)).fetchone()[0]
                loaded=self.db.execute('SELECT loaded_at FROM etl.source_state WHERE source=?',(source,)).fetchone()
                lag=int((datetime.now(timezone.utc)-instant(row[0])).total_seconds()) if row and instant(row[0]) else None
                values.append({'source':{'tracker':'task-tracker','planning':'planning-system','reference':'reference-manager','qa':'qa-system'}[source],
                               'stream':'reports','dataAsOf':row[0] if row else None,'lagSeconds':lag,'thresholdSeconds':3600,'state':('FRESH' if lag is not None and 0<=lag<=3600 and (not last_failure or last_failure<=loaded[0]) else 'STALE') if row else 'UNKNOWN'})
            return 200,{'items':values},{}
        if parts==['audit'] and method=='GET':
            if AD not in self.roles: raise Problem(403,'FORBIDDEN')
            cols=['auditId','actor','action','reportId','resourceId','queryHash','result','at','correlationId']
            rows,count=self.db_page('audit_log','1=1',(),'*','at DESC,id',params)
            return 200,{'items':[dict(zip(cols,row)) for row in rows],'total':count},{}
        if len(parts)>=2 and parts[0]=='reports':
            rid=parts[1];n=int(rid[2:]) if rid in {f'R-{i:02d}' for i in range(1,12)} else 0
            if not n: raise Problem(404,'NOT_FOUND')
            if len(parts)==2 and method=='GET':
                if not (self.roles & ACCESS[n] or AD in self.roles): raise Problem(403,'FORBIDDEN')
                return 200,definition(rid),{}
            if len(parts)==3 and method=='POST' and parts[2] in {'query','drilldown','print'}:
                if not isinstance(body,dict): raise Problem(422,'INVALID_PARAMETER')
                if parts[2]=='drilldown' and 'path' not in body: raise Problem(422,'INVALID_PARAMETER')
                result=self.query(rid,body)
                if parts[2]=='print':
                    return 200,printable(result,body,self.subject),{'Content-Type':'text/html; charset=utf-8',
                        'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"}
                return 200,result,{}
        if parts==['views']:
            if method=='GET':
                rows=self.db.execute('SELECT id,report_id,name,query,created_at FROM app.saved_view WHERE owner_sub=? ORDER BY created_at,id',(self.subject,)).fetchall()
                return 200,{'items':[{'viewId':r[0],'reportId':r[1],'name':r[2],'query':json.loads(r[3]),'createdAt':r[4]} for r in rows if not params.get('reportId') or r[1]==params['reportId']]},{}
            if method=='POST':
                if not isinstance(body,dict) or set(body)!={'reportId','name','query'} or not isinstance(body.get('name'),str) or not 1<=len(body['name'])<=120: raise Problem(422,'INVALID_PARAMETER')
                Scope(self.db,self.claims,body['reportId']);validate_query(body['reportId'],body['query'])
                key=str(uuid.uuid4());at=stamp()
                self.db.execute('INSERT INTO app.saved_view VALUES (?,?,?,?,?,?)',(key,self.subject,body['reportId'],body['name'],packed(body['query']),at))
                return 201,dict(body,viewId=key,createdAt=at),{}
        if len(parts)==2 and parts[0]=='views':
            key=identity(parts[1]);row=self.owned('saved_view',key,'report_id,name,query,created_at')
            if method=='GET': return 200,{'viewId':key,'reportId':row[0],'name':row[1],'query':json.loads(row[2]),'createdAt':row[3]},{}
            if method=='DELETE':
                self.db.execute('DELETE FROM app.saved_view WHERE id=?',(key,));return 204,None,{}
            if method=='PATCH':
                if not isinstance(body,dict) or set(body)!={'reportId','name','query'} or not isinstance(body['name'],str) or not 1<=len(body['name'])<=120: raise Problem(422,'INVALID_PARAMETER')
                Scope(self.db,self.claims,body['reportId']);validate_query(body['reportId'],body['query'])
                self.db.execute('UPDATE app.saved_view SET report_id=?,name=?,query=? WHERE id=?',(body['reportId'],body['name'],packed(body['query']),key))
                return self.route('GET',path)
        if parts==['exports']:
            if method=='GET':
                ids,count=self.db_page('export_job','owner_sub=?',(self.subject,),'id','created_at DESC,id',params)
                return 200,{'items':[self.export(key[0]) for key in ids],'total':count},{}
            if method=='POST':
                if not isinstance(body,dict) or set(body)-{'reportId','query','cube','format'} or not body.get('format'): raise Problem(422,'INVALID_PARAMETER')
                if 'cube' in body:
                    if not isinstance(body['cube'],dict) or 'reportId' in body or set(body['cube'])-{'cubeName','measures','dimensions','filters'} or body['cube'].get('cubeName')!='time_logs' or body['cube'].get('measures')!=['M-01']:
                        raise Problem(422,'INVALID_PARAMETER')
                    if not self.roles & {PM,AN}: raise Problem(403,'FORBIDDEN')
                    rid='R-01';query={'params':body['cube'].get('filters',{}),'slice':body['cube'].get('dimensions',['project'])}
                else: rid,query=body.get('reportId'),body.get('query')
                key=self.create_export(rid,query,body['format'])
                return 202,self.export(key),{}
        if len(parts) in {2,3} and parts[0]=='exports' and method=='GET':
            if len(parts)==2: return 200,self.export(parts[1]),{}
            if parts[2]=='file':
                raw,extra=self.download(identity(parts[1]));return 200,raw,extra
        if parts==['subscriptions']:
            if method=='GET':
                ids=[r[0] for r in self.db.execute("SELECT id FROM app.subscription WHERE owner_sub=? AND status!='COMPLETED' ORDER BY created_at,id",(self.subject,))]
                return 200,{'items':[self.subscription(key) for key in ids]},{}
            if method=='POST':
                due=self.validate_subscription(body);key=str(uuid.uuid4())
                self.db.execute("INSERT INTO app.subscription VALUES (?,?,?,'ACTIVE',1,?,?)",(key,self.subject,packed(body),due,stamp()))
                return 201,self.subscription(key),{'ETag':'1'}
        if len(parts) in {2,3} and parts[0]=='subscriptions':
            key=identity(parts[1]);current=self.subscription(key,admin=method=='PATCH')
            if len(parts)==3 and parts[2]=='deliveries' and method=='GET':
                rows,count=self.db_page('delivery','subscription_id=?',(key,),'payload','run_at DESC',params)
                return 200,{'items':[json.loads(r[0]) for r in rows],'total':count},{}
            if len(parts)==2:
                if method=='GET': return 200,current,{'ETag':current['version']}
                if method=='DELETE':
                    self.db.execute("UPDATE app.subscription SET status='COMPLETED',version=version+1,next_run_at=NULL WHERE id=?",(key,));return 204,None,{}
                if method=='PATCH':
                    if headers.get('if-match','').strip('"')!=current['version']: raise Problem(409,'CONFLICT')
                    if not isinstance(body,dict) or not body or set(body)-{'status','schedule','recipients','validUntil'}: raise Problem(422,'INVALID_PARAMETER')
                    owner=self.db.execute('SELECT owner_sub FROM app.subscription WHERE id=?',(key,)).fetchone()[0]
                    if owner!=self.subject and set(body)!={'status'}: raise Problem(403,'FORBIDDEN')
                    status=body.get('status',current['status'])
                    if status not in {'ACTIVE','PAUSED','COMPLETED'}: raise Problem(422,'INVALID_PARAMETER')
                    if current['status']=='COMPLETED' and status!='COMPLETED': raise Problem(409,'CONFLICT')
                    payload={k:v for k,v in current.items() if k not in {'subscriptionId','status','version','nextRunAt'}}
                    payload.update({k:v for k,v in body.items() if k!='status'})
                    due=self.validate_subscription(payload) if owner==self.subject else next_run(payload['schedule'],datetime.now(timezone.utc))
                    changed=self.db.execute('UPDATE app.subscription SET payload=?,status=?,version=version+1,next_run_at=? WHERE id=? AND version=?',
                        (packed(payload),status,due if status=='ACTIVE' else None,key,int(current['version']))).rowcount
                    if changed!=1: raise Problem(409,'CONFLICT')
                    return 200,self.subscription(key,admin=True),{'ETag':str(int(current['version'])+1)}
        if parts==['notifications'] and method=='GET':
            rows,count=self.db_page('notification','recipient_sub=?',(self.subject,),'id,kind,export_id,snapshot_id,created_at,read_at','created_at DESC,id',params)
            return 200,{'items':[dict(zip(['notificationId','kind','exportId','snapshotId','createdAt','readAt'],r)) for r in rows],'total':count},{}
        if len(parts)==2 and parts[0]=='notifications' and method=='PATCH':
            key=identity(parts[1])
            if not isinstance(body,dict) or set(body)!={'read'} or type(body['read']) is not bool: raise Problem(422,'INVALID_PARAMETER')
            changed=self.db.execute('UPDATE app.notification SET read_at=? WHERE id=? AND recipient_sub=?',(stamp() if body['read'] else None,key,self.subject)).rowcount
            if not changed: raise Problem(404,'NOT_FOUND')
            r=self.db.execute('SELECT id,kind,export_id,snapshot_id,created_at,read_at FROM app.notification WHERE id=?',(key,)).fetchone()
            return 200,dict(zip(['notificationId','kind','exportId','snapshotId','createdAt','readAt'],r)),{}
        raise Problem(404,'NOT_FOUND')


def complete_export(db,key,resolver):
    row=db.execute("SELECT owner_sub,report_id,query,format,expires_at FROM app.export_job WHERE id=? AND status='QUEUED'",(key,)).fetchone()
    if not row: return False
    subject,rid,raw,fmt,expires=row
    if instant(expires)<=datetime.now(timezone.utc):
        db.execute("UPDATE app.export_job SET status='EXPIRED',file_data=NULL WHERE id=?",(key,));return False
    query=json.loads(raw);ceiling_owner=query.pop('_ceilingOwner',None);kind=query.pop('_notificationKind','EXPORT_READY');subscription=query.pop('_subscriptionId',None)
    db.execute('SAVEPOINT reports_export')
    try:
        claims=resolver(subject);scope=Scope(db,claims,rid);ceiling=Scope(db,resolver(ceiling_owner),rid) if ceiling_owner else None
        result=Engine(db).query(rid,claims,query,limit=100000,ceiling=ceiling)
        data,_=encode(result,query,subject,fmt)
        if len(data)>20*1024*1024: raise Problem(422,'RESULT_TOO_LARGE')
        fingerprint=scope.fingerprint()
        db.execute("UPDATE app.export_job SET status='COMPLETED',fingerprint=?,row_count=?,checksum=?,file_data=? WHERE id=?",
                   (hashlib.sha256(fingerprint.encode()).hexdigest(),len(result['rows']),hashlib.sha256(data).hexdigest(),data,key))
        notify(db,subject,kind,key)
        from event_outbox import enqueue
        if subscription:
            enqueue(db,'ScheduledReportReady',subject,{'subscriptionId':subscription,'snapshotId':key,'reportId':rid,
                'dataAsOf':min(f['dataAsOf'] for f in result['freshness']),'viewPath':'/snapshots/'+key},subscription)
        else:
            enqueue(db,'ReportExportReady',subject,{'exportId':key,'reportId':rid,'format':fmt,'rowCount':len(result['rows']),
                'expiresAt':expires,'downloadPath':'/api/v1/exports/'+key+'/file'})
        audit(db,subject,'EXPORT_COMPLETED',rid,query,resource=key)
        db.execute('RELEASE SAVEPOINT reports_export')
        return True
    except Exception:
        db.execute('ROLLBACK TO SAVEPOINT reports_export')
        db.execute('RELEASE SAVEPOINT reports_export')
        db.execute("UPDATE app.export_job SET status='FAILED',error='AUTHORIZATION_OR_DATA_UNAVAILABLE',file_data=NULL WHERE id=?",(key,))
        audit(db,subject,'EXPORT_FAILED',rid,result='DENIED_OR_UNAVAILABLE',resource=key)
        return False


def tick(db,resolver=None,now=None):
    now=now or datetime.now(timezone.utc);resolve=resolver or (lambda subject:local_principal(db,subject))
    with db.transaction():
        if db.sqlite: db.execute('BEGIN IMMEDIATE')
        elif not db.execute("SELECT pg_try_advisory_xact_lock(hashtext('reports-product-jobs'))").fetchone()[0]: return {'busy':True}
        db.execute("UPDATE app.export_job SET status='EXPIRED',file_data=NULL WHERE expires_at<=? AND status!='EXPIRED'",(now.isoformat(),))
        ids=[r[0] for r in db.execute("SELECT id FROM app.export_job WHERE status='QUEUED' ORDER BY created_at,id LIMIT 10")]
        for key in ids: complete_export(db,key,resolve)
        due=db.execute("SELECT id,owner_sub,payload,next_run_at FROM app.subscription WHERE status='ACTIVE' AND next_run_at<=? ORDER BY next_run_at,id LIMIT 10",(now.isoformat(),)).fetchall()
        for key,owner,raw,scheduled in due:
            payload=json.loads(raw);rid=payload['reportId']
            if payload.get('validUntil') and now.astimezone(ZoneInfo('Europe/Moscow')).date().isoformat()>payload['validUntil']:
                db.execute("UPDATE app.subscription SET status='COMPLETED',version=version+1,next_run_at=NULL WHERE id=?",(key,))
                audit(db,owner,'SUBSCRIPTION_COMPLETED',rid,resource=key);continue
            try:
                owner_claims=resolve(owner);Scope(db,owner_claims,rid)
                if not roles(owner_claims)&{PM,TL,QA,AN}: raise PermissionError()
            except (Problem,PermissionError):
                db.execute("UPDATE app.subscription SET status='PAUSED',version=version+1,next_run_at=NULL WHERE id=?",(key,))
                notify(db,owner,'SUBSCRIPTION_PAUSED');audit(db,owner,'SUBSCRIPTION_PAUSED',rid,resource=key);continue
            delivered=[];skipped=[]
            for recipient in payload['recipients']:
                try:
                    claims=resolve(recipient);Scope(db,claims,rid)
                    service=Service(db,claims,resolver=resolve)
                    export_id=service.create_export(rid,payload['query'],payload['format'],ceiling=owner,kind='SCHEDULED_REPORT_READY',subscription=key)
                    if complete_export(db,export_id,resolve): delivered.append(recipient)
                    else: skipped.append({'recipient':recipient,'reason':'AUTHORIZATION_OR_DATA_UNAVAILABLE'})
                except (Problem,PermissionError): skipped.append({'recipient':recipient,'reason':'NO_CURRENT_ACCESS'})
            delivery={'runAt':scheduled,'status':'DELIVERED' if delivered else 'FAILED','snapshotId':None,'delivered':delivered,'skipped':skipped}
            db.execute('INSERT INTO app.delivery VALUES (?,?,?) ON CONFLICT(subscription_id,run_at) DO NOTHING',(key,scheduled,packed(delivery)))
            if skipped: notify(db,owner,'RECIPIENT_SKIPPED')
            db.execute('UPDATE app.subscription SET next_run_at=?,version=version+1 WHERE id=?',(next_run(payload['schedule'],now),key))
            audit(db,owner,'SUBSCRIPTION_DELIVERY',rid,result=delivery['status'],resource=key)
        return {'exports':len(ids),'subscriptions':len(due)}
