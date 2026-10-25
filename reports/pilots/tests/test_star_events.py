"""Independent star/event invariants on both SQLite and real PostgreSQL."""
import json
import os
import time
import unittest
import uuid
from datetime import datetime,timezone
from unittest.mock import patch
from test_product import seed,claims,QUERY,MEMBER_1
from db import Database
from etl import load,now,transform_time_logs
from star import dimension,key_at,refresh
from events import process,TOPICS,replay_dlq,schemas
from maintenance import run,reconcile
from event_outbox import publish
from product_service import Service,tick
from product_store import packed


def tracker(kind,payload,aggregate=None,at='2026-10-25T11:00:00Z'):
    return {'eventId':str(uuid.uuid4()),'eventType':kind,'aggregateId':aggregate or str(uuid.uuid4()),
            'occurredAt':at,'correlationId':'local-test','actor':'local-test','payload':payload}


class StarEvents(unittest.TestCase):
    def setUp(self):
        self.db=Database('sqlite::memory:');self.db.initialize();self.data=seed(self.db)
        self.task=self.data['tracker']['work-items'][0]['id'];self.project=self.data['tracker']['work-items'][0]['projectId']
    def tearDown(self):self.db.close()
    def send(self,body,offset=0,topic=None,key=None,**kwargs):
        return process(self.db,topic or TOPICS['tracker'],0,offset,key or body.get('aggregateId'),packed(body).encode(),**kwargs)
    def test_typed_star_unknown_fk_and_observed_scd2(self):
        attrs=dict(employee_id='1',full_name='Before')
        with self.db.transaction():
            first=dimension(self.db,'employee','reference','test',attrs,{'id':'test'},'2026-10-20T00:00:00+00:00')
            second=dimension(self.db,'employee','reference','test',dict(attrs,full_name='After'),{'id':'test'},'2026-10-21T00:00:00+00:00')
        self.assertNotEqual(first,second)
        self.assertEqual(key_at(self.db,'employee','reference','test','2026-10-19'),-1)
        self.assertEqual(key_at(self.db,'employee','reference','test','2026-10-20'),first)
        self.assertEqual(key_at(self.db,'employee','reference','test','2026-10-21'),second)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM dwh.fact_time_log WHERE employee_key=-1').fetchone()[0],6)
        with self.assertRaises(Exception):
            with self.db.transaction():self.db.execute('UPDATE dwh.fact_time_log SET project_key=999')
        self.assertEqual(self.db.execute('SELECT SUM(planned_hours) FROM dwh.cube_work_items').fetchone()[0],10)
    def test_zero_time_logs_are_valid_no_double_count_and_collision_is_dlq(self):
        eid=str(uuid.uuid4());body=tracker('TimeLogged',dict(timeLogId=eid,userId=MEMBER_1,hours=0,loggedDate='2026-10-25'),self.task)
        self.assertTrue(self.send(body));self.assertTrue(self.send(body,1))
        self.assertEqual(self.db.execute('SELECT hours_cents FROM dwh.fact_time_log WHERE id=?',(eid,)).fetchone()[0],0)
        changed=dict(body,payload=dict(body['payload'],hours=3))
        self.assertFalse(self.send(changed,2));self.assertFalse(self.send(changed,2));self.assertTrue(self.send(changed,2))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM etl.event_dlq').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT hours_cents FROM dwh.fact_time_log WHERE id=?',(eid,)).fetchone()[0],0)
    def test_transaction_failure_has_no_partial_fact_ledger_or_checkpoint_then_replay(self):
        eid=str(uuid.uuid4());body=tracker('TimeLogged',dict(timeLogId=eid,userId=MEMBER_1,hours=1.13,loggedDate='2026-10-25'),self.task)
        def fail(*args):raise RuntimeError('private dependency failure')
        for i in range(3):self.assertEqual(self.send(body,projector=fail),i==2)
        self.assertIsNone(self.db.execute('SELECT 1 FROM dwh.fact_time_log WHERE id=?',(eid,)).fetchone())
        self.assertIsNone(self.db.execute('SELECT 1 FROM etl.processed_event WHERE event_id=?',(body['eventId'],)).fetchone())
        self.db.connection.commit()
        self.assertTrue(replay_dlq(self.db,TOPICS['tracker'],0,0))
        self.assertEqual(self.db.execute('SELECT hours_cents FROM dwh.fact_time_log WHERE id=?',(eid,)).fetchone()[0],113)
        self.assertEqual(self.db.execute('SELECT next_offset FROM etl.event_checkpoint').fetchone()[0],1)
    def test_delayed_events_and_rest_cannot_roll_back_newer_fields(self):
        for offset,(hours,at) in enumerate([(15,'2026-10-25T13:00:00Z'),(12,'2026-10-25T12:00:00Z')]):
            self.assertTrue(self.send(tracker('WorkItemFieldsChanged',{'changedFields':['plannedHours','actualHours'],'oldValues':{},'newValues':{'plannedHours':hours,'actualHours':999},'version':offset},self.task,at),offset))
        from ops import rest
        with self.db.transaction():r=rest(self.db,'tracker','work-items',dict(self.data['tracker']['work-items'][0],plannedHours=1),'2026-10-25T14:00:00Z')
        self.assertEqual(r['plannedHours'],15);self.assertEqual(r['actualHours'],999)
        self.assertEqual(float(self.db.execute('SELECT SUM(hours_cents)/100.0 FROM dwh.fact_time_log').fetchone()[0]),11.25)
    def test_invalid_schema_partition_and_tombstones_preserve_historical_hours(self):
        body=tracker('WorkItemHardDeleted',{'workItemId':self.task,'title':'Synthetic','type':'TASK'},self.task)
        self.assertFalse(self.send(body,key='foreign'))
        self.assertTrue(self.send(body))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM dwh.fact_time_log WHERE is_deleted=1').fetchone()[0],6)
        self.assertEqual(float(self.db.execute('SELECT SUM(hours_cents)/100.0 FROM dwh.report_time_log').fetchone()[0]),11.25)
    def test_outbox_rollback_broker_failure_retry_and_no_values_in_events(self):
        service=Service(self.db,claims())
        with self.db.transaction():key=service.create_export('R-01',QUERY,'csv')
        tick(self.db)
        row=self.db.execute('SELECT payload FROM etl.outbox').fetchone();body=json.loads(row[0])
        self.assertEqual(body['eventType'],'ReportExportReady');self.assertNotIn('rows',body['payload'])
        self.db.connection.commit()
        def fail(*args):raise RuntimeError('broker is unavailable')
        self.assertEqual(publish(self.db,fail)['failed'],1)
        sent=[];self.assertEqual(publish(self.db,lambda *a:sent.append(a))['published'],1)
        self.assertEqual(publish(self.db,lambda *a:sent.append(a))['published'],0);self.assertEqual(len(sent),1)

    def test_qa_results_terminal_run_and_reopened_history(self):
        runid=str(uuid.uuid4());case=str(uuid.uuid4());result=str(uuid.uuid4());defect=str(uuid.uuid4())
        def qa(name,p,offset,at='2026-10-25T15:00:00Z'):
            body={'eventId':str(uuid.uuid4()),'eventType':name,'schemaVersion':1,'producer':'qa-system','correlationId':'test','occurredAt':at,'payload':p}
            topic=TOPICS['qa-defect' if name=='DefectChanged' else 'qa-run']
            return self.send(body,offset,topic,p.get('defectId',p.get('runId')))
        self.assertTrue(qa('TestRunStarted',{'runId':runid,'runKey':'RUN-LOCAL','environment':'dev','trigger':'MANUAL','caseCount':1,'startedAt':'2026-10-25T15:00:00Z'},0))
        p={'runId':runid,'resultId':result,'testCaseId':case,'testCaseKey':'LOCAL','caseVersion':1,'status':'PASSED','automated':False}
        self.assertTrue(qa('TestResultRecorded',p,1))
        self.assertTrue(qa('TestRunCompleted',{'runId':runid,'runKey':'RUN-LOCAL','status':'COMPLETED','finishedAt':'2026-10-25T16:00:00Z',
            'counts':{'total':1,'passed':1,'failed':0,'blocked':0,'notRun':0,'skipped':0}},2,'2026-10-25T16:00:00Z'))
        self.assertTrue(qa('TestResultRecorded',dict(p,status='FAILED'),3,'2026-10-25T17:00:00Z'))
        self.assertEqual(json.loads(self.db.execute('SELECT payload FROM ops.test_result WHERE id=?',(result,)).fetchone()[0])['status'],'PASSED')
        p={'defectId':defect,'defectKey':'DEF-LOCAL','change':'CREATED','status':'OPEN','severity':'MAJOR','priority':'HIGH','reopenCount':0}
        self.assertTrue(qa('DefectChanged',p,0))
        self.assertTrue(qa('DefectChanged',dict(p,change='STATUS_CHANGED',status='CLOSED',previousStatus='OPEN'),1,'2026-10-25T16:00:00Z'))
        self.assertTrue(qa('DefectChanged',dict(p,change='STATUS_CHANGED',status='REOPENED',previousStatus='CLOSED',reopenCount=1),2,'2026-10-25T17:00:00Z'))
        self.assertEqual(self.db.execute('SELECT SUM(is_reopen) FROM dwh.fact_defect_transition WHERE defect_id=?',(defect,)).fetchone()[0],1)

    def test_planning_signal_requests_reload_without_inventing_facts(self):
        from pathlib import Path
        path=Path(__file__).resolve().parents[3]/'planning-system/docs/contracts/events/PlanActivated.example.json'
        body=json.loads(path.read_text());before=self.db.execute('SELECT COUNT(*) FROM dwh.fact_demand').fetchone()[0]
        self.assertTrue(self.send(body,topic=TOPICS['planning'],key=body['projectId']))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM dwh.fact_demand').fetchone()[0],before)
        self.assertEqual(self.db.execute("SELECT status FROM etl.reload_request WHERE source='planning'").fetchone()[0],'PENDING')
    def test_moscow_snapshot_idempotent_stale_gaps_and_source_reconciliation(self):
        self.assertEqual(run(self.db,datetime(2026,10,25,22,59,tzinfo=timezone.utc))['status'],'NOT_DUE')
        at=datetime(2026,10,25,23,1,tzinfo=timezone.utc)
        self.assertIn(run(self.db,at)['status'],{'STALE','OBSERVED'})
        self.assertEqual(run(self.db,at)['status'],'ALREADY_DONE')
        run(self.db,datetime(2026,10,28,0,0,tzinfo=timezone.utc))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM etl.snapshot_gap').fetchone()[0],1)
        with self.db.transaction():statuses=reconcile(self.db,'tracker',{'work-items':[]})
        self.assertIn('SOURCE_DRIFT',statuses)
        self.assertGreater(self.db.execute('SELECT COUNT(*) FROM etl.reload_request').fetchone()[0],0)


@unittest.skipUnless(os.getenv('REPORTS_TEST_DATABASE_URL'),'Native PostgreSQL runner required')
class PostgreSQLStarEvents(StarEvents):
    def setUp(self):
        import psycopg
        from psycopg import sql
        from urllib.parse import urlsplit,urlunsplit
        self.owner=os.environ['REPORTS_TEST_DATABASE_URL'];self.name='star_'+uuid.uuid4().hex
        with psycopg.connect(self.owner,autocommit=True) as c:c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.name)))
        u=urlsplit(self.owner);self.db=Database(urlunsplit(u._replace(path='/'+self.name)));self.db.initialize();self.data=seed(self.db)
        self.task=self.data['tracker']['work-items'][0]['id'];self.project=self.data['tracker']['work-items'][0]['projectId']
    def tearDown(self):
        self.db.close()
        import psycopg
        from psycopg import sql
        with psycopg.connect(self.owner,autocommit=True) as c:c.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(self.name)))
