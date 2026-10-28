"""Reproducible pilot ETL. Full REST scans, atomic merge and checkpoints."""
import argparse
import json
import math
import os
import signal
import sys
import threading
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from adapters import Client, HR_RESOURCES, QA_RESOURCES, Rejected, numbered, planning, reference
from db import Database
from contracts import validate_tracker

DIMENSIONS = {'reference': HR_RESOURCES, 'tracker': {'work-items', 'iterations', 'statuses'}}


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat()
    except (AttributeError, TypeError, ValueError):
        raise Rejected('INVALID_DATA_AS_OF') from None


def dimension_version(db, source, entity, eid, payload, data_as_of):
    current = db.execute('''SELECT version_id,payload FROM dwh.dimension_version
        WHERE source=? AND entity=? AND entity_id=? AND valid_to IS NULL''', (source, entity, eid)).fetchone()
    if current and current[1] == payload:
        return
    if current:
        db.execute('UPDATE dwh.dimension_version SET valid_to=? WHERE version_id=?', (data_as_of, current[0]))
    db.execute('INSERT INTO dwh.dimension_version VALUES (?,?,?,?,?,?,NULL)',
               (str(uuid.uuid4()), source, entity, eid, payload, data_as_of))


def now():
    return datetime.now(timezone.utc).isoformat()


def transform_time_logs(logs, work_items):
    projects = {r["id"]: r.get("projectId") for r in work_items}
    rows = []
    for record in logs:
        try:
            uuid.UUID(record["id"])
            if not isinstance(record["userId"], str) or not record["userId"]:
                raise ValueError()
            day = date.fromisoformat(record["loggedDate"]).isoformat()
            if isinstance(record["hours"], bool):
                raise ValueError()
            hours = Decimal(str(record["hours"]))
            if not hours.is_finite() or hours < 0 or hours * 100 != (hours * 100).to_integral_value():
                raise ValueError()
            work_id = record.get("workItemId")
            # Missing project stays explicit. A Tracker project ID is not
            # silently interpreted as a Planning System ID.
            project = projects.get(work_id) or "UNASSIGNED"
            rows.append((record["id"], record["userId"], project, work_id, day, int(hours * 100)))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            raise Rejected("INVALID_TIME_LOG") from None
    return rows


PLANNING_TABLES = {'plan': 'plan_version', 'demand': 'fact_demand', 'allocation': 'fact_allocation',
                   'availability': 'fact_availability', 'forecast': 'fact_forecast'}


def planning_scope(entities):
    portfolios = {r.get('portfolioId') for rows in entities.values() for r in rows}
    return portfolios.pop() if len(portfolios) == 1 else None


def prune_planning(db, scope, entities):
    """A Planning batch is a full snapshot of one portfolio: an entity of that
    portfolio missing from a READY batch is closed. Daily observations in
    dwh.source_snapshot keep its history; other portfolios are untouched."""
    present = {(entity, str(row['id'])) for entity, rows in entities.items() for row in rows}
    stale = [(entity, eid) for entity, eid, payload in
             db.execute("SELECT entity,entity_id,payload FROM dwh.source_record WHERE source='planning'").fetchall()
             if (entity, eid) not in present and json.loads(payload).get('portfolioId', scope) == scope]
    for entity, eid in stale:
        db.execute("DELETE FROM dwh.source_record WHERE source='planning' AND entity=? AND entity_id=?", (entity, eid))
        if entity == 'plan':
            db.execute('DELETE FROM dwh.fact_plan_item WHERE plan_version_id=?', (eid,))
        if entity == 'forecast':
            db.execute("DELETE FROM ops.project_projection WHERE source='planning' AND id=?", (eid,))
        if entity in PLANNING_TABLES:
            db.execute(f'DELETE FROM dwh.{PLANNING_TABLES[entity]} WHERE id=?', (eid,))
    return len(stale)


