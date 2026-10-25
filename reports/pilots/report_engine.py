"""R-01..R-11 semantic layer. Source-owned identifiers require explicit links.

Ratios and quantiles are recomputed over source populations, never summed.
Missing historical/category/money inputs remain null with explicit notes.
"""
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from product_store import packed, stamp

PM, TL, QA, MB, AN, AD = ('reports-'+s for s in ('project-manager','team-lead','qa-lead','member','analyst','admin'))
NAMES = ['Трудозатраты','Потребность в сотрудниках','Назначенные задачи','Календарные сроки',
         'Динамика дефектов','План-факт и бюджет','Выполнение тест-плана','Дефекты',
         'Качество релиза и итерации','Здоровье процесса','Точность оценок']
ACCESS = {1:{PM,TL,MB,AN},2:{PM,TL,AN},3:{PM,TL,QA,MB,AN},4:{PM,TL,QA,MB,AN},
          5:{PM,TL,QA,AN},6:{PM,TL,AN},7:{PM,TL,QA,AN},8:{PM,TL,QA,MB,AN},
          9:{PM,TL,QA,AN},10:{PM,TL,AN},11:{PM,TL,MB,AN}}
SOURCES = {1:['tracker'],2:['tracker','planning','reference'],3:['tracker'],4:['tracker'],
           5:['qa'],6:['tracker','planning'],7:['qa'],8:['qa'],9:['tracker','qa'],10:['tracker'],11:['tracker']}
SOURCE_NAMES = dict(tracker='task-tracker',planning='planning-system',reference='reference-manager',qa='qa-system')
MEASURES = {1:['M-01'],2:['M-01','M-10','M-11'],3:['M-01','M-02','M-03','M-06'],4:['M-05'],
            5:['M-12','M-13'],6:['M-01','M-02','M-03','M-04','M-07','M-08','M-09'],
            7:['M-14','M-15'],8:['M-12'],9:['M-06','M-14','M-16','M-17'],
            10:['M-18','M-19'],11:['M-20']}
SLICES = {1:['project','unit','role','employee','iteration','epic','week','month','record'],
          2:['project','unit','employee','role','grade','week'],3:['project','iteration','employee','status','type','record'],
          4:['project','iteration','employee','record'],5:['project','severity','week'],
          6:['project','epic'],7:['project','iteration','record'],8:['project','severity','status','record'],
          9:['project','iteration'],10:['project','iteration'],11:['project','iteration','employee','record']}
FORMULAS = {'M-01':'SUM(hours) за период','M-02':'План листовых задач источника','M-03':'Остаток источника',
 'M-04':'MAX(0, факт - план)','M-05':'Срок < дата отчёта; отклонение в днях',
 'M-06':'Завершено / все без архивных, %','M-07':'Факт за 4 недели / 4',
 'M-08':'Прогноз Planning; сверочный: дата + остаток / темп недель',
 'M-09':'Отклонение бюджета из Planning; деньги не пересчитываются',
 'M-10':'Факт / доступные часы, %','M-11':'Потребность - назначения',
 'M-12':'Создано, закрыто и остаток дефектов','M-13':'Медиана первого закрытия - создания, дни',
 'M-14':'PASSED / (PASSED + FAILED), %','M-15':'Выполнено / все кейсы плана, %',
 'M-16':'Дефекты / (завершённые задачи / 10), методика Q-REP-12',
 'M-17':'Дефекты с REOPENED / закрытые дефекты, %',
 'M-18':'Медиана и p85 cycle/lead time','M-19':'Throughput по ISO-неделям; средний дневной WIP',
 'M-20':'(факт - план) / план, %; медиана факт / план'}


TITLES=dict(zip([f'M-{i:02d}' for i in range(1,21)],[
 'Факт, ч','План, ч','Остаток, ч','Перерасход, ч','Просрочено задач','Завершено, %',
 'Темп, ч/нед','Прогноз завершения','Корректировка бюджета','Загрузка, %','Дефицит, ч',
 'Дефекты','До закрытия, дни','Успешные тесты, %','Выполнение плана, %',
 'Плотность дефектов','Переоткрыто, %','Время цикла','Поток работ','Точность оценок']))
