import uuid
from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.models.enums import ClassifierKind, DefectStatus
from app.schemas import ApiModel, NonEmptyStr

ClassifierCode = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,31}$")]
# Код окружения передаёт пайплайн (`"environment": "staging"`, 130, 4.3), поэтому он неизменяем.
EnvironmentCode = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,31}$")]
SubsystemName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
HttpUrl = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^https?://\S+$")]


class Classifier(ApiModel):
    kind: ClassifierKind
    code: str
    name: str
    sort_order: int
    is_active: bool


class ClassifierInput(ApiModel):
    kind: ClassifierKind
    code: ClassifierCode
    name: NonEmptyStr
    sort_order: int = 0
    is_active: bool = True


class ClassifierUpdate(ApiModel):
    name: NonEmptyStr | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class Environment(ApiModel):
    id: uuid.UUID
    code: str
    name: str
    base_urls: dict[str, str]
    is_active: bool


class EnvironmentInput(ApiModel):
    code: EnvironmentCode
    name: NonEmptyStr
    base_urls: dict[SubsystemName, HttpUrl] = {}
    is_active: bool = True


class EnvironmentUpdate(ApiModel):
    code: str | None = None
    name: NonEmptyStr | None = None
    base_urls: dict[SubsystemName, HttpUrl] | None = None
    is_active: bool | None = None


class TrackerStatusMappingItem(ApiModel):
    """qaStatus null — статус Task Tracker дефект не меняет."""

    tracker_status_id: NonEmptyStr
    tracker_status_name: NonEmptyStr
    qa_status: DefectStatus | None = None
    requires_assignee: bool = False
    is_active: bool = True


class TrackerStatusMappingInput(ApiModel):
    """Вся таблица: строки, которых нет в запросе, удаляются."""

    items: list[TrackerStatusMappingItem]


class TrackerStatusMappingRow(TrackerStatusMappingItem):
    updated_by: str
    updated_at: datetime


class TrackerStatusMapping(ApiModel):
    items: list[TrackerStatusMappingRow]
