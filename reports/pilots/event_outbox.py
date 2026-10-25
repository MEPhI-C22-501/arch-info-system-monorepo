"""Reports notification contracts, enqueued in the file's database transaction."""
import json
import uuid
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker
from product_store import packed,stamp


def enqueue(db,name,recipient,payload,correlation=None):
    body={'eventId':str(uuid.uuid4()),'eventType':name,'producer':'Reports','schemaVersion':'1.0.0',
          'occurredAt':stamp(),'correlationId':correlation or str(uuid.uuid4()),'recipientSub':recipient,'payload':payload}
    root=Path('/docs/contracts/events') if Path('/docs/contracts/events').is_dir() else Path(__file__).resolve().parents[1]/'docs/contracts/events'
    schema=json.loads((root/(name+'.schema.json')).read_text())
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(body)
    db.execute('INSERT INTO etl.outbox(event_id,topic,partition_key,payload,created_at) VALUES (?,?,?,?,?)',
               (body['eventId'],'dev.reports.delivery.v1',recipient,packed(body),stamp()))
    return body['eventId']


def publish(db,send):
    """send must wait for broker acknowledgement. A crash can repeat eventId."""
    result={'published':0,'failed':0}
    with db.transaction():
        if not db.sqlite and not db.execute("SELECT pg_try_advisory_xact_lock(hashtext('reports-outbox'))").fetchone()[0]:return result
        rows=db.execute('SELECT event_id,topic,partition_key,payload FROM etl.outbox WHERE published_at IS NULL ORDER BY created_at,event_id LIMIT 100').fetchall()
        for eid,topic,key,body in rows:
            try:
                send(topic,key,body.encode())
                db.execute('UPDATE etl.outbox SET published_at=?,attempts=attempts+1,last_error=NULL WHERE event_id=?',(stamp(),eid));result['published']+=1
            except Exception:
                db.execute("UPDATE etl.outbox SET attempts=attempts+1,last_error='BROKER_UNAVAILABLE' WHERE event_id=?",(eid,));result['failed']+=1
                break  # Preserve recipient ordering until the next retry.
    return result