DIMENSION_TITLES=dict(project='Проект',employee='Сотрудник',iteration='Итерация',epic='Эпик',
 unit='Подразделение',role='Проектная роль',grade='Грейд',week='Неделя',month='Месяц',
 status='Статус',priority='Приоритет',severity='Серьёзность',type='Вид задачи',record='Запись')


class Problem(Exception):
    def __init__(self, status, code): self.status, self.code = status, code


def roles(claims):
    try:
        value=claims['resource_access']['reports']['roles']
        if not isinstance(value,list) or any(not isinstance(v,str) for v in value): raise ValueError()
        if not isinstance(claims['sub'],str) or not 0<len(claims['sub'])<=128: raise ValueError()
        if not isinstance(claims.get('scope',''),str): raise ValueError()
        return set(value)
    except (KeyError,TypeError,ValueError): raise Problem(403,'FORBIDDEN') from None


def report_number(rid):
    if not isinstance(rid,str) or rid not in {f'R-{i:02d}' for i in range(1,12)}: raise Problem(404,'NOT_FOUND')
    return int(rid[2:])


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value): return None
    return value


def total(values):
    values=list(values)
    return round(sum(values),4) if values and all(v is not None for v in values) else None


def ratio(a,b): return round(100*a/b,4) if a is not None and b not in (None,0) else None

def day(value):
    try: return date.fromisoformat(value[:10]) if isinstance(value,str) else None
    except ValueError: return None


