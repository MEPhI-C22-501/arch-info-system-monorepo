import copy
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from server import storage as db
from server.auth import Actor, DEMO_PORTFOLIO as PORT, DEMO_PROJECT as PID
from server.seed import stable
from test_application import call, headers, confirm

VID=stable('plan')


def workbook(client,path,role='R-02'):
    response=client.get('/api/v1/downloads/'+path,headers=headers(role))
    assert response.status_code==200,response.text
    assert response.headers['content-type'].startswith('application/vnd.openxmlformats')
    assert 'attachment;' in response.headers['content-disposition']
    return load_workbook(BytesIO(response.content))


def revision():
    with db.engine.connect() as c:return db.find(c,'plan',VID)['data']['revision']


def assignment_body(employee='employees/demo-2'):
    return {'demandId':stable('demand'),'employeeId':employee,'date':'2026-10-05','hours':2}


def test_project_cards_and_export_share_filters_and_visibility(client):
    call(client,'POST','projects',{'portfolioId':PORT,'programId':None,'code':'SECOND','name':'Другой проект',
         'goal':'Проверка фильтра','managerSubject':'someone-else'},expected=201)
    cards=call(client,'GET','project-cards?q=ERP&status=DRAFT&dateFrom=2026-10-05&dateTo=2026-10-09')
    assert cards['total']==1 and cards['items'][0]['id']==PID
    book=workbook(client,'projects.xlsx?q=ERP&status=DRAFT&dateFrom=2026-10-05&dateTo=2026-10-09')
    assert book['Проекты'].max_row==2
    assert book['Проекты']['A2'].value=='ERP-A'
    assert book['Проекты'].freeze_panes=='A2' and book['Проекты'].auto_filter.ref
    assert book['Проекты']['H2'].value.date().isoformat()=='2026-10-05'
    assert call(client,'GET','project-cards',role='R-03')['total']==1
    assert workbook(client,'projects.xlsx',role='R-03')['Проекты'].max_row==2
    assert workbook(client,'projects.xlsx?q=НетСовпадения')['Проекты'].max_row==1
    assert 'Фильтры' in book.sheetnames


def test_assign_employee_to_specific_work_and_revision(client):
    options=call(client,'GET','resource-options?projectId='+PID)
    assert len(options['employees'])==2
    assert options['demands'][0]['workName']=='Интерфейс'
    key=str(uuid4());rev=revision()
    created=call(client,'POST',f'versions/{VID}/assignments',assignment_body(),revision=rev,key=key,expected=201)
    assert created['assignment']['employeeId']=='employees/demo-2'
    assert created==call(client,'POST',f'versions/{VID}/assignments',assignment_body(),revision=rev,key=key,expected=201)
    call(client,'POST',f'versions/{VID}/assignments',assignment_body(),revision=revision(),expected=409)
    changed=call(client,'PATCH',f'versions/{VID}/assignments/'+created['assignment']['id'],
        {**assignment_body(),'hours':3},revision=revision())
    assert changed['assignment']['hours']==3 and changed['assignment']['status']=='PROPOSED'
    call(client,'PATCH',f'versions/{VID}/assignments/'+created['assignment']['id'],
        {**assignment_body(),'status':'CANCELLED'},revision=rev,expected=412)
    result=call(client,'GET','assignments?projectId='+PID+'&employeeId=employees/demo-2')
    assert result['total']==1 and result['items'][0]['workName']=='Интерфейс'


