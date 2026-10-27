from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import get_session
from app.main import create_app


def test_livez_does_not_need_database():
    client = TestClient(create_app())
    for path in ("/livez", "/api/v1/livez"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}


def test_readyz_with_database(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_without_database_returns_503():
    app = create_app()
    unreachable = create_engine(
        "postgresql+psycopg://qa:x@127.0.0.1:1/qa", connect_args={"connect_timeout": 1}
    )

    def broken_session():
        with Session(unreachable) as session:
            yield session

    app.dependency_overrides[get_session] = broken_session
    response = TestClient(app).get("/readyz")
    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"
