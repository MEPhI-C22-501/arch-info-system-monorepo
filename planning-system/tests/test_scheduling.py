import copy
from uuid import uuid4
import pytest
from fastapi import HTTPException
from server import storage as db
from server.seed import stable
from server.scheduling import reschedule
from test_application import call
from test_project_features import PID, PORT, VID, revision


def seeded():
    with db.engine.connect() as c:return copy.deepcopy(db.find(c,'plan',VID)['data'])


def test_move_synchronizes_tree_fs_demands_and_assignments(client):
    plan=seeded();plan['dependencies']=[{'id':str(uuid4()),'predecessorId':stable('feature'),'successorId':stable('milestone'),'type':'FS','lagWorkingDays':0}]
    plan['allocations'][0]['status']='CONFIRMED'
    result,moved=reschedule(plan,stable('feature'),'2026-10-10','2026-10-10')
    items={x['id']:x for x in result['items']}
    assert items[stable('milestone')]['start']=='2026-10-12'  # FS skips weekend
    assert items[stable('release')]['finish']=='2026-10-12'
    assert result['demands'][0]['periodStart']==result['demands'][0]['periodEnd']=='2026-10-10'
    assert result['allocations'][0]['date']=='2026-10-10'
    assert result['allocations'][0]['status']=='PROPOSED'
    assert result['allocations'][0]['hours']==6
    assert stable('milestone') in moved and plan['items'][2]['start']=='2026-10-05'


def test_group_move_and_resize_preserve_hours_and_cancelled_state(client):
    plan=seeded();plan['allocations'][0]['status']='CANCELLED'
    moved,_=reschedule(plan,stable('release'),'2026-10-07','2026-10-11')
    assert moved['demands'][0]['periodStart']=='2026-10-07'
    assert moved['allocations'][0]['status']=='CANCELLED'
    assert moved['items'][3]['finish']=='2026-10-11'
    resized,_=reschedule(plan,stable('feature'),'2026-10-05','2026-10-08')
    assert resized['demands'][0]['periodEnd']=='2026-10-08'
    assert resized['demands'][0]['hours']==6
    with pytest.raises(HTTPException):reschedule(plan,stable('release'),'2026-10-08','2026-10-09')


def test_timeline_command_atomic_revision_and_idempotency(client):
    body={'itemId':stable('feature'),'start':'2026-10-06','finish':'2026-10-07'}
    key=str(uuid4());rev=revision()
    result=call(client,'PATCH',f'versions/{VID}/timeline',body,revision=rev,key=key)
    assert result==call(client,'PATCH',f'versions/{VID}/timeline',body,revision=rev,key=key)
    assert revision()==rev+1
    call(client,'PATCH',f'versions/{VID}/timeline',body,revision=rev,expected=412)
    before=seeded()
    call(client,'PATCH',f'versions/{VID}/timeline',{**body,'finish':'2027-01-01'},revision=revision(),expected=422)
    assert seeded()==before
    call(client,'PATCH',f'versions/{VID}/timeline',{**body,'start':'bad-date'},revision=revision(),expected=422)
    call(client,'PATCH',f'versions/{VID}/timeline',body,revision=revision(),role='R-04',expected=403)
    with db.engine.begin() as c:
        v=seeded();v['status']='APPROVED';db.put(c,'plan',v,PORT,PID)
    call(client,'PATCH',f'versions/{VID}/timeline',body,revision=revision(),expected=409)


def test_cross_project_work_and_impossible_parent_dependency_rejected(client):
    plan=seeded()
    with pytest.raises(HTTPException):reschedule(plan,str(uuid4()),'2026-10-06','2026-10-06')
    plan['dependencies']=[{'id':str(uuid4()),'predecessorId':stable('release'),'successorId':stable('feature'),'type':'FS','lagWorkingDays':0}]
    with pytest.raises(HTTPException):reschedule(plan,stable('feature'),'2026-10-06','2026-10-06')
