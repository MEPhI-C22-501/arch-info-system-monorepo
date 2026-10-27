"""Базовый класс моделей и общие столбцы.

Правила 120: ключи — uuid, время — timestamptz в UTC, перечисления — text с CHECK,
ссылки на объекты других подсистем — text без внешнего ключа.
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, MetaData, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column

NAMING_CONVENTION = {
    "pk": "%(table_name)s_pkey",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "ix": "%(table_name)s_%(column_0_N_name)s_idx",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        str: Text,
        uuid.UUID: Uuid,
        datetime: DateTime(timezone=True),
        date: Date,
        dict: JSONB,
        list: JSONB,
    }


def uuid_pk():
    return mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )


def created_at_column():
    return mapped_column(server_default=func.now())


def updated_at_column():
    return mapped_column(server_default=func.now(), onupdate=func.now())


def one_of(column: str, values: Iterable[str], *, nullable: bool = False) -> CheckConstraint:
    """CHECK на допустимые значения; имя ограничения — <таблица>_<столбец>_check."""
    allowed = ", ".join(f"'{value}'" for value in values)
    sql = f"{column} IN ({allowed})"
    if nullable:
        sql = f"{column} IS NULL OR {sql}"
    return CheckConstraint(sql, name=column)
