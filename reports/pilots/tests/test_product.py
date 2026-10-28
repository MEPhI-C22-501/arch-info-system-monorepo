"""Independent report totals, role boundaries, export safety and durable delivery."""
import io
import json
import os
import sys
import time
import unittest
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db import Database
from demo import MEMBER_1, MEMBER_2
from product_fixture import business_fixture
from product_service import Service, tick
from product_store import audit, local_principal, remember
from report_engine import Engine, Scope, Problem, PM, TL, QA, MB, AN, AD
from etl import load, now, transform_time_logs
from delivery import encode, next_run

SUBJECTS={'member1':MEMBER_1,'member2':MEMBER_2}
ADMIN='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
QUERY={'params':{'periodFrom':'2026-10-01','periodTo':'2026-10-31'},'slice':['project']}


def claims(subject=ADMIN,roles=None):
    return {'sub':subject,'exp':int(time.time())+3600,'resource_access':{'reports':{'roles':roles if roles is not None else [AN,AD]}},'scope':''}


def seed(db):
    data=business_fixture(SUBJECTS)
    for source in ['tracker','planning','qa','reference']:
        entities=data[source];facts=transform_time_logs(entities['time-logs'],entities['work-items']) if source=='tracker' else None
        value=now();load(db,source,lambda e=entities,f=facts,s=value:(e,s,s,f))
    with db.transaction():
        for subject in SUBJECTS.values(): db.execute('INSERT INTO app.subject_binding VALUES (?,?)',(subject,subject))
        for link in data['links']: db.execute('INSERT INTO app.entity_link VALUES (?,?,?)',link)
        for c in [claims(),claims(MEMBER_1,[MB]),claims(MEMBER_2,[MB])]: remember(db,c)
        from star import refresh
        refresh(db,now())
    return data


