"""Transactional source events: durable deduplication, retries, DLQ and replay.

Schema owners remain outside Reports. Only read their local contract files.
Broker offsets are acknowledged by the runner after this module commits.
"""
import hashlib
import json
import os
import re
import uuid
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker, validators
from db import Database
from product_store import packed, stamp
from star import timestamp, refresh
from ops import event

TOPICS={'tracker':'task-tracker.events.v1','qa-run':'dev.qa.test-run.v1',
        'qa-defect':'dev.qa.defect.v1','planning':'dev.planning.signals.v1'}
ROOT=Path(__file__).resolve().parent.parent.parent
CONTRACT_ROOT=Path(os.getenv('REPORTS_CONTRACT_ROOT',str(ROOT)))


def multiple_of(validator, divisor, value, schema):
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if Decimal(str(value)) % Decimal(str(divisor)):
            from jsonschema import ValidationError
            yield ValidationError('Invalid decimal precision')
Validator=validators.extend(Draft202012Validator,{'multipleOf':multiple_of})


@lru_cache(maxsize=1)
def schemas():
    tracker=json.loads((CONTRACT_ROOT/'task-tracker/docs/block-g-api-and-events/event-schemas.json').read_text())
    qa={}
    for block in re.findall(r'```json\s*(.*?)```',(CONTRACT_ROOT/'qa/docs/140.event-schema.md').read_text(),re.S):
        value=json.loads(block)
        if '$id' in value:qa[value['$id'].split('.')[0]]=value
    planning={p.name.removesuffix('.schema.json'):json.loads(p.read_text()) for p in (CONTRACT_ROOT/'planning-system/docs/contracts/events').glob('*.schema.json')}
    return tracker,qa,planning


def validate(body,topic,key):
    if not isinstance(body,dict):raise ValueError('INVALID_ENVELOPE')
    tracker,qa,planning=schemas();name=body.get('eventType');checker=FormatChecker()
    if topic==TOPICS['tracker']:
        Validator(tracker,format_checker=checker).validate(body)
        source='tracker';aggregate=body['aggregateId']
    elif topic in (TOPICS['qa-run'],TOPICS['qa-defect']):
        Validator(qa['QaSystemEvent'],format_checker=checker).validate(body)
        Validator(qa[name],format_checker=checker).validate(body['payload'])
        source='qa';defect=name=='DefectChanged'
        if topic!=TOPICS['qa-defect' if defect else 'qa-run']:raise ValueError('INVALID_TOPIC')
        aggregate=body['payload']['defectId' if defect else 'runId']
        if name=='TestRunCompleted':
            counts=body['payload']['counts']
            if sum(counts[n] for n in ['passed','failed','blocked','notRun','skipped'])!=counts['total']:raise ValueError('INVALID_COUNTS')
    elif topic==TOPICS['planning'] and name in planning:
        Validator(planning[name],format_checker=checker).validate(body)
        source='planning';aggregate=body['projectId']
    else:raise ValueError('INVALID_TOPIC_OR_TYPE')
    if not aggregate or key!=aggregate:raise ValueError('INVALID_PARTITION_KEY')
    if not timestamp(body['occurredAt']):raise ValueError('INVALID_TIME')
    return source,str(aggregate)


def reload_request(db,source,identity,at,reason):
    db.execute('''INSERT INTO etl.reload_request VALUES (?,?,?,?,'PENDING') ON CONFLICT(source,aggregate_id)
      DO UPDATE SET requested_at=excluded.requested_at,reason=excluded.reason,status='PENDING' ''',(source,identity,at,reason))


