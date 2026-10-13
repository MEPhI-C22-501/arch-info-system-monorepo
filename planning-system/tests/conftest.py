import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import delete, text

os.environ.update(APP_ENV='development',AUTH_MODE='demo',DATABASE_URL=os.environ.get('TEST_DATABASE_URL','sqlite://'),DEMO_SEED='false',STORAGE_MODE='local')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.app import app
from server import storage as db
from server.seed import seed
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCAL_FILES',str(tmp_path/'files'))
    with TestClient(app) as client:
        with db.engine.begin() as c:
            if db.engine.dialect.name=='postgresql':c.execute(text('TRUNCATE request_results, audit, records'))
            else:
                for t in [db.requests,db.audit,db.records]:c.execute(delete(t))
        seed()
        yield client