class Product(unittest.TestCase):
    def setUp(self):
        self.db=Database('sqlite::memory:');self.db.initialize();self.data=seed(self.db)
        self.admin=claims();self.member=claims(MEMBER_1,[MB]);self.service=Service(self.db,self.admin)

    def tearDown(self): self.db.close()

    def query(self,rid,query=None,c=None): return Engine(self.db).query(rid,c or self.admin,query or QUERY)

    def test_all_eleven_reports_independent_metric_values(self):
        result={f'R-{n:02d}':self.query(f'R-{n:02d}') for n in range(1,12)}
        self.assertEqual(result['R-01']['totals']['M-01'],11.25)
        self.assertEqual(result['R-02']['totals']['M-11'],12)
        self.assertEqual(result['R-03']['totals'],{'M-01':11.25,'M-02':10,'M-03':-1.25,'M-06':100,'taskCount':1})
        self.assertEqual(result['R-04']['totals']['M-05'],0)
        self.assertEqual(result['R-05']['totals']['M-12'],{'opened':1,'closed':1,'remaining':1})
        self.assertEqual(result['R-05']['totals']['M-13'],2)
        self.assertEqual(result['R-06']['totals']['M-04'],1.25)
        self.assertEqual(result['R-06']['totals']['M-07'],1.5625)
        self.assertEqual(result['R-06']['totals']['crossCheckFinish'],'2026-10-31')
        self.assertIsNone(result['R-06']['totals']['M-08'])
        self.assertNotIn('budgetVarianceMoney',result['R-06']['totals'])
        self.assertEqual(result['R-07']['totals']['M-14'],100)
        self.assertEqual(result['R-07']['totals']['M-15'],100)
        self.assertEqual(result['R-08']['totals']['M-12']['remaining'],1)
        self.assertIsNone(result['R-09']['totals']['M-16'])
        self.assertEqual(result['R-09']['totals']['M-17'],100)
        self.assertEqual(result['R-10']['totals']['M-18']['cycleMedian'],3)
        self.assertEqual(result['R-10']['totals']['M-19']['throughput'],{'2026-W40':1})
        self.assertEqual(result['R-11']['totals']['M-20'],{'errorPercent':12.5,'correctionCoefficient':1.125,'eligibleTasks':1})
        for value in result.values(): json.dumps(value,allow_nan=False)

    def test_admin_is_not_a_business_role_and_member_cannot_query_resources(self):
        for c,rid in [(claims(ADMIN,[AD]),'R-01'),(self.member,'R-02'),(self.member,'R-06')]:
            with self.assertRaises(Problem) as denied: self.query(rid,c=c)
            self.assertEqual(denied.exception.status,403)
        self.assertEqual(self.query('R-01',c=self.member)['totals']['M-01'],3.75)
        other=claims(MEMBER_2,[MB]);self.assertEqual(self.query('R-03',c=other)['rows'],[])

    def test_project_scope_mapping_and_drilldown_never_expand_access(self):
        project=self.data['tracker']['work-items'][0]['projectId']
        c=claims(ADMIN,[PM])
        with self.assertRaises(Problem): self.query('R-01',c=c)
        with self.db.transaction(): self.db.execute('INSERT INTO app.user_scope VALUES (?,?,?,?)',(ADMIN,PM,project,''))
        self.assertEqual(self.query('R-01',c=c)['totals']['M-01'],11.25)
        bad={'params':dict(QUERY['params'],projectIds=['foreign']),'slice':['project']}
        with self.assertRaises(Problem): self.query('R-01',bad,c)
        detail=dict(QUERY,path=[{'slice':'project','id':project}],slice=['record'])
        self.assertEqual(len(self.query('R-01',detail,c)['rows']),6)
        tl=claims(ADMIN,[TL])
        with self.db.transaction(): self.db.execute('INSERT INTO app.user_scope VALUES (?,?,?,?)',(ADMIN,TL,project,''))
        with self.assertRaises(Problem): self.query('R-11',dict(QUERY,slice=['employee']),tl)

    def test_unknown_mapping_history_and_source_do_not_become_zero(self):
        with self.db.transaction(): self.db.execute("DELETE FROM app.entity_link WHERE kind='planning-project'")
        value=self.query('R-06');self.assertIn('MISSING_MAPPING:planning-project',value['notes'])
        with self.db.transaction(): self.db.execute("DELETE FROM etl.source_state WHERE source='qa'")
        with self.assertRaises(Problem) as unknown: self.query('R-05')
        self.assertEqual(unknown.exception.code,'SOURCE_NOT_LOADED')

    def test_schema_validation_period_comparison_and_empty_data(self):
        for query in [dict(QUERY,slice=['SQL; DROP TABLE']),{'params':{}},dict(QUERY,path='bad'),dict(QUERY,params={'periodFrom':'2026-10-31','periodTo':'2026-10-01'})]:
            with self.assertRaises(Problem): self.query('R-01',query)
        result=self.query('R-01',dict(QUERY,compareWithPrevious=True))
        self.assertIsNone(result['comparison']['delta'])
        self.assertEqual(self.query('R-01',{'params':{'periodFrom':'2020-01-01','periodTo':'2020-01-02'}})['rows'],[])

    def test_export_owner_ttl_scope_changes_and_formula_safety(self):
        with self.db.transaction(): key=self.service.create_export('R-01',QUERY,'xlsx')
        tick(self.db)
        raw,headers=self.service.download(key)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertIn('xl/worksheets/sheet1.xml',z.namelist())
            self.assertNotIn('<f>',z.read('xl/worksheets/sheet1.xml').decode())
        with self.assertRaises(Problem) as other: Service(self.db,self.member).download(key)
        self.assertEqual(other.exception.status,404)
        with self.db.transaction(): self.db.execute("UPDATE app.export_job SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?",(key,))
        with self.assertRaises(Problem) as expired: self.service.download(key)
        self.assertEqual(expired.exception.status,410)
        result=self.query('R-01');result['rows'][0]['project']['label']=' \t=HYPERLINK("x")'
        csv,_=encode(result,QUERY,ADMIN,'csv');self.assertIn(b"' \t=HYPERLINK",csv)
        with self.db.transaction():
            member_key=Service(self.db,self.member).create_export('R-01',QUERY,'csv')
        tick(self.db)
        with self.db.transaction(): self.db.execute('DELETE FROM app.subject_binding WHERE subject=?',(MEMBER_1,))
        with self.assertRaises(Problem): Service(self.db,self.member).download(member_key)

    def test_subscription_each_recipient_rechecked_and_owner_revocation_pauses(self):
        payload={'reportId':'R-01','query':QUERY,'schedule':'0 9 * * 1','format':'csv','recipients':[MEMBER_1,MEMBER_2]}
        with self.db.transaction():
            _,created,_=self.service.route('POST','subscriptions',payload)
            self.db.execute("UPDATE app.subscription SET next_run_at='2026-10-01T00:00:00+00:00' WHERE id=?",(created['subscriptionId'],))
            self.db.execute('UPDATE app.principal SET enabled=0 WHERE subject=?',(MEMBER_2,))
        tick(self.db)
        delivered=json.loads(self.db.execute('SELECT payload FROM app.delivery').fetchone()[0])
        self.assertEqual(delivered['delivered'],[MEMBER_1]);self.assertEqual(delivered['skipped'][0]['recipient'],MEMBER_2)
        files=self.db.execute('SELECT id FROM app.export_job WHERE owner_sub=?',(MEMBER_1,)).fetchall()
        self.assertEqual(len(files),1)
        raw,_=Service(self.db,self.member).download(files[0][0]);self.assertIn(b'3.75',raw);self.assertNotIn(b'11.25',raw)
        with self.db.transaction():
            self.db.execute('UPDATE app.principal SET enabled=0 WHERE subject=?',(ADMIN,))
            self.db.execute("UPDATE app.subscription SET next_run_at='2026-10-01T00:00:00+00:00'")
        tick(self.db)
        self.assertEqual(self.db.execute('SELECT status FROM app.subscription').fetchone()[0],'PAUSED')

    def test_subscription_version_ownership_and_cron_timezone(self):
        payload={'reportId':'R-01','query':QUERY,'schedule':'0 9 * * 1','format':'csv','recipients':[MEMBER_1]}
        with self.db.transaction(): _,created,_=self.service.route('POST','subscriptions',payload)
        key=created['subscriptionId']
        with self.assertRaises(Problem) as stale: self.service.route('PATCH','subscriptions/'+key,{'status':'PAUSED'},headers={'If-Match':'0'})
        self.assertEqual(stale.exception.status,409)
        with self.db.transaction(): status,updated,_=self.service.route('PATCH','subscriptions/'+key,{'status':'PAUSED'},headers={'If-Match':'1'})
        self.assertEqual(updated['version'],'2')
        with self.assertRaises(Problem): Service(self.db,self.member).subscription(key)
        self.assertEqual(next_run('0 9 * * 1',datetime(2026,10,4,tzinfo=timezone.utc)),'2026-10-05T06:00:00+00:00')

    def test_audit_is_append_only_and_views_are_owned(self):
        with self.db.transaction(): audit(self.db,ADMIN,'QUERY','R-01',QUERY)
        for sql in ["UPDATE app.audit_log SET result='changed'",'DELETE FROM app.audit_log']:
            with self.assertRaises(Exception),self.db.transaction(): self.db.execute(sql)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM app.audit_log').fetchone()[0],1)
        with self.db.transaction(): _,view,_=self.service.route('POST','views',{'reportId':'R-01','name':'<img src=x>','query':QUERY})
        with self.assertRaises(Problem): Service(self.db,self.member).route('GET','views/'+view['viewId'])

    def test_approved_config_and_owner_ceiling_do_not_widen_delivery(self):
        from configure_product import apply
        recipient='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
        project=self.data['tracker']['work-items'][0]['projectId']
        apply(self.db,{'scopes':[{'subject':ADMIN,'role':PM,'projectId':project}]})
        with self.db.transaction():
            remember(self.db,claims(ADMIN,[PM]));remember(self.db,claims(recipient,[AN]))
            self.db.execute('INSERT INTO dwh.fact_time_log(id,user_id,project_id,work_item_id,logged_date,hours_cents) VALUES (?,?,?,?,?,?)',('foreign-log',MEMBER_1,'foreign-project',None,'2026-10-01',100000))
        owner=Service(self.db,claims(ADMIN,[PM]))
        payload={'reportId':'R-01','query':QUERY,'schedule':'0 9 * * 1','format':'csv','recipients':[recipient]}
        with self.db.transaction():
            _,subscription,_=owner.route('POST','subscriptions',payload)
            self.db.execute("UPDATE app.subscription SET next_run_at='2026-10-01T00:00:00+00:00'")
        tick(self.db)
        job=self.db.execute('SELECT id FROM app.export_job WHERE owner_sub=?',(recipient,)).fetchone()[0]
        raw,_=Service(self.db,claims(recipient,[AN])).download(job)
        self.assertIn(b'11.25',raw);self.assertNotIn(b'foreign-project',raw)
        apply(self.db,{'disableSubjects':[recipient]})
        with self.assertRaises(Problem): Service(self.db,claims(recipient,[AN]))
        apply(self.db,{'enableSubjects':[recipient]})
        self.assertTrue(Service(self.db,claims(recipient,[AN])))

    def test_velocity_window_and_terminal_subscription(self):
        query=dict(QUERY,params=dict(QUERY['params'],velocityWeeks=1))
        self.assertEqual(self.query('R-06',query)['totals']['M-07'],0)
        for value in [0,53,True]:
            with self.assertRaises(Problem): self.query('R-06',dict(QUERY,params=dict(QUERY['params'],velocityWeeks=value)))
        payload={'reportId':'R-01','query':QUERY,'schedule':'0 9 * * 1','format':'csv','recipients':[MEMBER_1]}
        with self.db.transaction():
            _,subscription,_=self.service.route('POST','subscriptions',payload)
            self.service.route('DELETE','subscriptions/'+subscription['subscriptionId'])
        with self.assertRaises(Problem) as terminal:
            self.service.route('PATCH','subscriptions/'+subscription['subscriptionId'],{'status':'ACTIVE'},headers={'If-Match':'2'})
        self.assertEqual(terminal.exception.status,409)

    def test_money_from_owner_contract_requires_cost_permission(self):
        forecast=self.data['planning']['forecast'][0]
        forecast['data'].update(estimatedTotalCost=100,budgetAdjustment=-12.5,currencyCode='RUB')
        with self.db.transaction():
            self.db.execute("UPDATE dwh.source_record SET payload=? WHERE source='planning' AND entity='forecast'",(json.dumps(forecast),))
        from star import refresh
        with self.db.transaction(): refresh(self.db,now())
        hidden=self.query('R-06');self.assertNotIn('M-09',hidden['totals'])
        allowed=dict(self.admin,scope='cost.read')
        self.assertEqual(self.query('R-06',c=allowed)['totals']['M-09'],-12.5)
        self.assertEqual(self.query('R-06',c=allowed)['totals']['estimatedTotalCost'],100)

    def test_failed_encoder_does_not_poison_the_queue(self):
        with self.db.transaction(): key=self.service.create_export('R-01',QUERY,'csv')
        with patch('product_service.encode',side_effect=ValueError('not logged')): tick(self.db)
        self.assertEqual(self.service.export(key)['status'],'FAILED')
        with self.db.transaction(): key2=self.service.create_export('R-01',QUERY,'csv')
        tick(self.db);self.assertEqual(self.service.export(key2)['status'],'COMPLETED')