def test_assignment_export_filters_and_resource_scope(client,monkeypatch):
    call(client,'POST',f'versions/{VID}/assignments',assignment_body(),revision=revision(),expected=201)
    book=workbook(client,'assignments.xlsx?projectId='+PID+'&employeeId=employees/demo-2&status=PROPOSED&dateFrom=2026-10-05&dateTo=2026-10-05')
    assert book['Назначения'].max_row==2
    assert book['Назначения']['G2'].value=='employees/demo-2'
    assert book['Назначения']['I2'].value==2
    assert workbook(client,'assignments.xlsx?dateFrom=2027-01-01')['Назначения'].max_row==1
    monkeypatch.setattr('server.ui_features.actor',lambda req:Actor('resource',{'R-04'},set(),{PORT},{PID},{'employees/demo-1'}))
    assert [r['employeeId'] for r in call(client,'GET','assignments',role='R-04')['items']]==['employees/demo-1']
    own=workbook(client,'assignments.xlsx',role='R-04')
    assert own['Назначения'].max_row==2 and own['Назначения']['G2'].value=='employees/demo-1'
    assert len(call(client,'GET','resource-options?projectId='+PID,role='R-04')['employees'])==1
    call(client,'POST',f'versions/{VID}/assignments',assignment_body(),role='R-04',revision=revision(),expected=403)


def test_assignment_foreign_work_employee_and_immutable_plan(client):
    call(client,'POST',f'versions/{VID}/assignments',{**assignment_body(),'demandId':str(uuid4())},revision=revision(),expected=422)
    call(client,'POST',f'versions/{VID}/assignments',assignment_body('employees/unknown'),revision=revision(),expected=403)
    call(client,'POST',f'versions/{VID}/assignments',{**assignment_body(),'date':'2026-11-01'},revision=revision(),expected=422)
    call(client,'POST',f'versions/{VID}/assignments',{**assignment_body(),'status':'CONFIRMED'},revision=revision(),expected=422)
    with db.engine.begin() as c:
        row=db.find(c,'plan',VID);v=copy.deepcopy(row['data']);v.update(status='APPROVED',dataAsOf=db.now());db.put(c,'plan',v,PORT,PID)
    call(client,'POST',f'versions/{VID}/assignments',assignment_body(),revision=revision(),expected=409)


def test_assignment_selects_second_work_instead_of_first(client):
    with db.engine.begin() as c:
        v=copy.deepcopy(db.find(c,'plan',VID)['data'])
        item={**next(x for x in v['items'] if x['type']=='FEATURE'),'id':str(uuid4()),'logicalItemId':str(uuid4()),'name':'Вторая работа'}
        demand={**v['demands'][0],'id':str(uuid4()),'planItemId':item['id'],'hours':2}
        v['items'].append(item);v['demands'].append(demand);v['revision']+=1;db.put(c,'plan',v,PORT,PID)
    created=call(client,'POST',f'versions/{VID}/assignments',{**assignment_body(),'demandId':demand['id']},revision=revision(),expected=201)
    row=next(x for x in call(client,'GET','assignments')['items'] if x['id']==created['assignment']['id'])
    assert row['workName']=='Вторая работа' and row['planItemId']==item['id']


def test_features_require_authentication(client):
    for path in ['downloads/projects.xlsx','downloads/assignments.xlsx','project-cards','assignments','resource-options?projectId='+PID]:
        assert client.get('/api/v1/'+path).status_code==401


def test_cancelled_assignment_stays_cancelled_when_confirming_resources(client):
    created=call(client,'POST',f'versions/{VID}/assignments',assignment_body(),revision=revision(),expected=201)
    call(client,'PATCH',f'versions/{VID}/assignments/'+created['assignment']['id'],
        {**assignment_body(),'status':'CANCELLED'},revision=revision())
    row=next(x for x in call(client,'GET','availability',role='R-04') if x['data']['employeeId']=='employees/demo-2' and x['data']['date']=='2026-10-05')
    call(client,'PUT','availability/'+row['data']['id'],{**row['data'],'nominalHours':7,'availableHours':7},role='R-04',revision=row['revision'])
    confirm(client)
    rows=call(client,'GET','assignments')['items']
    assert next(r for r in rows if r['id']==created['assignment']['id'])['status']=='CANCELLED'
    assert call(client,'GET','workspace?projectId='+PID)['confirmed'] is True
    scenario=call(client,'POST',f'projects/{PID}/versions',{'baseVersionId':VID,'kind':'SCENARIO','name':'Копия без отменённых назначений'},expected=201)
    assert any(x['employeeId']=='employees/demo-2' and x['status']=='CANCELLED' for x in scenario['allocations'])


