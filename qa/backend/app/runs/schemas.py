import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.defects.schemas import DefectLink
from app.models.enums import ResultStatus, RunStatus, RunTrigger, Verdict
from app.schemas import ApiModel, NonEmptyStr


class RunInput(ApiModel):
    plan_id: uuid.UUID | None = None
    suite_id: uuid.UUID | None = None
    suite_name: NonEmptyStr | None = Field(None, description="Вместо suiteId, для CI")
    environment: NonEmptyStr = Field(description="Код окружения")
    start: bool = False
    automated_only: bool = Field(False, description="Только кейсы с реализованным автотестом")


class RunSummary(ApiModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    not_run: int = 0
    skipped: int = 0
    unverified: int = Field(0, description="Пропущены: проверка пока невозможна (vision 4.6)")


class Run(ApiModel):
    id: uuid.UUID
    key: str
    plan_id: uuid.UUID | None
    suite_id: uuid.UUID | None
    parent_run_id: uuid.UUID | None
    environment: str
    status: RunStatus
    trigger: RunTrigger
    started_by: str
    autotests_commit_sha: str | None
    sut_versions: dict[str, str] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    summary: RunSummary
    smoke_verdict: Literal["GREEN", "RED"] | None
    verdict: Verdict | None
    verdict_by: str | None
    verdict_at: datetime | None


class StepResultInput(ApiModel):
    step_id: uuid.UUID
    status: ResultStatus
    actual_result: str | None = None
    comment: str | None = None


class ResultInput(ApiModel):
    status: ResultStatus
    actual_result: str | None = None
    comment: str | None = None
    failure_reason: str | None = None
    duration_ms: int | None = Field(None, ge=0)
    steps: list[StepResultInput] | None = Field(
        None, description="Полный набор результатов шагов; повторная запись заменяет прежний"
    )


class RunResultStep(ApiModel):
    """Шаг зафиксированной версии и его результат; без записи — NOT_RUN."""

    step_id: uuid.UUID
    position: int
    action: str
    expected_result: str
    status: ResultStatus
    actual_result: str | None
    comment: str | None


class RunResult(ApiModel):
    id: uuid.UUID
    test_case_id: uuid.UUID
    test_case_key: str
    title: str
    case_version: int
    assignee: str | None
    status: ResultStatus
    failed_step_position: int | None
    actual_result: str | None
    comment: str | None
    failure_reason: str | None
    executed_by: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    steps: list[RunResultStep]
    defect: DefectLink | None