def apply(db,body,source,identity,offset):
    name=body['eventType'];p=body['payload'];at=timestamp(body['occurredAt']);eid=body['eventId']
    if source=='planning':reload_request(db,source,identity,at,name);return
    if source=='tracker':
        changes={};entity='work-items';target=identity
        if name=='WorkItemCreated':changes=dict(p,createdAt=at)
        elif name=='WorkItemFieldsChanged':
            # Task totals are replaced, never added to fact_time_log. Only
            # TimeLogged supplies the hours ledger used by M-01.
            fields={'title','plannedHours','actualHours','remainingHours','dueDate','startDate','projectId','iterationId','priorityId','type','parentId','isDeleted'}
            changes={k:v for k,v in p['newValues'].items() if k in fields and k in p['changedFields']}
        elif name=='AssigneeChanged':changes={'assigneeId':p['newAssigneeId']}
        elif name=='StatusChanged':
            changes={'statusId':p['toStatusId']}
            history={'id':eid,'workItemId':identity,'occurredAt':at,'actorId':body.get('actor'),
                     'oldValues':{'statusId':p['fromStatusId']},'newValues':{'statusId':p['toStatusId']}}
            db.execute('INSERT INTO dwh.source_record VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING',('tracker','history',eid,packed(history),at))
        elif name=='TimeLogged':
            entity='time-logs';target=p['timeLogId'];changes=dict(p,workItemId=identity)
        elif name=='WorkItemHardDeleted':
            if p['workItemId']!=identity:raise ValueError('AGGREGATE_MISMATCH')
            changes={'isDeleted':True}
            db.execute('UPDATE dwh.fact_time_log SET is_deleted=1 WHERE work_item_id=?',(identity,))
        elif name in {'IterationActivated','IterationCompleted','IterationCompositionChanged'}:
            entity='iterations';target=p.get('iterationId',identity)
            changes={'state':'COMPLETED' if name=='IterationCompleted' else 'ACTIVE'} if name!='IterationCompositionChanged' else {}
            reload_request(db,source,identity,at,name)
        elif name!='NotificationCreated':reload_request(db,source,identity,at,name)
        if changes:
            payload,accepted=event(db,source,entity,target,changes,at,offset)
            if name=='TimeLogged' and accepted:
                task=db.execute("SELECT payload FROM ops.work_item WHERE source='tracker' AND id=?",(identity,)).fetchone()
                project=json.loads(task[0]).get('projectId') if task else None
                if not project:
                    # Do not advance this partition until metadata can be resolved.
                    raise ValueError('MISSING_PROJECT_METADATA')
                cents=int(Decimal(str(payload['hours']))*100)
                db.execute('''INSERT INTO dwh.fact_time_log(id,user_id,project_id,work_item_id,logged_date,hours_cents)
                  VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET user_id=excluded.user_id,project_id=excluded.project_id,
                  work_item_id=excluded.work_item_id,logged_date=excluded.logged_date,hours_cents=excluded.hours_cents''',
                  (target,payload['userId'],project,identity,payload['loggedDate'],cents))
        return
    entity='defects' if name=='DefectChanged' else 'test-runs';changes=dict(p)
    if name=='TestResultRecorded':
        entity='test-results';identity=p['resultId']
        run=db.execute("SELECT payload FROM ops.test_run WHERE source='qa' AND id=?",(p['runId'],)).fetchone()
        if run and json.loads(run[0]).get('status') in {'COMPLETED','FINISHED','ABORTED'}:return
        changes['finishedAt']=at
    elif name=='TestRunStarted':changes['status']='IN_PROGRESS'
    elif name=='TestRunCompleted':changes.update(caseCount=p['counts']['total'],summary=p['counts'])
    if name=='DefectChanged':
        existing=db.execute("SELECT payload FROM ops.defect WHERE source='qa' AND id=?",(identity,)).fetchone()
        history=json.loads(existing[0]).get('history',[]) if existing else []
        if p['change'] in {'CREATED','STATUS_CHANGED'}:
            history=history+[{'field':'status','oldValue':p.get('previousStatus'),'newValue':p['status'],'occurredAt':at,'eventId':eid}]
        changes['history']=sorted(history,key=lambda h:(h.get('occurredAt',''),h.get('eventId','')))
        if p['change']=='CREATED':changes['createdAt']=at
        # Transition history is append-only even when a delayed state is ignored.
        event(db,source,entity,identity,{'history':changes.pop('history')},stamp(),offset)
    event(db,source,entity,identity,changes,at,offset)


def checkpoint(db,topic,partition,offset):
    db.execute('''INSERT INTO etl.event_checkpoint VALUES (?,?,?,?) ON CONFLICT(topic,partition_id)
      DO UPDATE SET next_offset=CASE WHEN excluded.next_offset>etl.event_checkpoint.next_offset THEN excluded.next_offset
      ELSE etl.event_checkpoint.next_offset END,updated_at=excluded.updated_at''',(topic,partition,offset+1,stamp()))


