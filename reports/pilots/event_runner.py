"""Private local Kafka runner. Manual commits only after durable PostgreSQL work."""
import argparse
import json
import logging
import os
import signal
import threading
import time
from pathlib import Path
from confluent_kafka import Consumer,Producer,KafkaException,TopicPartition
from confluent_kafka.admin import AdminClient,NewTopic
from db import Database
from events import TOPICS,process,replay_dlq
from event_outbox import publish
from maintenance import run
from product_store import stamp


def broker_config():
    # Shared SASL/TLS is intentionally not guessed; private local broker only.
    address=os.getenv('REPORTS_KAFKA_BOOTSTRAP','kafka:29092')
    return {'bootstrap.servers':address,'log_level':0}


def topics():
    admin=AdminClient(broker_config())
    names=[*TOPICS.values(),'dev.reports.delivery.v1','dev.reports.dlq.v1']
    for future in admin.create_topics([NewTopic(n,3,1,config={'retention.ms':'604800000'}) for n in names]).values():
        try:future.result(30)
        except KafkaException as error:
            from confluent_kafka import KafkaError
            if error.args[0].code()!=KafkaError.TOPIC_ALREADY_EXISTS:raise RuntimeError('BROKER_UNAVAILABLE') from None


def sender(producer):
    def send(topic,key,body):
        errors=[]
        producer.produce(topic,key=key.encode(),value=body,on_delivery=lambda error,_:errors.append(error))
        if producer.flush(10) or not errors or errors[0]:raise RuntimeError('BROKER_UNAVAILABLE')
    return send


def reload_local(db):
    # Synthetic development source only. Real endpoints use run_etl.py; a
    # Planning signal never substitutes for an authoritative source payload.
    if os.getenv('REPORTS_DEMO_PRODUCT')!='1':return
    pending=db.execute("SELECT source,aggregate_id,requested_at FROM etl.reload_request WHERE status='PENDING'").fetchall();db.connection.commit()
    if not pending:return
    from product_fixture import business_fixture
    from etl import load,tracker_extract
    subjects=json.loads(Path('/demo/subjects.json').read_text());data=business_fixture(subjects)
    for source in sorted({r[0] for r in pending}):
        if source=='tracker':
            from adapters import Client
            extract=lambda:tracker_extract(Client('http://mock-tracker:8080',allow_http=True))
        else:
            value=stamp();extract=lambda s=source,t=value:(data[s],t,t,None)
        result=load(db,source,extract)
        if result['status']=='LOADED':
            with db.transaction():
                for s,identity,requested in pending:
                    if s==source:db.execute("UPDATE etl.reload_request SET status='COMPLETED' WHERE source=? AND aggregate_id=? AND requested_at=?",(s,identity,requested))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--init',action='store_true');parser.add_argument('--health',action='store_true')
    parser.add_argument('--replay',nargs=3,metavar=('TOPIC','PARTITION','OFFSET'));args=parser.parse_args()
    if args.health:
        from worker import healthy
        return 0 if healthy('/tmp/reports-events.json',90) else 1
    if args.init:topics();print('Reports local Kafka topics initialized');return 0
    db=Database(os.environ['REPORTS_DATABASE_URL'])
    if args.replay:
        try:return 0 if replay_dlq(db,args.replay[0],int(args.replay[1]),int(args.replay[2])) else 1
        finally:db.close()
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    consumer=Consumer(dict(broker_config(),**{'group.id':'reports-local-ingest-v1','enable.auto.commit':False,
        'enable.auto.offset.store':False,'auto.offset.reset':'earliest','max.poll.interval.ms':300000}))
    producer=Producer(dict(broker_config(),**{'enable.idempotence':True,'acks':'all','delivery.timeout.ms':10000,'request.timeout.ms':5000}))
    def assign(client,partitions):
        for partition in partitions:
            row=db.execute('SELECT next_offset FROM etl.event_checkpoint WHERE topic=? AND partition_id=?',(partition.topic,partition.partition)).fetchone()
            if row:partition.offset=row[0]
        db.connection.commit();client.assign(partitions)
    consumer.subscribe(list(TOPICS.values()),on_assign=assign);last=0
    try:
        while not stop.is_set():
            message=consumer.poll(1)
            if message is not None:
                if message.error():raise RuntimeError('BROKER_CONSUMPTION_FAILED')
                try:key=(message.key() or b'').decode('utf-8')
                except UnicodeDecodeError:key=''
                while not stop.is_set():
                    if process(db,message.topic(),message.partition(),message.offset(),key,message.value() or b''):
                        result=consumer.commit(message=message,asynchronous=False)
                        if any(p.error for p in result):raise RuntimeError('BROKER_COMMIT_FAILED')
                        break
                    stop.wait(1)
            if time.monotonic()-last>=10:
                publish(db,sender(producer));reload_local(db);run(db);last=time.monotonic()
            target=Path('/tmp/reports-events.json');temporary=target.with_suffix('.tmp')
            temporary.write_text(json.dumps({'completed_at':stamp(),'status':'LOADED'}));temporary.replace(target)
    finally:consumer.close();db.close()
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        import traceback
        print(json.dumps({'worker':'reports-events','status':'DEPENDENCY_UNAVAILABLE','exceptionType':type(error).__name__,
            'sqlState':getattr(error,'sqlstate',None),'locations':[f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)]}),flush=True)
        raise SystemExit(1)
