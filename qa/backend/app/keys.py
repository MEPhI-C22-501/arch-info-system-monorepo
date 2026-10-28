"""Читаемые ключи объектов: TC-RM-03, TP-12, RUN-87, DEF-45 (130, раздел 2)."""

from sqlalchemy import text
from sqlalchemy.orm import Session

_NEXT = text(
    "INSERT INTO key_counter (prefix, last_value) VALUES (:prefix, 1) "
    "ON CONFLICT (prefix) DO UPDATE SET last_value = key_counter.last_value + 1 "
    "RETURNING last_value"
)


def next_key(session: Session, prefix: str) -> str:
    """Выдаёт следующий ключ в транзакции сессии; откат транзакции возвращает номер.

    Демо-данные с явными ключами должны поднять key_counter до последнего номера.
    """
    value = session.execute(_NEXT, {"prefix": prefix}).scalar_one()
    return f"{prefix}-{value:02d}"
