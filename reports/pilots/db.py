"""PostgreSQL storage; SQLite is an isolated contract-test backend only."""
import re
import sqlite3
from contextlib import contextmanager

DDL = """
CREATE TABLE IF NOT EXISTS etl.batch (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, status TEXT NOT NULL,
 started_at TEXT NOT NULL, completed_at TEXT, error_code TEXT);
CREATE TABLE IF NOT EXISTS stg.record (
 batch_id TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(batch_id, entity, entity_id));
CREATE TABLE IF NOT EXISTS etl.checkpoint (
 source TEXT PRIMARY KEY, value TEXT NOT NULL, loaded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS etl.source_state (
 source TEXT PRIMARY KEY, data_as_of TEXT NOT NULL, loaded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dwh.source_record (
 source TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT NOT NULL,
 payload TEXT NOT NULL, data_as_of TEXT NOT NULL,
 PRIMARY KEY(source, entity, entity_id));
CREATE TABLE IF NOT EXISTS dwh.dimension_version (
 version_id TEXT PRIMARY KEY, source TEXT NOT NULL, entity TEXT NOT NULL,
 entity_id TEXT NOT NULL, payload TEXT NOT NULL, valid_from TEXT NOT NULL,
 valid_to TEXT, CHECK(valid_to IS NULL OR valid_to >= valid_from));
CREATE UNIQUE INDEX IF NOT EXISTS reports_dimension_current
 ON dwh.dimension_version(source,entity,entity_id) WHERE valid_to IS NULL;
CREATE TABLE IF NOT EXISTS dwh.source_snapshot (
 snapshot_date TEXT NOT NULL, source TEXT NOT NULL, entity TEXT NOT NULL,
 entity_id TEXT NOT NULL, payload TEXT NOT NULL, data_as_of TEXT NOT NULL,
 PRIMARY KEY(snapshot_date,source,entity,entity_id));
CREATE TABLE IF NOT EXISTS etl.snapshot_batch (
 snapshot_date TEXT NOT NULL, source TEXT NOT NULL, batch_id TEXT NOT NULL,
 data_as_of TEXT NOT NULL, PRIMARY KEY(snapshot_date,source));
CREATE TABLE IF NOT EXISTS dwh.fact_time_log (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL, project_id TEXT NOT NULL,
 work_item_id TEXT, logged_date TEXT NOT NULL, hours_cents BIGINT NOT NULL
 CHECK(hours_cents >= 0));
CREATE TABLE IF NOT EXISTS app.subject_binding (
 subject TEXT PRIMARY KEY, tracker_user_id TEXT UNIQUE NOT NULL);
CREATE VIEW IF NOT EXISTS dwh.report_time_log AS
 SELECT f.id, b.subject AS user_id, f.project_id, f.work_item_id,
        f.logged_date, f.hours_cents
 FROM dwh.fact_time_log f LEFT JOIN app.subject_binding b
 ON b.tracker_user_id = f.user_id;
"""


class Database:
    def __init__(self, dsn):
        self.sqlite = dsn.startswith("sqlite:")
        if self.sqlite:
            self.connection = sqlite3.connect(dsn.removeprefix("sqlite:"))
            self.connection.execute('PRAGMA foreign_keys=ON')
        else:
            import psycopg
            self.connection = psycopg.connect(dsn)

    def execute(self, sql, params=()):
        if self.sqlite:
            sql = re.sub(r"\b(etl|stg|dwh|app|ops)\.", r"\1_", sql)
        else:
            sql = sql.replace("?", "%s")
            sql = sql.replace('CREATE VIEW IF NOT EXISTS', 'CREATE OR REPLACE VIEW')
        return self.connection.execute(sql, params) if params else self.connection.execute(sql)

    @contextmanager
    def transaction(self):
        try:
            yield self
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def initialize(self):
        with self.transaction():
            if not self.sqlite:
                for schema in ("etl", "stg", "dwh", "app", "ops"):
                    self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            for statement in DDL.split(";"):
                if statement.strip():
                    self.execute(statement)

            from product_store import migrate
            migrate(self)
            from star import migrate as migrate_star
            migrate_star(self)
            from ops import migrate as migrate_ops
            migrate_ops(self)
            from maintenance import migrate as migrate_maintenance
            migrate_maintenance(self)

    def close(self):
        self.connection.close()
