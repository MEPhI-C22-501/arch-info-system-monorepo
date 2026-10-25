"""Current-state projections with field-level event clocks and REST reconciliation."""
import json
from product_store import packed

TABLES={('tracker','work-items'):'work_item',('tracker','iterations'):'iteration',('tracker','time-logs'):'time_log',
        ('qa','test-runs'):'test_run',('qa','defects'):'defect',('qa','test-results'):'test_result',('planning','forecast'):'project_projection'}


def migrate(db):
    for name in set(TABLES.values()):
        db.execute(f'''CREATE TABLE IF NOT EXISTS ops.{name}(source TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,
          source_revision BIGINT,changed_at TEXT NOT NULL,field_versions TEXT NOT NULL,is_deleted INTEGER NOT NULL DEFAULT 0,
          status TEXT,assignee_id TEXT,project_id TEXT,iteration_id TEXT,planned_hours NUMERIC,actual_hours NUMERIC,remaining_hours NUMERIC,
          PRIMARY KEY(source,id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.processed_event(event_id TEXT PRIMARY KEY,body_hash TEXT NOT NULL,
      source TEXT NOT NULL,event_type TEXT NOT NULL,aggregate_id TEXT NOT NULL,occurred_at TEXT NOT NULL,
      status TEXT NOT NULL,processed_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.event_checkpoint(topic TEXT NOT NULL,partition_id INTEGER NOT NULL,
      next_offset BIGINT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(topic,partition_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.event_route(source TEXT NOT NULL,aggregate_id TEXT NOT NULL,
      topic TEXT NOT NULL,partition_id INTEGER NOT NULL,PRIMARY KEY(source,aggregate_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.event_failure(topic TEXT NOT NULL,partition_id INTEGER NOT NULL,offset_id BIGINT NOT NULL,
      attempts INTEGER NOT NULL,body_hash TEXT NOT NULL,reason TEXT NOT NULL,payload TEXT,
      updated_at TEXT NOT NULL,PRIMARY KEY(topic,partition_id,offset_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.event_dlq(topic TEXT NOT NULL,partition_id INTEGER NOT NULL,offset_id BIGINT NOT NULL,
      event_id TEXT,body_hash TEXT NOT NULL,reason TEXT NOT NULL,payload TEXT,created_at TEXT NOT NULL,replayed_at TEXT,
      PRIMARY KEY(topic,partition_id,offset_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.reload_request(source TEXT NOT NULL,aggregate_id TEXT NOT NULL,
      requested_at TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL,PRIMARY KEY(source,aggregate_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.reconciliation(id TEXT PRIMARY KEY,source TEXT NOT NULL,entity TEXT NOT NULL,
      source_count INTEGER NOT NULL,stored_count INTEGER NOT NULL,missing_count INTEGER NOT NULL,extra_count INTEGER NOT NULL,
      created_at TEXT NOT NULL,status TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS etl.outbox(event_id TEXT PRIMARY KEY,topic TEXT NOT NULL,partition_key TEXT NOT NULL,
      payload TEXT NOT NULL,created_at TEXT NOT NULL,published_at TEXT,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT)''')


def write(db,source,entity,row,at,versions=None):
    name=TABLES.get((source,entity))
    if not name:return
    actual=row.get('data',row) if source=='planning' else row
    from star import numeric
    db.execute(f'''INSERT INTO ops.{name} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(source,id) DO UPDATE SET payload=excluded.payload,source_revision=excluded.source_revision,
      changed_at=excluded.changed_at,field_versions=excluded.field_versions,is_deleted=excluded.is_deleted,status=excluded.status,
      assignee_id=excluded.assignee_id,project_id=excluded.project_id,iteration_id=excluded.iteration_id,
      planned_hours=excluded.planned_hours,actual_hours=excluded.actual_hours,remaining_hours=excluded.remaining_hours''',
      (source,str(row['id']),packed(row),row.get('sourceRevision',row.get('version',row.get('revision'))),at,packed(versions or {}),int(bool(row.get('isDeleted') or row.get('is_deleted'))),
       actual.get('status'),actual.get('assigneeId') or actual.get('authorId'),actual.get('projectId') or actual.get('planningProjectId'),actual.get('iterationId') or actual.get('trackerIterationId'),numeric(actual.get('plannedHours')),numeric(actual.get('actualHours')),numeric(actual.get('remainingHours'))))


def rest(db,source,entity,row,at):
    name=TABLES.get((source,entity))
    if not name:return row
    existing=db.execute(f'SELECT payload,field_versions,changed_at FROM ops.{name} WHERE source=? AND id=?',(source,str(row['id']))).fetchone()
    versions={};merged=dict(row)
    if existing:
        previous=json.loads(existing[0]);versions=json.loads(existing[1])
        from star import timestamp
        observed=timestamp(row.get('updatedAt'))
        # A REST record without an update clock fills metadata but cannot
        # overwrite fields already known from later source events.
        for field,clock in list(versions.items()):
            if observed is None or observed<clock[0]:
                if field in previous:merged[field]=previous[field]
            else:versions.pop(field,None)
    write(db,source,entity,merged,at,versions)
    return merged


def event(db,source,entity,identity,changes,at,offset):
    name=TABLES[(source,entity)]
    existing=db.execute(f'SELECT payload,field_versions,changed_at FROM ops.{name} WHERE source=? AND id=?',(source,str(identity))).fetchone()
    payload=json.loads(existing[0]) if existing else {'id':str(identity)}
    versions=json.loads(existing[1]) if existing else {};accepted=False
    for field,value in changes.items():
        if field=='id':continue
        old=versions.get(field)
        if old and (at,offset)<(old[0],old[1]):continue
        # REST clocks also protect against a delayed broker event.
        from star import timestamp
        observed=timestamp(payload.get('updatedAt')) if not old else None
        if observed and at<observed:continue
        payload[field]=value;versions[field]=[at,offset];accepted=True
    if accepted:
        write(db,source,entity,payload,max(at,existing[2]) if existing else at,versions)
        db.execute('''INSERT INTO dwh.source_record VALUES (?,?,?,?,?) ON CONFLICT(source,entity,entity_id)
          DO UPDATE SET payload=excluded.payload,data_as_of=excluded.data_as_of''',(source,entity,str(identity),packed(payload),max(at,existing[2]) if existing else at))
    return payload,accepted
