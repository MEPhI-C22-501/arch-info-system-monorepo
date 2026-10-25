"""Typed Reports star, observed SCD2, unknown members and atomic projection.

No backdated HR state is invented. A day-grain fact resolves dimension versions
at UTC end-of-day; missing historical versions use -1. Natural IDs are retained
for reconciliation and authorization, never treated as cross-system mappings.
"""
import hashlib
import json
from datetime import date,datetime,time,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from product_store import packed

DIMS={
 'employee':{'employee_id':'TEXT','account_user_id':'TEXT','full_name':'TEXT','org_unit_id':'TEXT','position_id':'TEXT','grade':'TEXT','is_active':'INTEGER'},
 'project':{'project_id':'TEXT','tracker_project_id':'TEXT','name':'TEXT','portfolio_id':'TEXT','status':'TEXT','manager_employee_id':'TEXT'},
 'epic':{'epic_id':'TEXT','project_key':'BIGINT','name':'TEXT'},
 'iteration':{'iteration_id':'TEXT','name':'TEXT','start_date':'TEXT','end_date':'TEXT','state':'TEXT'},
 'release':{'release_id':'TEXT','project_key':'BIGINT','name':'TEXT'},
 'work_item':{'work_item_id':'TEXT','work_item_type':'TEXT','title':'TEXT','parent_work_item_id':'TEXT','project_key':'BIGINT','epic_key':'BIGINT','created_at':'TEXT'},
 'status':{'status_id':'TEXT','name':'TEXT','category':'TEXT'},
 'priority':{'priority_id':'TEXT','name':'TEXT','rank':'INTEGER'},
 'severity':{'code':'TEXT','name':'TEXT'},
 'defect':{'defect_id':'TEXT','project_key':'BIGINT','tt_work_item_id':'TEXT','created_at':'TEXT'},
 'test_plan':{'test_plan_id':'TEXT','project_key':'BIGINT','iteration_key':'BIGINT','release_key':'BIGINT','name':'TEXT'},
 'test_case':{'test_case_id':'TEXT','case_version':'INTEGER','name':'TEXT','automated':'INTEGER'},
 'project_role':{'role_code':'TEXT','name':'TEXT'},
 'org_unit':{'org_unit_id':'TEXT','name':'TEXT','parent_id':'TEXT'},
 'position':{'position_id':'TEXT','name':'TEXT'},
 'grade':{'grade_id':'TEXT','name':'TEXT'},
}
# All column names below are internal constants, never SQL supplied by callers.
KEYS={k+'_key':k for k in DIMS}
FACTS={
 'work_item_daily':{'snapshot_date':'TEXT NOT NULL','work_item_id':'TEXT NOT NULL','work_item_key':'BIGINT','project_key':'BIGINT','epic_key':'BIGINT','iteration_key':'BIGINT','status_key':'BIGINT','priority_key':'BIGINT','assignee_key':'BIGINT','project_id':'TEXT','user_id':'TEXT','planned_hours':'NUMERIC','actual_hours':'NUMERIC','remaining_hours':'NUMERIC','start_date':'TEXT','due_date':'TEXT','created_at':'TEXT','completed_at':'TEXT','category':'TEXT','is_leaf':'INTEGER','is_deleted':'INTEGER','cycle_days':'NUMERIC','lead_days':'NUMERIC','is_overdue':'INTEGER','source_revision':'BIGINT'},
 'status_transition':{'work_item_id':'TEXT','work_item_key':'BIGINT','project_key':'BIGINT','from_status_key':'BIGINT','to_status_key':'BIGINT','changed_by_key':'BIGINT','date_key':'INTEGER','project_id':'TEXT','user_id':'TEXT','from_status':'TEXT','to_status':'TEXT','category':'TEXT','changed_at':'TEXT'},
 'defect_daily':{'snapshot_date':'TEXT NOT NULL','defect_id':'TEXT','defect_key':'BIGINT','project_key':'BIGINT','iteration_key':'BIGINT','release_key':'BIGINT','severity_key':'BIGINT','priority_key':'BIGINT','assignee_key':'BIGINT','project_id':'TEXT','user_id':'TEXT','status_code':'TEXT','created_at':'TEXT','first_closed_at':'TEXT','close_days':'NUMERIC','history_known':'INTEGER','is_open':'INTEGER','reopen_count':'INTEGER','is_deleted':'INTEGER'},
 'defect_transition':{'defect_id':'TEXT','defect_key':'BIGINT','project_key':'BIGINT','date_key':'INTEGER','project_id':'TEXT','user_id':'TEXT','severity':'TEXT','from_status':'TEXT','to_status':'TEXT','changed_at':'TEXT','is_reopen':'INTEGER','is_first_close':'INTEGER','close_days':'NUMERIC'},
 'test_result':{'result_id':'TEXT','run_id':'TEXT','case_id':'TEXT','test_case_key':'BIGINT','test_plan_key':'BIGINT','iteration_key':'BIGINT','release_key':'BIGINT','executed_by_key':'BIGINT','project_key':'BIGINT','project_id':'TEXT','user_id':'TEXT','case_version':'INTEGER','result':'TEXT','recorded_at':'TEXT','is_run_final':'INTEGER'},
 'test_run':{'run_id':'TEXT','test_plan_key':'BIGINT','project_key':'BIGINT','iteration_key':'BIGINT','project_id':'TEXT','user_id':'TEXT','status':'TEXT','started_at':'TEXT','finished_at':'TEXT','case_count':'INTEGER','passed':'INTEGER','failed':'INTEGER','blocked':'INTEGER','skipped':'INTEGER','not_run':'INTEGER'},
 'plan_item':{'plan_version_id':'TEXT','logical_item_id':'TEXT','project_key':'BIGINT','epic_key':'BIGINT','project_id':'TEXT','item_type':'TEXT','planned_start':'TEXT','planned_finish':'TEXT','planned_hours':'NUMERIC','is_baseline':'INTEGER'},
 'demand':{'plan_version_id':'TEXT','demand_id':'TEXT','project_key':'BIGINT','project_role_key':'BIGINT','week_key':'INTEGER','project_id':'TEXT','role_code':'TEXT','grade_code':'TEXT','period_start':'TEXT','period_end':'TEXT','required_hours':'NUMERIC'},
 'allocation':{'plan_version_id':'TEXT','demand_id':'TEXT','project_key':'BIGINT','employee_key':'BIGINT','project_role_key':'BIGINT','week_key':'INTEGER','date_key':'INTEGER','project_id':'TEXT','user_id':'TEXT','role_code':'TEXT','allocated_hours':'NUMERIC','status':'TEXT'},
 'availability':{'date_key':'INTEGER','employee_key':'BIGINT','project_id':'TEXT','user_id':'TEXT','available_hours':'NUMERIC','is_absent':'INTEGER','status':'TEXT','day':'TEXT'},
 'forecast':{'project_key':'BIGINT','project_id':'TEXT','plan_version_id':'TEXT','as_of_date_key':'INTEGER','remaining_hours':'NUMERIC','forecast_finish':'TEXT','estimated_total_cost':'NUMERIC','budget_adjustment':'NUMERIC','currency':'TEXT','quality':'TEXT','calculated_at':'TEXT'},
}
CUBE_VIEWS=['cube_'+n for n in ['work_items','defects','status_flow','defect_flow','test_runs','test_results','demands','allocations','availability','forecasts','scope','principal','resources','quality','daily_wip']]
UNKNOWN='0001-01-01T00:00:00+00:00'


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS dwh.dim_date(date_key INTEGER PRIMARY KEY,day TEXT,iso_week TEXT,month TEXT,quarter INTEGER,year INTEGER)')
    db.execute("INSERT INTO dwh.dim_date VALUES (-1,NULL,NULL,NULL,NULL,NULL) ON CONFLICT DO NOTHING")
    for name,columns in DIMS.items():
        attrs=','.join(k+' '+v for k,v in columns.items())
        refs=','.join(f'FOREIGN KEY({k}) REFERENCES dwh.dim_{k[:-4]}({k})' for k in columns if k.endswith('_key') and k[:-4] in DIMS)
        db.execute(f'''CREATE TABLE IF NOT EXISTS dwh.dim_{name}({name}_key BIGINT PRIMARY KEY,source TEXT NOT NULL,source_id TEXT NOT NULL,
          valid_from TEXT NOT NULL,valid_to TEXT,is_current INTEGER NOT NULL,is_deleted INTEGER NOT NULL,attribute_hash TEXT NOT NULL,payload TEXT NOT NULL,{attrs},
          UNIQUE(source,source_id,valid_from),CHECK(valid_to IS NULL OR valid_to>=valid_from){','+refs if refs else ''})''')
        db.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS star_{name}_current ON dwh.dim_{name}(source,source_id) WHERE is_current=1')
        db.execute(f"INSERT INTO dwh.dim_{name}({name}_key,source,source_id,valid_from,is_current,is_deleted,attribute_hash,payload) VALUES (-1,'unknown','UNKNOWN',?,1,0,'unknown','{{}}') ON CONFLICT DO NOTHING",(UNKNOWN,))
    for name,columns in FACTS.items():
        defs=[];refs=[]
        for column,kind in columns.items():
            if column.endswith('_key'):
                target={'assignee_key':'employee','executed_by_key':'employee','changed_by_key':'employee','from_status_key':'status','to_status_key':'status','week_key':'date','as_of_date_key':'date'}.get(column,column[:-4])
                defs.append(column+' '+kind+' NOT NULL DEFAULT -1')
                if target in DIMS or target=='date': refs.append(f'FOREIGN KEY({column}) REFERENCES dwh.dim_{target}({target}_key)')
            else: defs.append(column+' '+kind)
        db.execute(f'CREATE TABLE IF NOT EXISTS dwh.fact_{name}(id TEXT PRIMARY KEY,{",".join(defs)},data_as_of TEXT NOT NULL,payload TEXT NOT NULL{","+",".join(refs) if refs else ""})')
    db.execute('''CREATE TABLE IF NOT EXISTS dwh.plan_version(id TEXT PRIMARY KEY,project_key BIGINT NOT NULL DEFAULT -1 REFERENCES dwh.dim_project(project_key),
      project_id TEXT,version_number INTEGER,revision INTEGER,status TEXT,data_as_of TEXT NOT NULL,payload TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.star_issue(source TEXT NOT NULL,entity TEXT NOT NULL,entity_id TEXT NOT NULL,code TEXT NOT NULL,
      observed_at TEXT NOT NULL,PRIMARY KEY(source,entity,entity_id,code))''')
    if not db.sqlite:
        db.execute('ALTER TABLE dwh.fact_time_log DROP CONSTRAINT IF EXISTS fact_time_log_hours_cents_check')
        db.execute('ALTER TABLE dwh.fact_time_log ADD CONSTRAINT fact_time_log_hours_cents_check CHECK(hours_cents>=0)')
    fields={'date_key':'date','employee_key':'employee','work_item_key':'work_item','project_key':'project','iteration_key':'iteration','epic_key':'epic'}
    existing={row[1] for row in db.execute('PRAGMA table_info(dwh_fact_time_log)')} if db.sqlite else {r[0] for r in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='dwh' AND table_name='fact_time_log'")}
    for col,target in fields.items():
        if col not in existing: db.execute(f'ALTER TABLE dwh.fact_time_log ADD COLUMN {col} BIGINT NOT NULL DEFAULT -1 REFERENCES dwh.dim_{target}({target}_key)')
    for col,kind in {'is_deleted':'INTEGER NOT NULL DEFAULT 0','source_revision':'BIGINT','batch_id':'TEXT'}.items():
        if col not in existing: db.execute(f'ALTER TABLE dwh.fact_time_log ADD COLUMN {col} {kind}')
    for name in ['work_item_daily','defect_daily']:
        natural='work_item_id' if name=='work_item_daily' else 'defect_id'
        db.execute(f'''CREATE VIEW IF NOT EXISTS dwh.current_{name} AS SELECT f.* FROM dwh.fact_{name} f
          WHERE f.snapshot_date=(SELECT MAX(x.snapshot_date) FROM dwh.fact_{name} x WHERE x.{natural}=f.{natural})''')
    db.execute('''CREATE VIEW IF NOT EXISTS dwh.cube_work_items AS SELECT f.*,i.iteration_id,e.epic_id
      FROM dwh.current_work_item_daily f LEFT JOIN dwh.dim_iteration i ON f.iteration_key=i.iteration_key
      LEFT JOIN dwh.dim_epic e ON f.epic_key=e.epic_key WHERE COALESCE(f.is_deleted,0)=0''')
    db.execute('''CREATE VIEW IF NOT EXISTS dwh.cube_forecasts AS SELECT * FROM (SELECT f.*,CAST(NULL AS TEXT) AS user_id,
      ROW_NUMBER() OVER(PARTITION BY project_id ORDER BY calculated_at DESC,id DESC) AS latest_rank
      FROM dwh.fact_forecast f) selected WHERE latest_rank=1''')
    for model,table in [('defects','current_defect_daily'),('status_flow','fact_status_transition'),('defect_flow','fact_defect_transition'),('test_runs','fact_test_run'),('test_results','fact_test_result'),('demands','fact_demand'),('allocations','fact_allocation'),('availability','fact_availability')]:
        suffix=' WHERE COALESCE(is_deleted,0)=0' if model=='defects' else ''
        db.execute(f'CREATE VIEW IF NOT EXISTS dwh.cube_{model} AS SELECT * FROM dwh.{table}'+suffix)
    db.execute('''CREATE VIEW IF NOT EXISTS dwh.cube_resources AS
      SELECT 'time:'||l.id AS id,l.project_id,l.user_id,l.logged_date AS day,NULL AS role_code,l.hours_cents/100.0 AS actual_hours,
        CAST(NULL AS NUMERIC) AS required_hours,CAST(NULL AS NUMERIC) AS allocated_hours,CAST(NULL AS NUMERIC) AS available_hours,
        CASE WHEN EXISTS(SELECT 1 FROM dwh.fact_availability a WHERE a.user_id=l.user_id AND a.status='CONFIRMED') THEN 1 ELSE 0 END AS capacity_known,
        CAST(NULL AS TEXT) AS period_end FROM dwh.report_time_log l
      UNION ALL SELECT 'demand:'||id,project_id,NULL,period_start,role_code,NULL,required_hours,NULL,NULL,1,period_end FROM dwh.fact_demand
      UNION ALL SELECT 'allocation:'||id,project_id,user_id,d.day,f.role_code,NULL,NULL,allocated_hours,NULL,1,NULL
        FROM dwh.fact_allocation f LEFT JOIN dwh.dim_date d ON f.date_key=d.date_key WHERE status IS NULL OR status<>'CANCELLED'
      UNION ALL SELECT 'availability:'||id,project_id,user_id,day,NULL,NULL,NULL,NULL,available_hours,1,NULL
        FROM (SELECT a.*,ROW_NUMBER() OVER(PARTITION BY COALESCE(user_id,id),day ORDER BY data_as_of DESC,id DESC) AS rank
          FROM dwh.fact_availability a) selected WHERE rank=1 AND status='CONFIRMED' ''')
    db.execute('''CREATE VIEW IF NOT EXISTS dwh.cube_quality AS
      SELECT 'task:'||id AS id,project_id,user_id,0 AS defect_count,CASE WHEN category='COMPLETED' THEN 1 ELSE 0 END AS completed_count FROM dwh.cube_work_items
      UNION ALL SELECT 'defect:'||id,project_id,user_id,1,0 FROM dwh.cube_defects''')
    if not db.sqlite:
        db.execute('''CREATE VIEW IF NOT EXISTS dwh.cube_daily_wip AS
          SELECT w.work_item_id||':'||d.day::date::text AS id,w.project_id,w.user_id,d.day::date::text AS day,
            CASE WHEN state.category='WORKING' THEN 1 ELSE 0 END AS is_working,
            CASE WHEN EXISTS(SELECT 1 FROM dwh.fact_status_transition h WHERE h.work_item_id=w.work_item_id
              AND h.category IN ('BACKLOG','WORKING')) THEN 1 ELSE 0 END AS history_known
          FROM dwh.cube_work_items w CROSS JOIN LATERAL generate_series(
            LEAST(w.created_at::date,(SELECT MIN(changed_at::timestamptz)::date FROM dwh.fact_status_transition)),
            (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date,interval '1 day') d(day)
          LEFT JOIN LATERAL(SELECT h.category FROM dwh.fact_status_transition h
            WHERE h.work_item_id=w.work_item_id AND h.changed_at::timestamptz<d.day+interval '1 day'
            ORDER BY h.changed_at::timestamptz DESC,h.id DESC LIMIT 1) state ON true''')
    else:
        db.execute('''CREATE VIEW IF NOT EXISTS dwh.cube_daily_wip AS SELECT id,project_id,user_id,
          snapshot_date AS day,NULL AS is_working,0 AS history_known FROM dwh.current_work_item_daily''')
    db.execute("""CREATE VIEW IF NOT EXISTS dwh.cube_scope AS
      SELECT s.subject,s.role,s.project_id,s.employee_id FROM app.user_scope s
      LEFT JOIN app.principal p ON p.subject=s.subject WHERE p.enabled IS NULL OR p.enabled=1
      UNION ALL SELECT b.subject,'reports-member','',b.subject FROM app.subject_binding b
      LEFT JOIN app.principal p ON p.subject=b.subject WHERE p.enabled IS NULL OR p.enabled=1""")
    db.execute('CREATE VIEW IF NOT EXISTS dwh.cube_principal AS SELECT subject,enabled FROM app.principal')



def numeric(value):
    if isinstance(value,bool) or value is None:return None
    try:
        number=Decimal(str(value))
        return float(number) if number.is_finite() else None
    except Exception:return None


def timestamp(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d.astimezone(timezone.utc).isoformat() if d.tzinfo else None
    except (ValueError,TypeError,AttributeError):return None


def date_key(db,value):
    try:d=date.fromisoformat(value[:10])
    except (ValueError,TypeError):return -1
    key=int(d.strftime('%Y%m%d'))
    db.execute('INSERT INTO dwh.dim_date VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING',(key,d.isoformat(),d.strftime('%G-W%V'),d.strftime('%Y-%m'),(d.month-1)//3+1,d.year))
    return key


def dimension(db,name,source,source_id,attrs,payload,at):
    source_id=str(source_id);attrs={key:attrs.get(key) for key in DIMS[name]};deleted=int(bool(payload.get('is_deleted') or payload.get('isDeleted')))
    digest=hashlib.sha256(packed([attrs,deleted]).encode()).hexdigest()
    previous=db.execute(f'SELECT {name}_key,attribute_hash,valid_from FROM dwh.dim_{name} WHERE source=? AND source_id=? AND is_current=1',(source,source_id)).fetchone()
    if previous and previous[1]==digest:
        db.execute(f'UPDATE dwh.dim_{name} SET payload=? WHERE {name}_key=?',(packed(payload),previous[0]));return previous[0]
    if previous:
        if at<previous[2]:return previous[0]
        if at==previous[2]:
            # A corrected observation at the same instant replaces that version,
            # not a zero-length SCD interval or an invalid FK.
            assignments=','.join(k+'=?' for k in attrs)
            db.execute(f'UPDATE dwh.dim_{name} SET {assignments},is_deleted=?,attribute_hash=?,payload=? WHERE {name}_key=?',tuple(attrs.values())+(deleted,digest,packed(payload),previous[0]));return previous[0]
        db.execute(f'UPDATE dwh.dim_{name} SET valid_to=?,is_current=0 WHERE {name}_key=?',(at,previous[0]))
    key=int(hashlib.sha256(packed([name,source,source_id,at,digest]).encode()).hexdigest()[:15],16)
    cols=[name+'_key','source','source_id','valid_from','valid_to','is_current','is_deleted','attribute_hash','payload',*attrs]
    values=[key,source,source_id,at,None,1,deleted,digest,packed(payload),*attrs.values()]
    db.execute(f'INSERT INTO dwh.dim_{name}({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',tuple(values));return key


def key_at(db,name,source,source_id,at):
    if source_id is None:return -1
    at=timestamp(at) or ((str(at)[:10]+'T23:59:59.999999+00:00') if at else UNKNOWN)
    row=db.execute(f'''SELECT {name}_key FROM dwh.dim_{name} WHERE source=? AND source_id=? AND valid_from<=?
      AND (valid_to IS NULL OR valid_to>?) ORDER BY valid_from DESC LIMIT 1''',(source,str(source_id),at,at)).fetchone()
    return row[0] if row else -1


def upsert(db,table,key,values,payload,at):
    data=dict(id=str(key),**values,data_as_of=at,payload=packed(payload));cols=list(data)
    db.execute(f'INSERT INTO dwh.{table}({",".join(cols)}) VALUES ({",".join("?" for _ in cols)}) ON CONFLICT(id) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in cols if k!='id'),tuple(data.values()))


def records(db,source,entity):
    return [json.loads(r[0]) for r in db.execute('SELECT payload FROM dwh.source_record WHERE source=? AND entity=? ORDER BY entity_id',(source,entity))]


def refresh(db,at,batch_id=None,*,observed_at=None):
    from report_engine import Engine
    # at is the source watermark, not evidence that historical dimensions
    # were observed then. SCD2 and daily observations use our observation time.
    from product_store import stamp
    at=timestamp(observed_at) or stamp()
    if not db.sqlite:db.execute("SELECT pg_advisory_xact_lock(hashtext('reports-star-refresh'))")
    links={(k,s):t for k,s,t in db.execute('SELECT kind,source_id,target_id FROM app.entity_link')}
    bindings={u:s for s,u in db.execute('SELECT subject,tracker_user_id FROM app.subject_binding')}
    # The reference engine is used only for natural-key reconciliation; it reads
    # staging observations here. Serving paths below use the typed star.
    engine=Engine(db);engine.records=lambda source,entity:records(db,source,entity)
    def k(name,source,value,when=at):return key_at(db,name,source,value,when)
    project_inverse={target:source for (kind,source),target in links.items() if kind=='planning-project'}
    employee_inverse={target:source for (kind,source),target in links.items() if kind=='hr-employee'}
    def emp(subject,when=at):return k('employee','reference',employee_inverse.get(subject),when)
    def project(tracker,when=at):return k('project','planning',project_inverse.get(tracker),when)
    for r in records(db,'reference','employees'):
        dimension(db,'employee','reference',r['id'],dict(employee_id=str(r['id']),account_user_id=links.get(('hr-employee',str(r['id']))),full_name=' '.join(str(r.get(f,'')) for f in ['family_name','given_name','middle_name']).strip() or r.get('name'),org_unit_id=str(r['org_unit_id']) if r.get('org_unit_id') is not None else None,position_id=str(r['position_id']) if r.get('position_id') is not None else None,grade=r.get('grade'),is_active=int(not r.get('is_deleted',False))),r,at)
    for entity,name,idcol in [('org_units','org_unit','org_unit_id'),('positions','position','position_id'),('project_roles','project_role','role_code'),('grades','grade','grade_id')]:
        for r in records(db,'reference',entity):dimension(db,name,'reference',r['id'],{idcol:str(r['id']),'name':r.get('name'),'parent_id':str(r['parent_id']) if r.get('parent_id') is not None else None},r,at)
    plans=records(db,'planning','plan')
    for r in plans:
        p=r.get('data',{});pid=p.get('projectId')
        if pid:
            dimension(db,'project','planning',pid,dict(project_id=pid,tracker_project_id=links.get(('planning-project',pid)),name=p.get('projectName'),portfolio_id=p.get('portfolioId'),status=p.get('status'),manager_employee_id=p.get('managerEmployeeId')),p,at)
            for item in p.get('items',[]):
                kind=item.get('type') or item.get('kind')
                if kind in {'EPIC','RELEASE'}:
                    dim='epic' if kind=='EPIC' else 'release'
                    dimension(db,dim,'planning',item.get('logicalItemId',item.get('id')),{dim+'_id':item.get('logicalItemId',item.get('id')),'project_key':k('project','planning',pid),'name':item.get('name')},item,at)
        upsert(db,'plan_version',r['id'],dict(project_key=k('project','planning',pid),project_id=links.get(('planning-project',pid)),version_number=p.get('versionNumber'),revision=p.get('revision'),status=p.get('status')),r,at)
    for r in records(db,'tracker','iterations'):dimension(db,'iteration','tracker',r['id'],dict(iteration_id=r['id'],name=r.get('name'),start_date=r.get('startDate'),end_date=r.get('endDate'),state=r.get('state')),r,at)
    for r in records(db,'tracker','statuses'):dimension(db,'status','tracker',r['id'],dict(status_id=r['id'],name=r.get('name'),category=links.get(('tracker-status-category',r['id'])) or r.get('category')),r,at)
    for r in records(db,'tracker','work-items'):
        dimension(db,'priority','tracker',r.get('priorityId','UNKNOWN'),dict(priority_id=r.get('priorityId'),name=r.get('priority'),rank=None),{'id':r.get('priorityId')},at)
        dimension(db,'work_item','tracker',r['id'],dict(work_item_id=r['id'],work_item_type=r.get('type'),title=r.get('title'),parent_work_item_id=r.get('parentId'),project_key=project(r.get('projectId')),epic_key=k('epic','planning',r.get('epicId')),created_at=r.get('createdAt')),r,at)
    tasks=engine.task_rows();taskmap={r['id']:r for r in tasks}
    snapshot=datetime.fromisoformat(at).astimezone(ZoneInfo('Europe/Moscow')).date().isoformat()
    raw_tasks={r['id']:r for r in records(db,'tracker','work-items')}
    for t in tasks:
        changes=engine.transitions(t);finish=next((dt for dt,c in changes if c=='COMPLETED'),None);start=next((dt for dt,c in changes if c=='WORKING'),None);created=timestamp(t.get('createdAt'));created_dt=datetime.fromisoformat(created) if created else None
        values=dict(snapshot_date=snapshot,work_item_id=t['id'],work_item_key=k('work_item','tracker',t['id']),project_key=project(t.get('project')),epic_key=k('epic','planning',t.get('epic')),iteration_key=k('iteration','tracker',t.get('iteration')),status_key=k('status','tracker',t.get('status')),priority_key=k('priority','tracker',t.get('priority')),assignee_key=emp(t.get('employee')),project_id=t.get('project'),user_id=t.get('employee'),planned_hours=numeric(t.get('plannedHours')),actual_hours=numeric(t.get('actualHours')),remaining_hours=numeric(t.get('remainingHours')),start_date=t.get('startDate'),due_date=t.get('dueDate'),created_at=t.get('createdAt'),completed_at=finish.isoformat() if finish else None,category=t.get('_category'),is_leaf=1,is_deleted=int(bool(t.get('isDeleted'))),cycle_days=(finish-start).total_seconds()/86400 if finish and start and finish>=start else None,lead_days=(finish-created_dt).total_seconds()/86400 if finish and created_dt and finish>=created_dt else None,is_overdue=int(bool(t.get('dueDate') and t['dueDate']<snapshot and t.get('_category') not in {'COMPLETED','ARCHIVED'})),source_revision=t.get('version'))
        original=raw_tasks[t['id']]
        upsert(db,'fact_work_item_daily',snapshot+':'+t['id'],values,original,at)
    for r in records(db,'tracker','history'):
        t=taskmap.get(r.get('workItemId'),{});sid=r.get('newValues',{}).get('statusId')
        if not sid:continue
        old=r.get('oldValues',{}).get('statusId');changed=r.get('occurredAt')
        category=links.get(('tracker-status-category',sid)) or next((s.get('category') for s in records(db,'tracker','statuses') if s['id']==sid),None)
        upsert(db,'fact_status_transition',r['id'],dict(work_item_id=r.get('workItemId'),work_item_key=k('work_item','tracker',r.get('workItemId'),changed),project_key=project(t.get('project'),changed),from_status_key=k('status','tracker',old,changed),to_status_key=k('status','tracker',sid,changed),changed_by_key=emp(bindings.get(r.get('actorId')),changed),date_key=date_key(db,changed),project_id=t.get('project'),user_id=t.get('employee'),from_status=old,to_status=sid,category=category,changed_at=changed),r,at)
    for row in db.execute('SELECT id,user_id,project_id,work_item_id,logged_date FROM dwh.fact_time_log').fetchall():
        rid,user,pid,wid,day=row;t=taskmap.get(wid,{})
        db.execute('''UPDATE dwh.fact_time_log SET date_key=?,employee_key=?,work_item_key=?,project_key=?,iteration_key=?,epic_key=?,batch_id=? WHERE id=?''',
          (date_key(db,day),emp(bindings.get(user),day),k('work_item','tracker',wid,day),project(pid,day),k('iteration','tracker',t.get('iteration'),day),k('epic','planning',t.get('epic'),day),batch_id,rid))
    qa_project={}
    for r in engine.qa_rows('test-plans'):
        qa_project[r['id']]=r
        dimension(db,'test_plan','qa',r['id'],dict(test_plan_id=r['id'],project_key=project(r.get('project')),iteration_key=k('iteration','tracker',r.get('iteration')),release_key=k('release','planning',r.get('planningReleaseId')),name=r.get('title')),r,at)
    for r in records(db,'qa','test-cases'):dimension(db,'test_case','qa',r['id'],dict(test_case_id=r['id'],case_version=r.get('version'),name=r.get('title'),automated=int(bool(r.get('automated')))),r,at)
    for d in engine.qa_rows('defects'):
        severity=d.get('severity')
        dimension(db,'severity','qa',severity or 'UNKNOWN',dict(code=severity,name=severity),{'id':severity},at)
        dimension(db,'defect','qa',d['id'],dict(defect_id=d['id'],project_key=project(d.get('project')),tt_work_item_id=d.get('trackerWorkItemId'),created_at=d.get('createdAt')),d,at)
        history=[h for h in d.get('history',[]) if h.get('field','status')=='status' and timestamp(h.get('occurredAt'))]
        closes=sorted(h['occurredAt'] for h in history if (h.get('newValue') or h.get('status'))=='CLOSED')
        first=closes[0] if closes else d.get('closedAt');created=timestamp(d.get('createdAt'));closed=timestamp(first)
        latency=(datetime.fromisoformat(closed)-datetime.fromisoformat(created)).total_seconds()/86400 if created and closed else None
        values=dict(snapshot_date=snapshot,defect_id=d['id'],defect_key=k('defect','qa',d['id']),project_key=project(d.get('project')),iteration_key=k('iteration','tracker',d.get('iteration')),release_key=k('release','planning',d.get('planningReleaseId')),severity_key=k('severity','qa',severity or 'UNKNOWN'),priority_key=-1,assignee_key=emp(d.get('employee')),project_id=d.get('project'),user_id=d.get('employee'),status_code=d.get('status'),created_at=d.get('createdAt'),first_closed_at=first,close_days=latency,history_known=int(bool(history) or d.get('status')=='OPEN'),is_open=int(d.get('status')!='CLOSED'),reopen_count=d.get('reopenCount'),is_deleted=int(bool(d.get('isDeleted'))))
        original=next(r for r in records(db,'qa','defects') if r['id']==d['id']);upsert(db,'fact_defect_daily',snapshot+':'+d['id'],values,original,at)
        for h in history:
            changed=h['occurredAt'];status=h.get('newValue') or h.get('status');identity=hashlib.sha256(packed([d['id'],changed,h.get('oldValue'),status]).encode()).hexdigest()
            upsert(db,'fact_defect_transition',h.get('eventId') or identity,dict(defect_id=d['id'],defect_key=k('defect','qa',d['id'],changed),project_key=project(d.get('project'),changed),date_key=date_key(db,changed),project_id=d.get('project'),user_id=d.get('employee'),severity=severity,from_status=h.get('oldValue'),to_status=status,changed_at=changed,is_reopen=int(status=='REOPENED'),is_first_close=int(status=='CLOSED' and changed==first),close_days=latency if status=='CLOSED' and changed==first else None),h,at)
    runs={r['id']:r for r in engine.qa_rows('test-runs')};latest={}
    for r in records(db,'qa','test-results'):
        natural=(r.get('runId'),r.get('testCaseId')) if r.get('runId') and r.get('testCaseId') else (r['id'],)
        order=(r.get('finishedAt') or r.get('updatedAt') or '',str(r['id']))
        if natural not in latest or order>latest[natural][0]:latest[natural]=(order,r)
    for _,r in latest.values():
        run=runs.get(r.get('runId'),{});changed=r.get('finishedAt') or r.get('updatedAt') or at;identity=':'.join(str(x) for x in [r.get('runId'),r.get('testCaseId')]) if r.get('runId') and r.get('testCaseId') else r['id']
        upsert(db,'fact_test_result',identity,dict(result_id=r['id'],run_id=r.get('runId'),case_id=r.get('testCaseId'),test_case_key=k('test_case','qa',r.get('testCaseId'),changed),test_plan_key=k('test_plan','qa',run.get('planId'),changed),iteration_key=k('iteration','tracker',run.get('iteration'),changed),release_key=-1,executed_by_key=emp(r.get('executedBy'),changed),project_key=project(run.get('project'),changed),project_id=run.get('project'),user_id=run.get('employee'),case_version=r.get('caseVersion'),result=r.get('status'),recorded_at=changed,is_run_final=int(run.get('status') in {'COMPLETED','FINISHED','ABORTED'})),r,at)
    for run in runs.values():
        states=[r.get('status') for _,r in latest.values() if r.get('runId')==run['id']]
        counts={name:states.count(name) for name in ['PASSED','FAILED','BLOCKED','SKIPPED','NOT_RUN']}
        upsert(db,'fact_test_run',run['id'],dict(run_id=run['id'],test_plan_key=k('test_plan','qa',run.get('planId')),project_key=project(run.get('project')),iteration_key=k('iteration','tracker',run.get('iteration')),project_id=run.get('project'),user_id=run.get('employee'),status=run.get('status'),started_at=run.get('startedAt'),finished_at=run.get('finishedAt'),case_count=run.get('caseCount',run.get('summary',{}).get('total')),passed=counts['PASSED'],failed=counts['FAILED'],blocked=counts['BLOCKED'],skipped=counts['SKIPPED'],not_run=counts['NOT_RUN']),next(r for r in records(db,'qa','test-runs') if r['id']==run['id']),at)
    for entity in ['demand','allocation','availability','forecast']:
        for r in engine.planning_rows(entity):
            original=next(v for v in records(db,'planning',entity) if v['id']==r['record']);p=original.get('data',{});when=p.get('date') or p.get('periodStart') or p.get('dataAsOf') or at
            common=dict(project_id=r.get('project'))
            if entity in {'demand','allocation','forecast'}:common['project_key']=project(r.get('project'),when)
            if entity=='demand':
                start=p.get('periodStart');end=p.get('periodEnd');week=-1
                if start and end and date.fromisoformat(start).isocalendar()[:2]==date.fromisoformat(end).isocalendar()[:2]:week=date_key(db,(date.fromisoformat(start)-__import__('datetime').timedelta(days=date.fromisoformat(start).weekday())).isoformat())
                else:db.execute("INSERT INTO etl.star_issue VALUES ('planning','demand',?,'UNSPLIT_SOURCE_PERIOD',?) ON CONFLICT DO NOTHING",(r['record'],at))
                common.update(plan_version_id=p.get('planVersionId'),demand_id=r['record'],project_role_key=k('project_role','reference',p.get('roleCode')),week_key=week,role_code=p.get('roleCode'),grade_code=p.get('gradeCode'),period_start=start,period_end=end,required_hours=numeric(p.get('hours')))
            elif entity=='allocation':common.update(plan_version_id=p.get('planVersionId'),demand_id=p.get('demandId'),employee_key=emp(r.get('employee'),when),project_role_key=k('project_role','reference',r.get('role')),week_key=date_key(db,(date.fromisoformat(when[:10])-__import__('datetime').timedelta(days=date.fromisoformat(when[:10]).weekday())).isoformat()) if when else -1,date_key=date_key(db,when),user_id=r.get('employee'),role_code=r.get('role'),allocated_hours=numeric(p.get('hours')),status=p.get('status'))
            elif entity=='availability':common.update(date_key=date_key(db,when),employee_key=emp(r.get('employee'),when),user_id=r.get('employee'),available_hours=numeric(p.get('availableHours')),is_absent=int((numeric(p.get('absenceHours')) or 0)>0),status=p.get('status'),day=p.get('date'))
            else:common.update(plan_version_id=p.get('planVersionId'),as_of_date_key=date_key(db,p.get('dataAsOf')),remaining_hours=numeric(p.get('remainingHours')),forecast_finish=p.get('forecastFinish'),estimated_total_cost=numeric(p.get('estimatedTotalCost')),budget_adjustment=numeric(p.get('budgetAdjustment')),currency=p.get('currencyCode'),quality=p.get('quality'),calculated_at=p.get('calculatedAt'))
            upsert(db,'fact_'+entity,r['record'],common,original,at)
    for plan in plans:
        p=plan.get('data',{})
        for item in p.get('items',[]):
            iid=item.get('logicalItemId') or item.get('id')
            if not iid:continue
            upsert(db,'fact_plan_item',plan['id']+':'+iid,dict(plan_version_id=plan['id'],logical_item_id=iid,project_key=k('project','planning',p.get('projectId')),epic_key=k('epic','planning',iid) if item.get('type')=='EPIC' else -1,project_id=links.get(('planning-project',p.get('projectId'))),item_type=item.get('type'),planned_start=item.get('plannedStart') or item.get('startDate'),planned_finish=item.get('plannedFinish') or item.get('endDate'),planned_hours=numeric(item.get('plannedHours')),is_baseline=int(p.get('status') in {'ACTIVE','APPROVED'})),item,at)


READERS={('tracker','work-items'):'dim_work_item',('tracker','iterations'):'dim_iteration',('tracker','statuses'):'dim_status',('tracker','history'):'fact_status_transition',
 ('qa','test-cases'):'dim_test_case',('qa','test-plans'):'dim_test_plan',('qa','test-runs'):'fact_test_run',('qa','test-results'):'fact_test_result',('qa','defects'):'current_defect_daily',
 ('planning','plan'):'plan_version',**{('planning',k):'fact_'+k for k in ['demand','allocation','availability','forecast']},
 **{('reference',resource):'dim_'+name for resource,name in [('employees','employee'),('org_units','org_unit'),('positions','position'),('project_roles','project_role'),('grades','grade')]}}


def read(db,source,entity):
    table=READERS.get((source,entity))
    if not table:return []
    where=' WHERE is_current=1 AND '+table.removeprefix('dim_')+'_key<>-1' if table.startswith('dim_') else ''
    values=db.execute('SELECT payload FROM dwh.'+table+where+' LIMIT 100001').fetchall()
    if len(values)>100000:
        from report_engine import Problem
        raise Problem(422,'RESULT_TOO_LARGE')
    return [json.loads(row[0]) for row in values]
