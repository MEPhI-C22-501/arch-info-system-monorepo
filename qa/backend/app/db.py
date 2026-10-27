"""Подключение к БД. Транзакцию фиксирует сервис модуля явным session.commit()."""

from collections.abc import Iterator
from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3}
    )


@cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with _session_factory()() as session:
        yield session
