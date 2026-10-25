"""02:00 Moscow observed snapshots, reconciliation, gaps and bounded retention."""
import json
import uuid
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from product_store import stamp,packed
from star import refresh


def migrate(db):
    db.execute('''CREATE TABLE IF NOT EXISTS etl.daily_run(day TEXT PRIMARY KEY,observed_at TEXT NOT NULL,status TEXT NOT NULL,watermarks TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS dwh.daily_snapshot(day TEXT NOT NULL,source TEXT NOT NULL,entity TEXT NOT NULL,
      entity_id TEXT NOT NULL,payload TEXT NOT NULL,data_as_of TEXT NOT NULL,observed_at TEXT NOT NULL,
      PRIMARY KEY(day,source,entity,entity_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.snapshot_gap(day TEXT PRIMARY KEY,status TEXT NOT NULL,detected_at TEXT NOT NULL)''')


def reconcile(db,source,entities=None,at=None):
    at=at or stamp();result=[]
    if entities is None:
        entities={entity:[{'id':eid} for (eid,) in db.execute('SELECT entity_id FROM dwh.source_record WHERE source=? AND entity=?',(source,entity))]
                  for (entity,) in db.execute('SELECT DISTINCT entity FROM dwh.source_record WHERE source=?',(source,))}
        # Without a fresh owner response this only checks local projection parity.
        mode='LOCAL'
    else:mode='SOURCE'
    from ops import TABLES
    for entity,rows in entities.items():
        expected={str(r['id']) for r in rows}
        table=TABLES.get((source,entity))
        actual={r[0] for r in db.execute(f'SELECT id FROM ops.{table} WHERE source=?',(source,))} if mode=='LOCAL' and table else {r[0] for r in db.execute('SELECT entity_id FROM dwh.source_record WHERE source=? AND entity=?',(source,entity))}
        missing=expected-actual;extra=actual-expected
        status=mode+('_DRIFT' if missing or extra else '_MATCH')
        db.execute('INSERT INTO etl.reconciliation VALUES (?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),source,entity,len(expected),len(actual),len(missing),len(extra),at,status))
        if missing or extra:
            from events import reload_request
            reload_request(db,source,'*',at,'RECONCILIATION_DRIFT')
        result.append(status)
    return result


def run(db,now=None):
    now=now or datetime.now(timezone.utc);local=now.astimezone(ZoneInfo('Europe/Moscow'))
    if local.hour<2:return {'status':'NOT_DUE'}
    today=local.date().isoformat();at=now.astimezone(timezone.utc).isoformat()
    with db.transaction():
        if not db.sqlite:db.execute("SELECT pg_advisory_xact_lock(hashtext('reports-star-refresh'))")
        if db.execute('SELECT 1 FROM etl.daily_run WHERE day=?',(today,)).fetchone():return {'status':'ALREADY_DONE'}
        previous=db.execute('SELECT MAX(day) FROM etl.daily_run').fetchone()[0]
        if previous:
            day=datetime.fromisoformat(previous).date()+timedelta(days=1)
            while day<local.date():
                db.execute("INSERT INTO etl.snapshot_gap VALUES (?,'MISSING_OBSERVATION',?) ON CONFLICT DO NOTHING",(day.isoformat(),at));day+=timedelta(days=1)
        for (gap,) in db.execute("SELECT day FROM etl.snapshot_gap WHERE status='MISSING_OBSERVATION'").fetchall():
            # Recover the available historical observation, never manufacture
            # the exact missing 02:00 state or use today's payload for the past.
            rows=db.execute('SELECT source,entity,entity_id,payload,data_as_of FROM dwh.source_snapshot WHERE snapshot_date=?',(gap,)).fetchall()
            if rows:
                for source,entity,eid,payload,watermark in rows:
                    db.execute('INSERT INTO dwh.daily_snapshot VALUES (?,?,?,?,?,?,?) ON CONFLICT DO NOTHING',(gap,source,entity,eid,payload,watermark,at))
                db.execute("UPDATE etl.snapshot_gap SET status='RECOVERED_PARTIAL_OBSERVATION' WHERE day=?",(gap,))
        states=list(db.execute('SELECT source,data_as_of,loaded_at FROM etl.source_state'))
        fresh=bool(states) and all(0<=(now-datetime.fromisoformat(t)).total_seconds()<=3600 for _,_,t in states)
        refresh(db,at,observed_at=at)
        db.execute('''INSERT INTO dwh.daily_snapshot SELECT ?,source,entity,entity_id,payload,data_as_of,? FROM dwh.source_record WHERE true
          ON CONFLICT DO NOTHING''',(today,at))
        for source,_,_ in states:reconcile(db,source,at=at)
        db.execute('INSERT INTO etl.daily_run VALUES (?,?,?,?)',(today,at,'OBSERVED' if fresh else 'STALE',packed(states)))
        # No unpublished deliveries or unresolved DLQ is discarded.
        cutoff=(now-timedelta(days=90)).isoformat()
        db.execute('DELETE FROM etl.event_failure WHERE updated_at<? AND EXISTS(SELECT 1 FROM etl.event_dlq d WHERE d.topic=etl.event_failure.topic AND d.partition_id=etl.event_failure.partition_id AND d.offset_id=etl.event_failure.offset_id AND d.replayed_at IS NOT NULL)',(cutoff,))
        db.execute('DELETE FROM etl.reconciliation WHERE created_at<?',(cutoff,))
        db.execute('DELETE FROM etl.outbox WHERE published_at IS NOT NULL AND published_at<?',(cutoff,))
    return {'status':'OBSERVED' if fresh else 'STALE'}
