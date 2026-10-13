"""Versioned persistence. JSON stores contract snapshots, relational keys scope them."""
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer,
                        JSON, UniqueConstraint, ForeignKey, select, update, CheckConstraint)
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB

URL = os.environ.get('DATABASE_URL', 'sqlite:///./planning-dev.db')
engine = create_engine(URL, poolclass=StaticPool if URL == 'sqlite://' else None,
                       connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {})
metadata = MetaData()
records = Table('records', metadata,
    Column('id', String(36), primary_key=True), Column('kind', String(40), primary_key=True),
    Column('portfolio_id', String(36), nullable=False, index=True),
    Column('project_id', String(36), index=True), Column('revision', Integer, nullable=False),
    Column('data', JSON().with_variant(JSONB, 'postgresql'), nullable=False), CheckConstraint('revision >= 1'))
requests = Table('request_results', metadata,
    Column('id', String(64), primary_key=True), Column('fingerprint', String(64), nullable=False),
    Column('status', Integer, nullable=False), Column('body', JSON, nullable=False),
    Column('portfolio_id', String(36), nullable=False), Column('project_id', String(36)))
audit = Table('audit', metadata, Column('id', String(36), primary_key=True),
    Column('subject', String(200), nullable=False), Column('project_id', String(36)),
    Column('action', String(100), nullable=False), Column('occurred_at', String(40), nullable=False),
    Column('details', JSON, nullable=False))
schema_versions = Table('schema_versions', metadata,
    Column('version', Integer, primary_key=True), Column('applied_at', String(40), nullable=False))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
def uid(): return str(uuid4())
def migrate():
    metadata.create_all(engine)
    with engine.begin() as c:
        if not c.execute(select(schema_versions).where(schema_versions.c.version == 1)).first():
            c.execute(schema_versions.insert().values(version=1, applied_at=now()))
        if engine.dialect.name=='postgresql' and not c.execute(select(schema_versions).where(schema_versions.c.version==2)).first():
            script=(Path(__file__).parents[1]/'migrations/002-baseline-guard.sql').read_text()
            c.connection.driver_connection.execute(script)
            c.execute(schema_versions.insert().values(version=2,applied_at=now()))

def find(c, kind, identifier):
    return c.execute(select(records).where(records.c.kind == kind, records.c.id == identifier)).mappings().first()

def all_rows(c, kind, portfolio=None, project=None):
    q = select(records).where(records.c.kind == kind)
    if portfolio: q = q.where(records.c.portfolio_id == portfolio)
    if project: q = q.where(records.c.project_id == project)
    return list(c.execute(q).mappings())

def put(c, kind, data, portfolio, project=None, expected=None):
    identifier = data['id']; old = find(c, kind, identifier)
    revision = old['revision'] + 1 if old else 1
    if old:
        stmt = update(records).where(records.c.id == identifier, records.c.kind == kind,
                                     records.c.revision == (expected or old['revision']))
        if c.execute(stmt.values(data=data, revision=revision)).rowcount != 1:
            raise Conflict('Конкурентное изменение; перечитайте объект')
    else:
        c.execute(records.insert().values(id=identifier, kind=kind, portfolio_id=portfolio,
                                         project_id=project, revision=revision, data=data))
    return data

class Conflict(Exception): pass