def load(db, source, extract, scope=None):
    batch_id, started = str(uuid.uuid4()), now()
    with db.transaction():
        db.execute("INSERT INTO etl.batch(id,source,status,started_at) VALUES (?,?,?,?)",
                   (batch_id, source, "EXTRACTING", started))
    try:
        with db.transaction():
            # The lock spans extraction and merge. A second PostgreSQL job
            # cannot overwrite the same source with an older concurrent scan.
            if db.sqlite:
                db.execute('BEGIN IMMEDIATE')
            elif not db.execute('SELECT pg_try_advisory_xact_lock(hashtext(?))',
                                ('reports-etl:'+source,)).fetchone()[0]:
                raise Rejected('SOURCE_LOAD_IN_PROGRESS')
            entities, checkpoint, data_as_of, facts = extract()
            if not db.sqlite:
                db.execute("SELECT pg_advisory_xact_lock(hashtext('reports-star-refresh'))")
            data_as_of = timestamp(data_as_of)
            if source == 'planning':
                scope = scope or planning_scope(entities)
            if source == 'planning' and scope:
                # Order is checked per portfolio: batches of different
                # portfolios are independent snapshots.
                previous = db.execute('SELECT value FROM etl.checkpoint WHERE source=?',
                                      ('planning:' + scope,)).fetchone()
                if previous and data_as_of < timestamp(json.loads(previous[0])['dataAsOf']):
                    raise Rejected('OUT_OF_ORDER_BATCH')
            else:
                previous = db.execute('SELECT data_as_of FROM etl.source_state WHERE source=?', (source,)).fetchone()
                if previous and data_as_of < timestamp(previous[0]):
                    raise Rejected('OUT_OF_ORDER_BATCH')
            snapshot_date = started[:10]  # First successful observed state per UTC day.
            take_snapshot = db.execute('SELECT 1 FROM etl.snapshot_batch WHERE snapshot_date=? AND source=?',
                                       (snapshot_date, source)).fetchone() is None
            if take_snapshot:
                db.execute('INSERT INTO etl.snapshot_batch VALUES (?,?,?,?)',
                           (snapshot_date, source, batch_id, data_as_of))
            for entity, rows in entities.items():
                for row in rows:
                    from ops import rest
                    row = rest(db,source,entity,row,data_as_of)
                    eid = str(row["id"])
                    payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
                    if entity in DIMENSIONS.get(source, set()):
                        dimension_version(db, source, entity, eid, payload, data_as_of)
                    if take_snapshot:
                        db.execute('INSERT INTO dwh.source_snapshot VALUES (?,?,?,?,?,?)',
                                   (snapshot_date, source, entity, eid, payload, data_as_of))
                    db.execute("INSERT INTO stg.record VALUES (?,?,?,?)", (batch_id, entity, eid, payload))
                    db.execute("""INSERT INTO dwh.source_record VALUES (?,?,?,?,?)
                        ON CONFLICT(source,entity,entity_id) DO UPDATE SET
                        payload=excluded.payload,data_as_of=excluded.data_as_of""",
                               (source, entity, eid, payload, data_as_of))
            if facts is not None:
                # Reconcile source rows with newer event fields before fact upsert.
                current_logs=[json.loads(r[0]) for r in db.execute("SELECT payload FROM dwh.source_record WHERE source='tracker' AND entity='time-logs'")]
                current_items=[json.loads(r[0]) for r in db.execute("SELECT payload FROM dwh.source_record WHERE source='tracker' AND entity='work-items'")]
                corrected={r[0]:r for r in transform_time_logs(current_logs,current_items)}
                for row in facts:
                    row=corrected.get(row[0],row)
                    db.execute("""INSERT INTO dwh.fact_time_log(id,user_id,project_id,work_item_id,logged_date,hours_cents) VALUES (?,?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET user_id=excluded.user_id,
                        project_id=excluded.project_id,work_item_id=excluded.work_item_id,
                        logged_date=excluded.logged_date,hours_cents=excluded.hours_cents""", row)
            if source == 'planning' and scope:
                prune_planning(db, scope, entities)
            from star import refresh
            refresh(db,data_as_of,batch_id)
            from maintenance import reconcile
            reconcile(db,source,entities,scope=scope if source == 'planning' else None)
            completed = now()
            # Planning freshness does not move back when an older batch of
            # another portfolio is replayed later in the same slot.
            db.execute('''INSERT INTO etl.source_state VALUES (?,?,?)
                ON CONFLICT(source) DO UPDATE SET data_as_of=CASE WHEN etl.source_state.source='planning'
                AND etl.source_state.data_as_of>excluded.data_as_of THEN etl.source_state.data_as_of
                ELSE excluded.data_as_of END,loaded_at=excluded.loaded_at''',
                       (source, data_as_of, completed))
            db.execute("""INSERT INTO etl.checkpoint VALUES (?,?,?)
                ON CONFLICT(source) DO UPDATE SET value=excluded.value,loaded_at=excluded.loaded_at""",
                       (source, checkpoint, completed))
            if source == 'planning' and scope:
                # Checkpoint (portfolioId, batchId, dataAsOf) only after the whole batch.
                db.execute("""INSERT INTO etl.checkpoint VALUES (?,?,?)
                    ON CONFLICT(source) DO UPDATE SET value=excluded.value,loaded_at=excluded.loaded_at""",
                           ('planning:' + scope, json.dumps({'batchId': checkpoint, 'dataAsOf': data_as_of}), completed))
            db.execute("UPDATE etl.batch SET status='LOADED',completed_at=? WHERE id=?", (completed, batch_id))
            # Payloads live in source_record; staging is not retained indefinitely.
            db.execute("DELETE FROM stg.record WHERE batch_id=?", (batch_id,))
        return {"batchId": batch_id, "status": "LOADED", "rows": sum(map(len, entities.values())), "dataAsOf": data_as_of}
    except Exception as error:
        code = str(error) if isinstance(error, Rejected) else "LOAD_FAILED"
        if code=='LOAD_FAILED':
            import traceback
            frames=traceback.extract_tb(error.__traceback__)
            print(json.dumps({'diagnostic':'LOAD_FAILED','exceptionType':type(error).__name__,
                'sqlState':getattr(error,'sqlstate',None),'locations':[f.name+':'+str(f.lineno) for f in frames]}),file=__import__('sys').stderr)
        with db.transaction():
            db.execute("UPDATE etl.batch SET status='REJECTED',completed_at=?,error_code=? WHERE id=?",
                       (now(), code, batch_id))
        if isinstance(error, Rejected):
            raise
        raise Rejected("LOAD_FAILED") from None