@unittest.skipUnless(os.getenv('REPORTS_TEST_DATABASE_URL'),'Native PostgreSQL runner required')
class PostgreSQLProduct(Product):
    def setUp(self):
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import conninfo_to_dict,make_conninfo
        self.admin_connection=psycopg.connect(os.environ['REPORTS_TEST_DATABASE_URL'],autocommit=True)
        self.name='reports_product_'+uuid.uuid4().hex[:12]
        self.admin_connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.name)))
        self.db=Database(make_conninfo(**dict(conninfo_to_dict(os.environ['REPORTS_TEST_DATABASE_URL']),dbname=self.name)))
        self.db.initialize();self.data=seed(self.db);self.admin=claims();self.member=claims(MEMBER_1,[MB]);self.service=Service(self.db,self.admin)

    def tearDown(self):
        from psycopg import sql
        self.db.close();self.admin_connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(self.name)))
        self.admin_connection.close()

    def test_postgres_audit_update_delete_truncate_are_rejected(self):
        with self.db.transaction(): audit(self.db,ADMIN,'TEST')
        for query in ['DELETE FROM app.audit_log','UPDATE app.audit_log SET result=\'bad\'','TRUNCATE app.audit_log']:
            with self.assertRaises(Exception),self.db.transaction(): self.db.execute(query)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM app.audit_log').fetchone()[0],1)