def instant(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        return result if result.tzinfo else None
    except (ValueError,TypeError,AttributeError): return None


def quantile(values,p):
    if not values: return None
    values=sorted(values); pos=(len(values)-1)*p; low=math.floor(pos); high=math.ceil(pos)
    return round(values[low]+(values[high]-values[low])*(pos-low),4)


class Scope:
    def __init__(self,db,claims,rid):
        self.db,self.claims,self.rid=db,claims,rid
        self.subject=claims['sub']; self.roles=roles(claims); self.n=report_number(rid)
        self.allowed=self.roles & ACCESS[self.n]
        if not self.allowed: raise Problem(403,'FORBIDDEN')
        disabled=db.execute('SELECT enabled FROM app.principal WHERE subject=?',(self.subject,)).fetchone()
        if disabled and not disabled[0]: raise Problem(403,'FORBIDDEN')
        self.global_access=AN in self.allowed
        self.projects=set(); self.employees=set()
        binding=db.execute('SELECT tracker_user_id FROM app.subject_binding WHERE subject=?',(self.subject,)).fetchone()
        self.tracker_id=binding[0] if binding else None
        if MB in self.allowed and self.tracker_id: self.employees.add(self.subject)
        for role,project,employee in db.execute('SELECT role,project_id,employee_id FROM app.user_scope WHERE subject=?',(self.subject,)):
            if role in self.allowed:
                if project: self.projects.add(project)
                if employee and role==TL: self.employees.add(employee)
        if not self.global_access and not self.projects and not self.employees: raise Problem(403,'FORBIDDEN')
        self.cost=bool(self.allowed & {PM,AN}) and 'cost.read' in claims.get('scope','').split()

    def permits(self,row):
        if self.global_access: return True
        # Employee scoping only authorizes employee-owned rows, never a whole
        # project merely because this employee has some hours in that project.
        return (row.get('project') in self.projects or row.get('employee') in self.employees)

    def fingerprint(self):
        mappings=list(self.db.execute('SELECT kind,source_id,target_id FROM app.entity_link ORDER BY kind,source_id'))
        bindings=list(self.db.execute('SELECT subject,tracker_user_id FROM app.subject_binding ORDER BY subject'))
        return hashlib.sha256(packed([sorted(self.allowed),self.global_access,sorted(self.projects),sorted(self.employees),self.cost,mappings,bindings]).encode()).hexdigest()


def definition(rid):
    n=report_number(rid)
    return {'reportId':rid,'name':NAMES[n-1],'question':NAMES[n-1],
            'contour':'ANALYTICAL','sources':[SOURCE_NAMES[s] for s in SOURCES[n]],'version':1,
            'parameters':[{'key':k,'title':k,'type':'date','required':True} for k in ['periodFrom','periodTo']],
            'slices':SLICES[n], 'measures':[{'key':m,'title':TITLES[m],'formula':FORMULAS[m]} for m in MEASURES[n]]}


def validate_query(rid,query):
    n=report_number(rid)
    if not isinstance(query,dict) or set(query)-{'params','slice','compareWithPrevious','viewId','path'}: raise Problem(422,'INVALID_PARAMETER')
    params=query.get('params')
    if not isinstance(params,dict) or set(params)-{'periodFrom','periodTo','projectIds','iterationIds','employeeIds','epicIds','statuses','priorities','severities','types','velocityWeeks'}: raise Problem(422,'INVALID_PARAMETER')
    first,last=day(params.get('periodFrom')),day(params.get('periodTo'))
    if (not first or not last or params.get('periodFrom')!=first.isoformat() or params.get('periodTo')!=last.isoformat()
        or not 0<=(last-first).days<366): raise Problem(422,'INVALID_PARAMETER')
    for key,values in params.items():
        if key=='velocityWeeks':
            if n!=6 or type(values) is not int or not 1<=values<=52: raise Problem(422,'INVALID_PARAMETER')
            continue
        if key in {'periodFrom','periodTo'}: continue
        if not isinstance(values,list) or not 1<=len(values)<=200 or any(not isinstance(x,str) or not 0<len(x)<=128 for x in values): raise Problem(422,'INVALID_PARAMETER')
    slices=query.get('slice',['project'])
    if not isinstance(slices,list) or not slices or len(set(map(str,slices)))!=len(slices) or any(s not in SLICES[n] for s in slices): raise Problem(422,'INVALID_PARAMETER')
    if type(query.get('compareWithPrevious',False)) is not bool: raise Problem(422,'INVALID_PARAMETER')
    paths=query.get('path',[])
    if not isinstance(paths,list) or len(paths)>10 or any(not isinstance(p,dict) or set(p)!={'slice','id'} or p['slice'] not in SLICES[n] or (p['id'] is not None and not isinstance(p['id'],str)) for p in paths): raise Problem(422,'INVALID_PARAMETER')
    return params,slices,first,last


class Engine:
    def __init__(self,db):
        self.db=db; self.notes=set(); self.cache={}; self.transition_cache={}
        self.links={(k,s):t for k,s,t in db.execute('SELECT kind,source_id,target_id FROM app.entity_link')}
        self.bindings={u:s for s,u in db.execute('SELECT subject,tracker_user_id FROM app.subject_binding')}

    def records(self,source,entity):
        key=(source,entity)
        if key not in self.cache:
            from star import read
            self.cache[key]=read(self.db,source,entity)
        return self.cache[key]

    def link(self,kind,value):
        if value is None: return None
        result=self.links.get((kind,str(value)))
        if result is None: self.notes.add('MISSING_MAPPING:'+kind)
        return result

    def freshness(self,n):
        result=[]
        for source in SOURCES[n]:
            row=self.db.execute('SELECT data_as_of,loaded_at FROM etl.source_state WHERE source=?',(source,)).fetchone()
            if not row: raise Problem(503,'SOURCE_NOT_LOADED')
            failed=self.db.execute("SELECT MAX(completed_at) FROM etl.batch WHERE source=? AND status='REJECTED'",(source,)).fetchone()[0]
            observed=instant(row[0]); lag=int((datetime.now(timezone.utc)-observed).total_seconds()) if observed else None
            result.append({'source':SOURCE_NAMES[source],'stream':'reports','dataAsOf':row[0],
                           'lagSeconds':lag,'thresholdSeconds':3600,
                           'state':'FRESH' if lag is not None and 0<=lag<=3600 and (not failed or failed<=row[1]) else 'STALE'})
        return result

    def task_rows(self):
        statuses={s['id']:s for s in self.records('tracker','statuses')}
        items=self.records('tracker','work-items'); parents={i.get('parentId') for i in items if i.get('parentId')}
        by_id={i['id']:i for i in items}
        units={self.links.get(('hr-employee',str(e['id']))):str(e['org_unit_id']) for e in self.records('reference','employees') if e.get('org_unit_id') is not None}
        result=[]
        for item in items:
            if item.get('type') not in {'TASK','SUBTASK','BUG'} or item['id'] in parents: continue
            status=statuses.get(item.get('statusId'),{})
            category=self.links.get(('tracker-status-category',item.get('statusId')))
            if not category and status.get('category') in {'COMPLETED','ARCHIVED'}: category=status['category']
            epic=item.get('epicId');project=item.get('projectId');parent=by_id.get(item.get('parentId'));seen=set()
            while parent and parent['id'] not in seen:
                seen.add(parent['id'])
                if parent.get('type')=='EPIC': epic=parent['id']
                if parent.get('type')=='PROJECT' and not project: project=parent['id']
                parent=by_id.get(parent.get('parentId'))
            employee=self.bindings.get(item.get('assigneeId'))
            result.append(dict(item,project=project,unit=units.get(employee),role=self.links.get(('employee-role',employee)),iteration=item.get('iterationId'),epic=epic,
                               employee=self.bindings.get(item.get('assigneeId')),status=item.get('statusId'),
                               priority=item.get('priorityId'),type=item.get('type'),record=item['id'],_category=category))
        return result

    def logs(self,first,last):
        items={t['id']:t for t in self.task_rows()}
        units={self.links.get(('hr-employee',str(e['id']))):str(e['org_unit_id']) for e in self.records('reference','employees') if e.get('org_unit_id') is not None}
        rows=self.db.execute('''SELECT id,user_id,project_id,work_item_id,logged_date,hours_cents
            FROM dwh.report_time_log WHERE logged_date>=? AND logged_date<=? ORDER BY id LIMIT 100001''',
            (first.isoformat(),last.isoformat())).fetchall()
        if len(rows)>100000: raise Problem(422,'RESULT_TOO_LARGE')
        result=[]
        for key,employee,project,task,logged,cents in rows:
            t=items.get(task,{})
            result.append(dict(t,record=key,employee=employee,project=None if project=='UNASSIGNED' else project,
                               unit=units.get(employee),role=self.links.get(('employee-role',employee)),_task_id=task,_hours=cents/100,week=day(logged).strftime('%G-W%V'),month=logged[:7]))
        return result

    def qa_rows(self,entity):
        plans={p['id']:p for p in self.records('qa','test-plans')}
        runs={r['id']:r for r in self.records('qa','test-runs')}
        rows=[]
        for item in self.records('qa',entity):
            run=runs.get(item.get('runId'),item if entity=='test-runs' else {})
            plan=plans.get(item.get('planId') or run.get('planId'),{})
            planning_id=item.get('planningProjectId') or plan.get('planningProjectId')
            # trackerProjectId is an explicit source field. Never compare two
            # different systems' project IDs based on coincident UUID strings.
            project=item.get('trackerProjectId') or plan.get('trackerProjectId')
            if planning_id: project=self.link('planning-project',planning_id)
            owner=item.get('authorId') or item.get('assigneeId')
            rows.append(dict(item,project=project,iteration=item.get('trackerIterationId') or plan.get('trackerIterationId'),
                             employee=self.bindings.get(owner),record=item['id'],severity=item.get('severity'),
                             status=item.get('status'),week=(day(item.get('createdAt')).strftime('%G-W%V') if day(item.get('createdAt')) else None)))
        return rows

    def planning_rows(self,entity):
        result=[]
        plans=self.records('planning','plan')
        item_projects={i.get('id'):p['data'].get('projectId') for p in plans for i in p['data'].get('items',[])}
        demand_by_id={d['id']:d['data'] for d in self.records('planning','demand')}
        for record in self.records('planning',entity):
            item=record.get('data',{})
            demand=demand_by_id.get(item.get('demandId'),{})
            pid=item.get('projectId') or item_projects.get(item.get('planItemId') or demand.get('planItemId'))
            if not pid and entity=='plan': pid=item.get('projectId')
            if not pid and item.get('planVersionId'):
                plan=next((p['data'] for p in self.records('planning','plan') if p['id']==item['planVersionId']),{})
                pid=plan.get('projectId')
            result.append(dict(item,record=record['id'],project=self.link('planning-project',pid) if pid else None,
                               employee=self.link('planning-employee',item.get('employeeId')) if item.get('employeeId') else None,
                               role=item.get('roleCode') or demand.get('roleCode'),grade=item.get('gradeCode') or demand.get('gradeCode')))
        return result

    def transitions(self,task):
        if task['id'] in self.transition_cache: return self.transition_cache[task['id']]
        status_map={s['id']:s.get('category') for s in self.records('tracker','statuses')}
        rows=[]
        for h in self.records('tracker','history'):
            if h.get('workItemId')!=task['id']: continue
            sid=h.get('newValues',{}).get('statusId'); at=instant(h.get('occurredAt'))
            category=self.links.get(('tracker-status-category',sid)) or status_map.get(sid)
            if at and category: rows.append((at,category))
        self.transition_cache[task['id']]=sorted(rows)
        return self.transition_cache[task['id']]

    def query(self,rid,claims,query,limit=10000,ceiling=None):
        scope=Scope(self.db,claims,rid); params,slices,first,last=validate_query(rid,query); n=scope.n
        if n==11 and 'employee' in slices and not (scope.allowed & {PM,MB,AN}): raise Problem(403,'FORBIDDEN')
        visible_projects=set(scope.projects)
        if scope.employees:
            for subject in scope.employees:
                visible_projects.update(r[0] for r in self.db.execute('SELECT DISTINCT project_id FROM dwh.report_time_log WHERE user_id=?',(subject,)))
            visible_projects.update(t['project'] for t in self.task_rows() if t.get('employee') in scope.employees and t.get('project'))
        for key,allowed in [('projectIds',visible_projects),('employeeIds',scope.employees)]:
            if key in params and not scope.global_access and not set(params[key])<=allowed:
                # Project roles may choose employees only from their visible
                # rows below; never grant a new scope through a query filter.
                if key=='projectIds' or not scope.projects: raise Problem(403,'FORBIDDEN')
        fresh=self.freshness(n)
        from zoneinfo import ZoneInfo
        if last>datetime.now(ZoneInfo('Europe/Moscow')).date(): self.notes.add('PERIOD_NOT_FINISHED')
        def visible(rows):
            result=[]
            filters={'projectIds':'project','employeeIds':'employee','iterationIds':'iteration','epicIds':'epic',
                     'statuses':'status','priorities':'priority','severities':'severity','types':'type'}
            for row in rows:
                if not scope.permits(row) or (ceiling is not None and not ceiling.permits(row)): continue
                if any(row.get(field) not in params[key] for key,field in filters.items() if key in params): continue
                if any(row.get(p['slice'])!=p['id'] for p in query.get('path',[])): continue
                result.append(row)
            return result
        tasks=visible([t for t in self.task_rows() if day(t.get('createdAt')) is None or day(t['createdAt'])<=last])
        for t in tasks:
            observed=[(at,c) for at,c in self.transitions(t) if at.date()<=last]
            if observed: t['_category']=observed[-1][1]
            elif day(t.get('updatedAt')) and day(t['updatedAt'])>last:
                t['_category']=None; self.notes.add('INCOMPLETE_TASK_HISTORY')
        logs=visible(self.logs(first,last))
        if n==3 and not scope.allowed & {PM,TL,MB,AN}: logs=[]; self.notes.add('LABOR_MEASURES_REDACTED')
        defects=visible(self.qa_rows('defects')) if n in {5,8,9} else []
        runs=visible(self.qa_rows('test-runs')) if n in {7,9} else []
        population=logs if n==1 else defects if n in {5,8} else runs if n==7 else tasks
        demands=[]; allocations=[]; availability=[]; forecasts=[]
        if n in {2,6}:
            def within(row):
                start,end=day(row.get('periodStart') or row.get('date')),day(row.get('periodEnd') or row.get('date'))
                if not start or not end: self.notes.add('MISSING_PLANNING_PERIOD'); return False
                if end<first or start>last: return False
                if start<first or end>last:
                    self.notes.add('PARTIAL_PLANNING_PERIOD_NOT_PRORATED'); return False
                return True
            demands=[r for r in visible(self.planning_rows('demand')) if within(r)]
            allocations=[r for r in visible(self.planning_rows('allocation')) if within(r) and r.get('status')!='CANCELLED']
            for a in self.planning_rows('availability'):
                if not within(a) or a.get('status')!='CONFIRMED': continue
                joins={(r.get('project'),r.get('role'),r.get('grade')) for r in [*allocations,*logs] if r.get('employee')==a.get('employee') and a.get('employee') is not None}
                for project,role,grade in joins:
                    availability.append(dict(a,project=project,role=role,grade=grade))
            forecasts=visible(self.planning_rows('forecast'))
            if n==2: population=[*demands,*allocations,*availability,*logs]
            else: population=[*tasks,*forecasts]
        groups=defaultdict(list)
        for row in population: groups[tuple(row.get(s) for s in slices)].append(row)
        if len(groups)>limit: raise Problem(422,'RESULT_TOO_LARGE')
        matching_cache={}
        def matching(rows,key):
            signature=(id(rows),len(key))
            if signature not in matching_cache:
                partition=defaultdict(list)
                for r in rows:
                    group=tuple(r.get('_task_id') if s=='record' and n!=1 and '_task_id' in r else r.get(s) for s in slices[:len(key)])
                    partition[group].append(r)
                matching_cache[signature]=partition
            return matching_cache[signature].get(key,[])
        velocity_window=visible(self.logs(last-timedelta(days=params.get('velocityWeeks',4)*7-1),last)) if n==6 else []
        def metrics(key):
            ts=matching(tasks,key) if key is not None else tasks
            ls=matching(logs,key) if key is not None else logs
            ds=matching(defects,key) if key is not None else defects
            rs=matching(runs,key) if key is not None else runs
            demand=matching(demands,key) if key is not None else demands
            allocation=matching(allocations,key) if key is not None else allocations
            avail=matching(availability,key) if key is not None else availability
            fc=matching(forecasts,key) if key is not None else forecasts
            actual=round(sum(r['_hours'] for r in ls),4)
            planned=total(number(t.get('plannedHours')) for t in ts)
            remaining=total(number(t.get('remainingHours')) for t in ts)
            done=[t for t in ts if t['_category']=='COMPLETED']
            active=[t for t in ts if t['_category']!='ARCHIVED']
            if n==1: return {'M-01':actual}
            if n==2:
                unique_avail={(r.get('employee'),r.get('date')):r for r in avail}
                capacity=total(number(r.get('availableHours')) for r in unique_avail.values())
                if {r.get('employee') for r in ls}-{r.get('employee') for r in unique_avail.values()}: capacity=None
                need=total(number(r.get('hours')) for r in demand)
                assigned=total(number(r.get('hours')) for r in allocation) if allocation else 0
                if capacity is None: self.notes.add('MISSING_CAPACITY')
                return {'M-01':actual,'M-10':ratio(actual,capacity),'M-11':round(need-assigned,4) if need is not None and assigned is not None else None,
                        'demandHours':need,'allocatedHours':assigned,'availableHours':capacity}
            if n==3: return {'M-01':actual,'M-02':planned,'M-03':remaining,'M-06':ratio(len(done),len(active)),'taskCount':len(ts)}
            if n==4:
                overdue=[t for t in ts if t['_category'] not in {'COMPLETED','ARCHIVED'} and day(t.get('dueDate')) and day(t['dueDate'])<last]
                return {'M-05':len(overdue),'overdueDays':sum((last-day(t['dueDate'])).days for t in overdue),
                        'missingDueDates':sum(day(t.get('dueDate')) is None for t in ts),
                        'lateCompletedDays':sum(max(0,(at.date()-day(t['dueDate'])).days) for t in done for at in [next((at for at,c in self.transitions(t) if c=='COMPLETED'),None)] if at and day(t.get('dueDate')))}
            if n in {5,8,9}:
                opened=closed=reopened=backlog=0; durations=[]; complete=True
                for d in ds:
                    created=day(d.get('createdAt')); history=d.get('history',[])
                    if not created: complete=False; continue
                    events=[(day(h.get('occurredAt')),h.get('newValue') or h.get('status')) for h in history if h.get('field','status')=='status']
                    events=[(at,status) for at,status in events if at]
                    if day(d.get('closedAt')): events.append((day(d['closedAt']),'CLOSED'))
                    closes=sorted({at for at,status in events if status=='CLOSED'})
                    opened+=first<=created<=last
                    closed+=any(first<=at<=last for at in closes)
                    reopened+=any(first<=at<=last and status=='REOPENED' for at,status in events)
                    if closes and first<=closes[0]<=last: durations.append((closes[0]-created).days)
                    if not events and d.get('status')!='OPEN': complete=False
                    state=next((status for at,status in sorted(events,reverse=True) if at<=last),'OPEN')
                    backlog+=created<=last and state!='CLOSED'
                if not complete: self.notes.add('INCOMPLETE_DEFECT_TIMELINE')
                dm={'M-12':{'opened':opened,'closed':closed if complete else None,'remaining':backlog if complete else None},
                    'M-13':median(durations) if durations else None,'M-17':ratio(reopened,closed) if complete else None}
                if n in {5,8}: return {k:v for k,v in dm.items() if k in MEASURES[n]}
            if n in {7,9}:
                run_ids={r['id'] for r in rs}; latest={}
                for r in self.records('qa','test-results'):
                    if r.get('runId') not in run_ids: continue
                    updated=instant(r.get('finishedAt') or r.get('updatedAt'))
                    if updated and updated.date()>last: continue
                    pair=(r['runId'],r.get('testCaseId'))
                    order=(r.get('finishedAt') or r.get('updatedAt') or '',str(r['id']))
                    if pair not in latest or order>latest[pair][0]: latest[pair]=(order,r)
                states=[r['status'] for _,r in latest.values()]
                passed,failed=states.count('PASSED'),states.count('FAILED')
                count=total(number(r.get('caseCount',r.get('summary',{}).get('total'))) for r in rs)
                executed=sum(states.count(k) for k in ['PASSED','FAILED','BLOCKED','SKIPPED'])
                qm={'M-14':ratio(passed,passed+failed),'M-15':ratio(executed,count),
                    'passed':passed,'failed':failed,'blocked':states.count('BLOCKED'),'skipped':states.count('SKIPPED')}
                if n==7: return qm
                self.notes.add('Q-REP-12_DENSITY_NOT_APPROVED')
                return {'M-06':ratio(len(done),len(active)),'M-14':qm['M-14'],'M-16':None,'M-17':dm['M-17'],
                        'candidateDefectDensity':ratio(len(ds),len(done))/10 if done else None}
            if n==6:
                weeks=params.get('velocityWeeks',4)
                window=velocity_window
                if key is not None: window=matching(window,key)
                tempo=sum(r['_hours'] for r in window)/weeks
                forecast=sorted(fc,key=lambda f:f.get('calculatedAt',''))[-1] if fc else None
                if len(fc)>1: self.notes.add('LATEST_FORECAST_SELECTED')
                if not forecast: self.notes.add('MISSING_PLANNING_FORECAST')
                if forecast and forecast.get('quality')!='COMPLETE': self.notes.add('PARTIAL_PLANNING_FORECAST')
                result={'M-01':actual,'M-02':planned,'M-03':remaining,'M-04':max(0,actual-planned) if planned is not None else None,
                        'M-07':round(tempo,4),'M-08':forecast.get('forecastFinish') if forecast else None,
                        'crossCheckFinish':(last+timedelta(days=math.ceil(max(0,remaining)/tempo*7))).isoformat() if remaining is not None and tempo>0 else None,
                        'quality':forecast.get('quality') if forecast else 'PARTIAL',
                        'missingInputs':forecast.get('missingInputs',[]) if forecast else ['FORECAST']}
                if scope.cost:
                    result['M-09']=number(forecast.get('budgetAdjustment')) if forecast else None
                    result['estimatedTotalCost']=number(forecast.get('estimatedTotalCost')) if forecast else None
                    result['currencyCode']=forecast.get('currencyCode') if forecast else None
                return result
            if n==10:
                cycle=[]; lead=[]; weekly=defaultdict(int); daily=[]; known=True
                for t in ts:
                    changes=self.transitions(t); created=instant(t.get('createdAt'))
                    finish=next((at for at,c in changes if c=='COMPLETED'),None)
                    start=next((at for at,c in changes if c=='WORKING'),None)
                    if finish and first<=finish.date()<=last:
                        weekly[finish.strftime('%G-W%V')]+=1
                        if created and finish>=created: lead.append((finish-created).total_seconds()/86400)
                        if start and finish>=start: cycle.append((finish-start).total_seconds()/86400)
                    if not any(c in {'WORKING','BACKLOG'} for _,c in changes): known=False
                observed_last=min(last,datetime.now(ZoneInfo('Europe/Moscow')).date())
                for offset in range(max(0,(observed_last-first).days+1)):
                    observed=first+timedelta(days=offset); count=0
                    for t in ts:
                        current=next((c for at,c in reversed(self.transitions(t)) if at.date()<=observed),None)
                        count+=current=='WORKING'
                    daily.append(count)
                if not known: self.notes.add('MISSING_WORKING_STATUS_MAPPING_OR_HISTORY')
                return {'M-18':{'cycleMedian':median(cycle) if cycle else None,'cycleP85':quantile(cycle,.85),
                                'leadMedian':median(lead) if lead else None,'leadP85':quantile(lead,.85)},
                        'M-19':{'throughput':dict(sorted(weekly.items())),'averageWip':round(sum(daily)/len(daily),4) if known and daily else None}}
            if n==11:
                completed=[]
                for t in done:
                    closed=next((at.date() for at,c in self.transitions(t) if c=='COMPLETED'),day(t.get('completedAt')))
                    if closed is None: self.notes.add('MISSING_TASK_COMPLETION_TIME')
                    elif first<=closed<=last: completed.append(t)
                pairs=[(number(t.get('actualHours')),number(t.get('plannedHours'))) for t in completed]
                pairs=[(a,p) for a,p in pairs if a is not None and p is not None and p>0]
                return {'M-20':{'errorPercent':ratio(sum(a-p for a,p in pairs),sum(p for _,p in pairs)),
                                'correctionCoefficient':median(a/p for a,p in pairs) if pairs else None,
                                'eligibleTasks':len(pairs)}}
            raise Problem(422,'INVALID_PARAMETER')
        rows=[]
        for key in sorted(groups,key=lambda k:packed(k)):
            dimensions={s:{'id':v,'label':str(v) if v is not None else 'не задано'} for s,v in zip(slices,key)}
            rows.append(dict(dimensions,**metrics(key)))
        totals=metrics(None)
        subtotals=[]
        for depth in range(1,len(slices)):
            prefixes=sorted({key[:depth] for key in groups},key=packed)
            subtotals.append({'slice':slices[:depth],'rows':[dict({s:{'id':v,'label':str(v) if v is not None else 'не задано'} for s,v in zip(slices,key)},**metrics(key)) for key in prefixes]})
        columns=[{'key':s,'title':DIMENSION_TITLES[s],'type':'dimension'} for s in slices]
        columns += [{'key':m,'title':TITLES[m],'type':'measure','formula':FORMULAS[m]} for m in MEASURES[n] if m!='M-09' or scope.cost]
        result={'reportId':rid,'reportVersion':1,'generatedAt':stamp(),'freshness':fresh,'columns':columns,
                'rows':rows,'subtotals':subtotals,'totals':totals,'notes':sorted(self.notes),'comparison':None}
        if not rows: result['notes'].append('NO_DATA')
        if query.get('compareWithPrevious'):
            length=(last-first).days+1; previous=dict(query,compareWithPrevious=False)
            previous['params']=dict(params,periodFrom=(first-timedelta(days=length)).isoformat(),periodTo=(first-timedelta(days=1)).isoformat())
            old=self.query(rid,claims,previous,limit,ceiling)
            result['comparison']={'periodFrom':previous['params']['periodFrom'],'periodTo':previous['params']['periodTo'],
                                  'totals':old['totals'],'delta':{k:round(v-old['totals'][k],4) for k,v in totals.items()
                                  if type(v) in (int,float) and type(old['totals'].get(k)) in (int,float)} if rows and old['rows'] else None}
        return result