def tracker_extract(client):
    started = now()
    items = numbered(client, "work-items", validate=lambda r: validate_tracker("ReportWorkItem", r))
    logs = numbered(client, "time-logs", validate=lambda r: validate_tracker("TimeLog", r))
    iterations = numbered(client, 'iterations', validate=lambda r: validate_tracker('ReportIteration', r))
    history = numbered(client, 'history', validate=lambda r: validate_tracker('History', r))
    statuses = client.request('/api/v1/reports/statuses')
    if not isinstance(statuses, list) or any(not isinstance(row, dict) for row in statuses):
        raise Rejected('INVALID_STATUSES')
    from adapters import unique
    unique(statuses)
    for row in statuses:
        validate_tracker('Status', row)
    # Snapshot isolation is not guaranteed by the owner. Do not infer deletions
    # or claim an incremental change feed from these full scans.
    facts = transform_time_logs(logs, items)
    return {"work-items": items, "time-logs": logs, 'iterations': iterations,
            'history': history, 'statuses': statuses}, started, started, facts


def planning_extract(client, portfolio_id, slot=None):
    manifest, rows = planning(client, portfolio_id, slot)
    # Only top-level rows are used. Arrays nested in plan.data (demands,
    # allocations) repeat the same entities and are never counted again.
    entities = {kind: [] for kind in PLANNING_TABLES}
    for row in rows:
        entities[row["entityType"]].append({"id": row["entityId"], "data": row["data"],
                                            "batchId": manifest["batchId"], "portfolioId": portfolio_id})
    return entities, manifest["batchId"], manifest["dataAsOf"], None


