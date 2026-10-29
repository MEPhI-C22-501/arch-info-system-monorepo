"""Общие фикстуры.

Тесты с БД требуют PostgreSQL:
    docker compose -f qa/compose.yaml -f qa/compose.dev.yaml up -d --wait qa-db
База `<имя>_test` создаётся и очищается автоматически; адрес — TEST_DATABASE_URL.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://qa:qa-local@localhost:5435/qa_test"
)
os.environ.update(DATABASE_URL=TEST_DATABASE_URL, APP_ENV="test", AUTH_MODE="demo")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, make_url, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth import Role  # noqa: E402
from app.db import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import load_classifiers  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _ensure_database(url: str) -> None:
    target = make_url(url)
    if not target.database or not target.database.endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL должен указывать на БД с суффиксом _test")
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.database},
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    try:
        _ensure_database(TEST_DATABASE_URL)
    except OperationalError as exc:
        pytest.fail(
            f"Нет тестовой БД ({exc.orig}). Поднимите её: docker compose -f qa/compose.yaml "
            "-f qa/compose.dev.yaml up -d --wait qa-db",
            pytrace=False,
        )
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    # Откат проверяется на каждом запуске: миграции должны проходить в обе стороны.
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Сессия внутри транзакции, которая откатывается после теста; commit() в коде допустим."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth() -> Callable[..., dict[str, str]]:
    """auth(Role.LEAD) или auth(Role.TESTER, "ivanov") — заголовки демо-токена."""

    def headers(role: Role, user: str | None = None) -> dict[str, str]:
        token = f"demo-{role}" + (f"@{user}" if user else "")
        return {"Authorization": f"Bearer {token}"}

    return headers


@pytest.fixture
def classifiers(db_session: Session) -> None:
    """Серьёзность, приоритеты и типы кейсов из демо-данных."""
    load_classifiers(db_session)