@pytest.mark.parametrize('query_string',['status=UNKNOWN','dateFrom=bad','dateFrom=2026-10-09&dateTo=2026-10-01','q=a&q=b','unknown=x'])
def test_export_rejects_invalid_filters(client,query_string):
    assert client.get('/api/v1/downloads/projects.xlsx?'+query_string,headers=headers()).status_code==422
    assert client.get('/api/v1/project-cards?'+query_string,headers=headers()).status_code==422


@pytest.mark.parametrize('role',['R-05','R-06','S-06'])
def test_exports_and_choices_deny_unrelated_roles(client,role):
    for path in ['downloads/projects.xlsx','downloads/assignments.xlsx','project-cards','assignments','resource-options?projectId='+PID]:
        assert client.get('/api/v1/'+path,headers=headers(role)).status_code==403


def test_excel_keeps_user_text_literal_and_excludes_other_portfolios(client):
    name='=HYPERLINK("https://example.invalid","test")'
    p=call(client,'GET','projects/'+PID)
    call(client,'PATCH','projects/'+PID,{'name':name,'goal':'Literal export'},revision=p['revision'])
    with db.engine.begin() as c:
        foreign={**p,'id':str(uuid4()),'portfolioId':str(uuid4()),'code':'SECRET','name':'Другой портфель'}
        db.put(c,'project',foreign,foreign['portfolioId'],foreign['id'])
    book=workbook(client,'projects.xlsx')
    assert book['Проекты'].max_row==2
    assert book['Проекты']['B2'].value==name and book['Проекты']['B2'].data_type=='s'
    assert not any(cell.data_type=='f' for row in book['Проекты'] for cell in row)


def test_planning_choices_scope_and_manager_identity(client,monkeypatch):
    data=call(client,'GET','planning-options?portfolioId='+PORT)
    assert {'id':'developer','name':'Разработчик'} in data['specialties']
    assert len(data['grades'])>=4
    assert any(x['id']=='demo-R-03' for x in data['managers'])
    assert call(client,'GET','planning-options?portfolioId='+PORT,role='R-03')['managers'][0]['id']=='demo-R-03'
    call(client,'GET','planning-options?portfolioId='+str(uuid4()),expected=404)
    call(client,'GET','planning-options?portfolioId='+PORT,role='R-05',expected=403)
    with db.engine.begin() as c:
        db.put(c,'manager',{'id':str(uuid4()),'subject':'another-manager','displayName':'Второй руководитель'},PORT)
    assert {'id':'another-manager','name':'Второй руководитель'} in call(client,'GET','planning-options?portfolioId='+PORT)['managers']
    monkeypatch.setattr('server.ui_features.actor',lambda req:Actor('planner',{'R-02'},set(),{PORT},{PID},set()))
    monkeypatch.setenv('APP_ENV','production')
    # Existing manager subjects remain available without creating imaginary accounts.
    assert any(x['id']=='demo-R-03' for x in call(client,'GET','planning-options?portfolioId='+PORT)['managers'])


def test_project_timeline_real_records_and_scope(client,monkeypatch):
    timeline=call(client,'GET','project-timeline?projectId='+PID)
    assert timeline['id']==VID and len(timeline['items'])==4
    assert any(x['name']=='Интерфейс' and x['start']=='2026-10-05' for x in timeline['items'])
    assert 'allocations' not in timeline and 'baselineBudget' not in timeline
    call(client,'GET','project-timeline?projectId='+str(uuid4()),expected=404)
    call(client,'GET','project-timeline?projectId='+PID,role='R-05',expected=403)
    monkeypatch.setattr('server.ui_features.actor',lambda req:Actor('other',{'R-03'},set(),{PORT},set(),set()))
    call(client,'GET','project-timeline?projectId='+PID,expected=404)