class ContractAndEncoders(unittest.TestCase):
    def test_report_results_match_openapi_and_no_html_sinks(self):
        import yaml
        from jsonschema import Draft202012Validator,FormatChecker
        root=Path(__file__).resolve().parents[3]
        contract=yaml.safe_load((root/'reports/api/openapi/v1/openapi.yaml').read_text())
        def convert(value):
            if isinstance(value,list): return [convert(v) for v in value]
            if not isinstance(value,dict): return value
            result={k:convert(v) for k,v in value.items()}
            if result.get('nullable') and 'type' in result: result['type']=[result['type'],'null']
            return result
        schema=convert({'$ref':'#/components/schemas/ReportResult','components':contract['components']})
        db=Database('sqlite::memory:');db.initialize()
        try:
            seed(db)
            for n in range(1,12): Draft202012Validator(schema,format_checker=FormatChecker()).validate(Engine(db).query(f'R-{n:02d}',claims(),QUERY))
        finally: db.close()
        script=(root/'reports/pilots/ui/app.js').read_text()
        for sink in ['.innerHTML','.outerHTML','document.write','localStorage.setItem']:
            self.assertNotIn(sink,script)
        self.assertNotIn("sessionStorage.setItem('token",script)

    def test_xlsx_xml_valid_and_dangerous_strings_stay_strings(self):
        from xml.etree import ElementTree
        db=Database('sqlite::memory:');db.initialize()
        try:
            seed(db);result=Engine(db).query('R-01',claims(),QUERY)
        finally: db.close()
        result['rows'][0]['project']['label']='=HYPERLINK("https://invalid")\ud800\ufffe'
        raw,_=encode(result,QUERY,ADMIN,'xlsx')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for name in z.namelist(): ElementTree.fromstring(z.read(name))
            sheet=z.read('xl/worksheets/sheet1.xml').decode()
            self.assertIn('=HYPERLINK',sheet);self.assertNotIn('<f>',sheet)
        for value in ['=cmd',' \t@SUM(1)','\ufeff+cmd','-cmd','\tdata']:
            result['rows'][0]['project']['label']=value
            raw,_=encode(result,QUERY,ADMIN,'csv')
            self.assertIn(("'"+value).encode(),raw)
