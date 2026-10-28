"""Idempotent synthetic fixture, never writes HR or real accounts."""
import uuid
from . import storage as db
from .auth import DEMO_PORTFOLIO as PORT, DEMO_PROJECT as PROJECT

def stable(name):return str(uuid.uuid5(uuid.NAMESPACE_URL,'planning-demo:'+name))
def seed():
    with db.engine.begin() as c:
        if db.find(c,'project',PROJECT):return
        db.put(c,'portfolio',{'id':PORT,'code':'DEMO','name':'Портфель ERP','status':'ACTIVE','ownerSubject':'demo-R-01'},PORT)
        db.put(c,'project',{'id':PROJECT,'portfolioId':PORT,'programId':None,'code':'ERP-A','name':'ERP · планирование ресурсов',
            'goal':'Демонстрация планирования','managerSubject':'demo-R-03','revision':1,'priority':1,'status':'DRAFT','activePlanVersionId':None},PORT,PROJECT)
        items=[]
        for n,kind,parent,start,finish,h in [('release','RELEASE',None,'2026-10-05','2026-10-09',6),('epic','EPIC','release','2026-10-05','2026-10-09',6),
            ('feature','FEATURE','epic','2026-10-05','2026-10-05',6),('milestone','MILESTONE','release','2026-10-09','2026-10-09',0)]:
            items.append({'id':stable(n),'logicalItemId':stable('logical-'+n),'parentItemId':stable(parent) if parent else None,
                'type':kind,'name':{'release':'Релиз ERP 1.0','epic':'Планирование','feature':'Интерфейс','milestone':'Приёмка'}[n],
                'start':start,'finish':finish,'plannedHours':h})
        vid=stable('plan')
        plan={'id':vid,'projectId':PROJECT,'name':'Годовой план','planningMode':'ANNUAL','horizonStart':'2026-10-05','horizonEnd':'2026-12-31',
            'items':items,'dependencies':[],'demands':[{'id':stable('demand'),'planItemId':stable('feature'),'roleCode':'developer','gradeCode':'middle','periodStart':'2026-10-05','periodEnd':'2026-10-05','hours':6}],
            'allocations':[{'id':stable('allocation'),'demandId':stable('demand'),'employeeId':'employees/demo-1','date':'2026-10-05','hours':6,'status':'PROPOSED'}],
            'revision':1,'contentRevision':1,'reviewRound':0,'kind':'PLAN','baseVersionId':None,'versionNumber':1,'status':'DRAFT','dataAsOf':None,
            'baselineBudget':18000,'currencyCode':'RUB','reviewers':[],'decisions':[]}
        db.put(c,'plan',plan,PORT,PROJECT)
        for employee in ['employees/demo-1','employees/demo-2']:
            for day in range(5,10):
                identifier=stable(employee+str(day));absence=4 if employee.endswith('1') and day==5 else 0
                db.put(c,'availability',{'id':identifier,'employeeId':employee,'date':f'2026-10-{day:02}','calendarCode':'demo-week','timeZone':'Europe/Moscow',
                    'nominalHours':8,'absenceHours':absence,'availableHours':8-absence,'status':'CONFIRMED'},PORT)
        db.put(c,'task',{'id':stable('task'),'externalTaskId':'fixture-task-1','sourceRevision':1,'sourceChangedAt':'2026-10-05T12:00:00Z',
            'logicalItemId':stable('logical-feature'),'taskStatus':'InProgress','actualHours':12,'sourceRemainingHours':-6,'remainingHours':None,'isDeleted':False},PORT,PROJECT)
        db.put(c,'forecast_input',{'id':vid,'etc':8,'rate':1000,'currencyCode':'RUB','author':'synthetic-fixture','asOf':'2026-10-05T12:00:00Z'},PORT,PROJECT)
