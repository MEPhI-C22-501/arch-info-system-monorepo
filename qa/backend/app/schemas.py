"""Общие схемы API: camelCase в JSON и постраничные списки (130, раздел 2)."""

import math
from collections.abc import Callable
from typing import Annotated, Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

T = TypeVar("T", bound=BaseModel)


class Page(ApiModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total_pages: int


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
    ) -> None:
        self.page = page
        self.page_size = page_size


def paginate(session: Session, stmt: Select, params: PageParams, schema: type[T]) -> Page[T]:
    """stmt должен иметь устойчивый ORDER BY, иначе страницы будут пересекаться."""
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = session.scalars(
        stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)
    ).all()
    return Page[schema](
        items=[schema.model_validate(row) for row in rows],
        page=params.page,
        page_size=params.page_size,
        total_pages=math.ceil(total / params.page_size),
    )


def paginate_rows(
    session: Session,
    stmt: Select,
    params: PageParams,
    schema: type[T],
    build: Callable[[list[Any]], list[T]],
) -> Page[T]:
    """Как paginate(), но строки страницы превращаются в схемы разом: build делает один запрос
    на страницу вместо запросов на каждую строку."""
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = session.scalars(
        stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)
    ).all()
    return Page[schema](
        items=build(list(rows)),
        page=params.page,
        page_size=params.page_size,
        total_pages=math.ceil(total / params.page_size),
    )
