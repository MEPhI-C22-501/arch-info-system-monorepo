"""Reports-owned migrations and bounded authorization directory; no source writes."""
import json
import time
import uuid
from datetime import datetime, timezone

TABLES = '''
CREATE TABLE IF NOT EXISTS app.user_scope (
 subject TEXT NOT NULL, role TEXT NOT NULL, project_id TEXT NOT NULL DEFAULT '',
 employee_id TEXT NOT NULL DEFAULT '', PRIMARY KEY(subject,role,project_id,employee_id));
CREATE TABLE IF NOT EXISTS app.entity_link (
 kind TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
 PRIMARY KEY(kind,source_id));
CREATE TABLE IF NOT EXISTS app.principal (
 subject TEXT PRIMARY KEY, roles TEXT NOT NULL, token_scope TEXT NOT NULL,
 valid_until BIGINT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS app.saved_view (
 id TEXT PRIMARY KEY, owner_sub TEXT NOT NULL, report_id TEXT NOT NULL,
 name TEXT NOT NULL, query TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app.export_job (
 id TEXT PRIMARY KEY, owner_sub TEXT NOT NULL, report_id TEXT NOT NULL,
 query TEXT NOT NULL, format TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL, fingerprint TEXT,
 row_count INTEGER, checksum TEXT, file_data BYTEA, error TEXT);
CREATE INDEX IF NOT EXISTS reports_export_queue ON app.export_job(status,created_at);
CREATE TABLE IF NOT EXISTS app.subscription (
 id TEXT PRIMARY KEY, owner_sub TEXT NOT NULL, payload TEXT NOT NULL,
 status TEXT NOT NULL, version INTEGER NOT NULL, next_run_at TEXT,
 created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS reports_subscription_due ON app.subscription(status,next_run_at);
CREATE TABLE IF NOT EXISTS app.delivery (
 subscription_id TEXT NOT NULL, run_at TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(subscription_id,run_at));
CREATE TABLE IF NOT EXISTS app.notification (
 id TEXT PRIMARY KEY, recipient_sub TEXT NOT NULL, kind TEXT NOT NULL,
 export_id TEXT, snapshot_id TEXT, created_at TEXT NOT NULL, read_at TEXT);
CREATE TABLE IF NOT EXISTS app.audit_log (
 id TEXT PRIMARY KEY, actor_sub TEXT NOT NULL, action TEXT NOT NULL,
 report_id TEXT, resource_id TEXT, query_hash TEXT, result TEXT NOT NULL,
 at TEXT NOT NULL, correlation_id TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS reports_audit_at ON app.audit_log(at);
'''


def migrate(db):
    for statement in TABLES.split(';'):
        if statement.strip(): db.execute(statement)
    if db.sqlite:
        for operation in ('UPDATE', 'DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS reports_audit_no_{operation.lower()} BEFORE {operation} ON app.audit_log BEGIN SELECT RAISE(ABORT,'append only audit'); END")
    else:
        db.execute("""CREATE OR REPLACE FUNCTION app.reject_audit_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append only audit'; END $$""")
        for event, mode in [('UPDATE OR DELETE', 'ROW'), ('TRUNCATE', 'STATEMENT')]:
            suffix = 'rows' if mode == 'ROW' else 'truncate'
            db.execute(f'DROP TRIGGER IF EXISTS reports_audit_{suffix} ON app.audit_log')
            db.execute(f'CREATE TRIGGER reports_audit_{suffix} BEFORE {event} ON app.audit_log FOR EACH {mode} EXECUTE FUNCTION app.reject_audit_mutation()')


def stamp(): return datetime.now(timezone.utc).isoformat()
def packed(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def remember(db, claims):
    # Only verified JWT claims enter here. Never re-enable a disabled principal.
    from report_engine import roles
    db.execute('''INSERT INTO app.principal(subject,roles,token_scope,valid_until) VALUES (?,?,?,?)
        ON CONFLICT(subject) DO UPDATE SET roles=excluded.roles,token_scope=excluded.token_scope,
        valid_until=excluded.valid_until''',
        (claims['sub'], packed(sorted(roles(claims))), claims.get('scope', ''), claims['exp']))


def local_principal(db, subject):
    row = db.execute('SELECT roles,token_scope,valid_until,enabled FROM app.principal WHERE subject=?', (subject,)).fetchone()
    if not row or not row[3] or row[2] <= time.time(): raise PermissionError('Current authorization unavailable')
    return {'sub': subject, 'resource_access': {'reports': {'roles': json.loads(row[0])}}, 'scope': row[1], 'exp': row[2]}


def audit(db, actor, action, report_id=None, query=None, result='SUCCESS', resource=None, correlation=None):
    import hashlib
    db.execute('INSERT INTO app.audit_log VALUES (?,?,?,?,?,?,?,?,?)',
               (str(uuid.uuid4()), actor, action, report_id, resource,
                hashlib.sha256(packed(query).encode()).hexdigest() if query is not None else None,
                result, stamp(), correlation or str(uuid.uuid4())))


def notify(db, recipient, kind, export_id=None, snapshot_id=None):
    db.execute('INSERT INTO app.notification VALUES (?,?,?,?,?,?,NULL)',
               (str(uuid.uuid4()), recipient, kind, export_id, snapshot_id, stamp()))
