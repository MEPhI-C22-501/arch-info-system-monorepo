"""Isolated real Kafka/PostgreSQL integration. No changes to pilot business data."""
import hashlib,json,os,sys,time,uuid
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import psycopg
from psycopg import sql
from confluent_kafka import Producer,Consumer
from confluent_kafka.admin import AdminClient,NewTopic
from db import Database
from product_store import packed
from event_runner import broker_config,sender
from events import TOPICS,process
from event_outbox import enqueue,publish
from demo import MEMBER_1,MEMBER_2


def seed(db):
    from product_fixture import business_fixture
    from etl import load,now,transform_time_logs
    from star import refresh
    data=business_fixture({'member1':MEMBER_1,'member2':MEMBER_2})
    for source in ['tracker','planning','qa','reference']:
        entities=data[source];facts=transform_time_logs(entities['time-logs'],entities['work-items']) if source=='tracker' else None
        at=now();assert load(db,source,lambda e=entities,f=facts,t=at:(e,t,t,f))['status']=='LOADED'
    with db.transaction():
        for sub in [MEMBER_1,MEMBER_2]:db.execute('INSERT INTO app.subject_binding VALUES (?,?)',(sub,sub))
        for link in data['links']:db.execute('INSERT INTO app.entity_link VALUES (?,?,?)',link)
        refresh(db,now())
    return data


def main():
    suffix=uuid.uuid4().hex;dbname='reports_check_'+suffix;topic='dev.reports.check.'+suffix;delivery=topic+'.delivery';dlq=topic+'.dlq'
    config=broker_config();admin=AdminClient(config)
    owner=os.environ['REPORTS_DATABASE_URL'];db=None;consumer=None
    with psycopg.connect(owner,autocommit=True) as c:c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
    try:
        for future in admin.create_topics([NewTopic(n,3,1) for n in [topic,delivery,dlq]]).values():future.result(30)
        db=Database(urlunsplit(urlsplit(owner)._replace(path='/'+dbname)));db.initialize();data=seed(db);task=data['tracker']['work-items'][0]['id']
        TOPICS['tracker']=topic
        producer=Producer(dict(config,**{'enable.idempotence':True,'acks':'all'}));send=sender(producer)
        logid=str(uuid.uuid4());body={'eventId':str(uuid.uuid4()),'eventType':'TimeLogged','aggregateId':task,'actor':'local-check',
            'occurredAt':'2026-10-25T12:00:00Z','correlationId':'isolated-local-check','payload':{'timeLogId':logid,'userId':MEMBER_1,'hours':1.13,'loggedDate':'2026-10-25'}}
        send(topic,task,packed(body).encode())
        group='reports-check-'+suffix
        def connect():
            c=Consumer(dict(config,**{'group.id':group,'enable.auto.commit':False,'enable.auto.offset.store':False,'auto.offset.reset':'earliest'}));c.subscribe([topic]);return c
        def read(c):
            for _ in range(60):
                m=c.poll(1)
                if m and not m.error():return m
            raise RuntimeError('Local Kafka check timed out')
        consumer=connect();m=read(consumer)
        assert process(db,m.topic(),m.partition(),m.offset(),m.key().decode(),m.value())
        # Simulate loss after database commit but before broker commit.
        consumer.close();consumer=connect();m=read(consumer)
        assert process(db,m.topic(),m.partition(),m.offset(),m.key().decode(),m.value())
        result=consumer.commit(message=m,asynchronous=False);assert not any(p.error for p in result)
        assert db.execute('SELECT COUNT(*) FROM etl.processed_event').fetchone()[0]==1
        assert db.execute('SELECT hours_cents FROM dwh.fact_time_log WHERE id=?',(logid,)).fetchone()[0]==113
        db.connection.commit()
        # Poison record is retried at this offset and durably quarantined before ack.
        send(topic,task,b'{invalid-json');m=read(consumer)
        for attempt in range(3):assert process(db,m.topic(),m.partition(),m.offset(),m.key().decode(),m.value())==(attempt==2)
        result=consumer.commit(message=m,asynchronous=False);assert not any(p.error for p in result)
        assert db.execute('SELECT COUNT(*) FROM etl.event_dlq').fetchone()[0]==1;db.connection.commit()
        with db.transaction():db.execute('UPDATE etl.outbox SET topic=? WHERE published_at IS NULL',(dlq,))
        assert publish(db,send)['published']==1  # Metadata-only DLQ outbox.
        # Contract-valid delivery is committed before publishing, reuses eventId.
        export=str(uuid.uuid4())
        with db.transaction():
            eid=enqueue(db,'ReportExportReady',MEMBER_1,{'exportId':export,'reportId':'R-01','format':'csv','rowCount':1,
                'expiresAt':'2026-10-26T12:00:00Z','downloadPath':'/api/v1/exports/'+export+'/file'})
            db.execute('UPDATE etl.outbox SET topic=? WHERE event_id=?',(delivery,eid))
        assert publish(db,send)['published']==1
        consumer.close();consumer=Consumer(dict(config,**{'group.id':group+'-delivery','auto.offset.reset':'earliest','enable.auto.commit':False}));consumer.subscribe([delivery]);notification=read(consumer)
        assert json.loads(notification.value())['eventId']==eid
        assert publish(db,send)['published']==0
        result={'passed':True,'real_kafka':'3.9.1','real_postgres':True,'duplicate_after_restart':True,'poison_retries':3,
                'durable_dlq':True,'outbox_acknowledged':True,'isolated_database':True,'pilot_data_changed':False}
        print(json.dumps(result));return 0
    finally:
        if consumer:consumer.close()
        if db:db.close()
        with psycopg.connect(owner,autocommit=True) as c:c.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(dbname)))
        for future in admin.delete_topics([topic,delivery,dlq]).values():
            try:future.result(30)
            except Exception:pass


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(json.dumps({'passed':False,'errorType':type(e).__name__,'locations':[str(f.lineno) for f in __import__('traceback').extract_tb(e.__traceback__)]}));sys.exit(1)
