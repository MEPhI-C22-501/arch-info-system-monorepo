import uuid
from datetime import datetime

from pydantic import Field

from app.cases.schemas import Code
from app.models.enums import (
    ChangeSource,
    DefectOrigin,
    DefectStatus,
    ResultStatus,
    Severity,
    TrackerSyncState,
)
from app.schemas import ApiModel, NonEmptyStr


class DefectInput(ApiModel):
    title: NonEmptyStr
    description: str | None = None
    repro_steps: str | None = None
    expected_result: str | None = None
    actual_result: NonEmptyStr
    severity: Severity
    priority: Code | None = Field(None, description="По умолчанию — приоритет версии кейса")
    test_case_id: uuid.UUID | None = None
    run_result_id: uuid.UUID | None = None
    step_id: uuid.UUID | None = None
    environment: str | None = Field(None, description="Код окружения; без результата обязателен")
    requirement_ref: str | None = None
    epic_ref: str | None = None


class DefectUpdate(ApiModel):
    """Меняются только присланные поля; каждое изменение пишется в историю."""

    title: NonEmptyStr | None = None
    description: str | None = None
    repro_steps: str | None = None
    expected_result: str | None = None
    actual_result: NonEmptyStr | None = None
    severity: Severity | None = None
    priority: Code | None = None
    environment: str | None = None
    build_version: str | None = None
    requirement_ref: str | None = None
    epic_ref: str | None = None


class Defect(ApiModel):
    id: uuid.UUID
    key: str
    origin: DefectOrigin
    title: str
    description: str | None
    repro_steps: str | None
    expected_result: str | None
    actual_result: str
    severity: str
    priority: str
    status: DefectStatus
    environment: str | None
    build_version: str | None
    author: str
    test_case_id: uuid.UUID | None
    test_case_key: str | None
    case_version: int | None
    step_id: uuid.UUID | None
    plan_id: uuid.UUID | None
    requirement_ref: str | None
    epic_ref: str | None
    tracker_work_item_id: str | None
    tracker_work_item_url: str | None
    tracker_sync_state: TrackerSyncState
    tracker_status: str | None
    tracker_priority: str | None
    tracker_assignee: str | None
    tracker_mismatch: bool
    reopen_count: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    run_ids: list[uuid.UUID]


class DefectRun(ApiModel):
    run_id: uuid.UUID
    run_key: str
    result_id: uuid.UUID
    result_status: ResultStatus
    linked_at: datetime


class DefectComment(ApiModel):
    id: uuid.UUID
    author: str
    source: ChangeSource
    body: str
    created_at: datetime


class DefectDetail(Defect):
    runs: list[DefectRun]
    comments: list[DefectComment]


class DefectTransition(ApiModel):
    to: DefectStatus
    comment: NonEmptyStr | None = None


class DefectCommentInput(ApiModel):
    body: NonEmptyStr


class DefectHistoryEntry(ApiModel):
    author: str
    source: ChangeSource
    field: str
    old_value: str | None
    new_value: str | None
    occurred_at: datetime


class DefectHistoryList(ApiModel):
    items: list[DefectHistoryEntry]


class DefectLink(ApiModel):
    """Дефект в ответе записи результата; created=false — связан существующий (FR-DEF-03)."""

    id: uuid.UUID
    key: str
    created: bool
