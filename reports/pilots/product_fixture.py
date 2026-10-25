"""Small complete synthetic business example, keeping BI totals at 11.25 h."""
from copy import deepcopy
from demo import fixture as compact
from acceptance_data import uid


def business_fixture(subjects):
    tracker=compact(subjects);t=tracker['work-items'][0];project=t['projectId'];task=t['id']
    working=t['statusId'];done=uid(900);start='2026-10-01T00:00:00Z';finish='2026-10-04T00:00:00Z'
    t.update(assigneeId=subjects['member1'],dueDate='2026-10-02',plannedHours=10,actualHours=11.25,
             remainingHours=-1.25,statusId=done,updatedAt=finish)
    tracker['statuses'].append(dict(tracker['statuses'][0],id=done,name='Done',category='COMPLETED',boardOrder=2))
    tracker['history']=[dict(tracker['history'][0],id=uid(901),occurredAt=start,newValues={'statusId':working}),
                        dict(tracker['history'][0],id=uid(902),occurredAt=finish,newValues={'statusId':done})]
    plan,planning_project,item,demand,run,case,defect=[uid(910+i) for i in range(7)]
    forecast=uid(920)
    planning={
      'plan':[{'id':plan,'data':{'id':plan,'projectId':planning_project,'items':[{'id':item}]}}],
      'demand':[{'id':demand,'data':{'id':demand,'planItemId':item,'roleCode':'developer','gradeCode':'middle',
                   'periodStart':'2026-10-01','periodEnd':'2026-10-31','hours':20}}],
      'allocation':[{'id':uid(921),'data':{'id':uid(921),'demandId':demand,'employeeId':'employees/1',
                        'date':'2026-10-01','hours':8,'status':'CONFIRMED'}}],
      'availability':[{'id':uid(922),'data':{'id':uid(922),'employeeId':'employees/1','date':'2026-10-01',
                           'availableHours':8,'status':'CONFIRMED'}}],
      'forecast':[{'id':forecast,'data':{'id':forecast,'planVersionId':plan,'dataAsOf':finish,'calculatedAt':finish,
                       'quality':'PARTIAL','missingInputs':['RATE'],'remainingHours':-1.25,'forecastFinish':None}}]}
    qa={'test-plans':[{'id':uid(930),'planningProjectId':planning_project,'trackerIterationId':t['iterationId']}],
        'test-runs':[{'id':run,'planId':uid(930),'status':'FINISHED','caseCount':2}],
        'test-cases':[{'id':case},{'id':uid(931)}],
        'test-results':[{'id':uid(932),'runId':run,'testCaseId':case,'status':'PASSED','finishedAt':finish},
                        {'id':uid(933),'runId':run,'testCaseId':uid(931),'status':'BLOCKED','finishedAt':finish}],
        'defects':[{'id':defect,'planningProjectId':planning_project,'createdAt':start,'status':'REOPENED',
                    'severity':'MAJOR','authorId':subjects['member1'],
                    'history':[{'field':'status','newValue':'CLOSED','occurredAt':'2026-10-03T00:00:00Z'},
                               {'field':'status','newValue':'REOPENED','occurredAt':finish}]}]}
    reference={name:[{'id':1,'name':'Synthetic','is_deleted':False}] for name in ['employees','org_units','positions','project_roles','grades']}
    links=[('planning-project',planning_project,project),('planning-employee','employees/1',subjects['member1']),
           ('hr-employee','1',subjects['member1']),('tracker-status-category',working,'WORKING')]
    return {'tracker':tracker,'planning':planning,'qa':qa,'reference':reference,'links':links}