def process(db,topic,partition,offset,key,raw,*,projector=refresh,replay=False):
    """True means durable processing/DLQ; False means retry this same offset."""
    digest=hashlib.sha256(raw).hexdigest();body=None
    try:
        if len(raw)>1024*1024:raise ValueError('EVENT_TOO_LARGE')
        body=json.loads(raw);source,identity=validate(body,topic,key)
        digest=hashlib.sha256(packed(body).encode()).hexdigest()
        with db.transaction():
            if db.sqlite:db.execute('BEGIN IMMEDIATE')
            else:db.execute("SELECT pg_advisory_xact_lock(hashtext('reports-star-refresh'))")
            route=db.execute('SELECT topic,partition_id FROM etl.event_route WHERE source=? AND aggregate_id=?',(source,identity)).fetchone()
            if route and tuple(route)!=(topic,partition):raise ValueError('AGGREGATE_PARTITION_CHANGED')
            db.execute('INSERT INTO etl.event_route VALUES (?,?,?,?) ON CONFLICT DO NOTHING',(source,identity,topic,partition))
            old=db.execute('SELECT body_hash FROM etl.processed_event WHERE event_id=?',(body['eventId'],)).fetchone()
            if old and old[0]!=digest:raise ValueError('EVENT_ID_COLLISION')
            position=db.execute('SELECT next_offset FROM etl.event_checkpoint WHERE topic=? AND partition_id=?',(topic,partition)).fetchone()
            if position and offset<position[0] and not replay:return True
            if not old:
                apply(db,body,source,identity,offset)
                projector(db,body['occurredAt'])
                db.execute('INSERT INTO etl.processed_event VALUES (?,?,?,?,?,?,?,?)',(body['eventId'],digest,source,body['eventType'],identity,body['occurredAt'],'APPLIED',stamp()))
            if not replay:checkpoint(db,topic,partition,offset)
            db.execute('DELETE FROM etl.event_failure WHERE topic=? AND partition_id=? AND offset_id=?',(topic,partition,offset))
        return True
    except Exception:
        # No exception bodies, DSNs, raw broker data or schema values in logs.
        db.connection.rollback()
        with db.transaction():
            if not db.sqlite:db.execute("SELECT pg_advisory_xact_lock(hashtext('reports-star-refresh'))")
            old=db.execute('SELECT attempts FROM etl.event_failure WHERE topic=? AND partition_id=? AND offset_id=?',(topic,partition,offset)).fetchone()
            attempts=(old[0] if old else 0)+1
            safe=None
            # Invalid envelopes remain hash-only. Valid business events may be
            # stored privately in PostgreSQL for operator replay.
            try:
                validate(body,topic,key);safe=packed(body)
            except Exception:pass
            db.execute('''INSERT INTO etl.event_failure VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(topic,partition_id,offset_id)
              DO UPDATE SET attempts=excluded.attempts,updated_at=excluded.updated_at''',(topic,partition,offset,attempts,digest,'EVENT_REJECTED',safe,stamp()))
            if attempts>=3 and not replay:
                db.execute('INSERT INTO etl.event_dlq VALUES (?,?,?,?,?,?,?,?,NULL) ON CONFLICT DO NOTHING',
                           (topic,partition,offset,body.get('eventId') if isinstance(body,dict) else None,digest,'EVENT_REJECTED',safe,stamp()))
                checkpoint(db,topic,partition,offset)
                # Broker DLQ contains references and a digest, never source
                # payloads or personal values. The replay payload stays in PG.
                dlq_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'reports-dlq:{topic}:{partition}:{offset}'))
                notice={'eventId':dlq_id,'sourceTopic':topic,'partition':partition,'offset':offset,'bodyHash':digest,'reason':'EVENT_REJECTED'}
                db.execute('INSERT INTO etl.outbox(event_id,topic,partition_key,payload,created_at) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING',
                    (dlq_id,'dev.reports.dlq.v1',topic+':'+str(partition),packed(notice),stamp()))
        return attempts>=3 and not replay


def replay_dlq(db,topic,partition,offset):
    row=db.execute('SELECT payload FROM etl.event_dlq WHERE topic=? AND partition_id=? AND offset_id=? AND replayed_at IS NULL',(topic,partition,offset)).fetchone()
    db.connection.rollback()
    if not row or not row[0]:return False
    body=json.loads(row[0]);key=body.get('aggregateId') or body.get('projectId') or body['payload'].get('runId') or body['payload'].get('defectId')
    if not process(db,topic,partition,offset,key,row[0].encode(),replay=True):return False
    with db.transaction():db.execute('UPDATE etl.event_dlq SET replayed_at=? WHERE topic=? AND partition_id=? AND offset_id=?',(stamp(),topic,partition,offset))
    return True