def pending_planning_requests(db):
    return db.execute("SELECT aggregate_id,requested_at FROM etl.reload_request "
                      "WHERE source='planning' AND status='PENDING'").fetchall()


def complete_planning_requests(db, data_as_of, pending):
    """A signal is served only by a batch observed after it; otherwise it stays
    PENDING and the next hourly slot creates a newer batch."""
    projects = {json.loads(p).get('data', {}).get('projectId') for (p,) in
                db.execute("SELECT payload FROM dwh.source_record WHERE source='planning' AND entity='plan'")}
    with db.transaction():
        for aggregate, requested in pending:
            if (aggregate in projects or aggregate == '*') and timestamp(requested) <= data_as_of:
                db.execute("UPDATE etl.reload_request SET status='COMPLETED' WHERE source='planning' "
                           "AND aggregate_id=? AND requested_at=?", (aggregate, requested))


def catalog_extract(client, source):
    started = now()
    if source == "reference":
        entities = {resource: reference(client, resource) for resource in sorted(HR_RESOURCES)}
    else:
        entities = {resource: numbered(client, resource, tracker=False) for resource in sorted(QA_RESOURCES)}
    return entities, started, started, None


def run_once(args):
    # Credentials are never command-line parameters. The launcher loads these
    # variables from ~/secrets.env, never from a repository .env file.
    client = Client(args.url, os.getenv("REPORTS_SOURCE_TOKEN"), allow_http=args.allow_http)
    db = Database(os.environ["REPORTS_DATABASE_URL"])
    try:
        db.initialize()
        if args.source == "planning":
            pending = pending_planning_requests(db)
            if getattr(args, 'only_if_requested', False) and not pending:
                return {"status": "SKIPPED", "reason": "NO_PLANNING_SIGNAL"}
            extract = lambda: planning_extract(client, args.portfolio_id, getattr(args, 'export_slot', None))
            try:
                result = load(db, args.source, extract, scope=args.portfolio_id)
            except Rejected as error:
                if str(error) != 'OUT_OF_ORDER_BATCH':
                    raise
                # The slot replayed a batch older than one already loaded
                # (for example after a manual run): nothing newer to merge.
                return {"status": "SKIPPED", "reason": "SUPERSEDED_BATCH"}
            if pending:
                complete_planning_requests(db, result["dataAsOf"], pending)
            return result
        elif args.source == "tracker":
            extract = lambda: tracker_extract(client)
        else:
            extract = lambda: catalog_extract(client, args.source)
        return load(db, args.source, extract)
    except Rejected as error:
        return {"status": "REJECTED", "error": str(error)}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['tracker', 'planning', 'reference', 'qa'], default='tracker')
    parser.add_argument('--url', required=True)
    parser.add_argument('--portfolio-id')
    parser.add_argument('--only-if-requested', action='store_true',
                        help='Planning: run only when a Planning signal is pending (hourly CronJob)')
    parser.add_argument('--export-slot', help='Planning: Idempotency-Key slot, default is the current UTC hour')
    parser.add_argument('--allow-http', action='store_true', help='Only for an isolated local stand')
    parser.add_argument('--every', type=float, help='Repeat at this interval in seconds; skip missed ticks')
    parser.add_argument('--runs', type=int, default=0, help='Stop after N runs; 0 repeats until SIGTERM')
    args = parser.parse_args()
    if args.source == 'planning' and not args.portfolio_id:
        parser.error('--portfolio-id required for planning')
    if args.runs < 0 or (args.every is not None and (not math.isfinite(args.every) or args.every <= 0)):
        parser.error('Positive finite --every and nonnegative --runs required')
    if args.every is not None:
        from worker import repeat
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        return repeat(lambda: run_once(args), args.every, stop, max_runs=args.runs,
                      state_file='/tmp/reports-etl-'+args.source+'.json')
    try:
        result = run_once(args)
    except Exception:
        result = {'status': 'REJECTED', 'error': 'DEPENDENCY_UNAVAILABLE'}
    print(json.dumps(result))
    return 0 if result['status'] in ('LOADED', 'SKIPPED') else 1


if __name__ == "__main__":
    sys.exit(main())
