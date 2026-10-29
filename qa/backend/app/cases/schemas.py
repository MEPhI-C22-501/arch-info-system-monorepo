"""Схемы TestCase, TestCaseInput, Step и LastResult из OpenAPI."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from app.models import TestCase as TestCaseRow
from app.models import TestCaseVersion
from app.models.enums import CaseStatus, ResultStatus, Severity
from app.schemas import ApiModel, NonEmptyStr

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
# Модуль — префикс неизменяемого ключа TC-<модуль>-NN, поэтому и сам модуль не меняется.
Module = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]{1,9}$")]


class StepInput(ApiModel):
    action: NonEmptyStr
    expected_result: NonEmptyStr


class Step(ApiModel):
    id: uuid.UUID
    position: int
    action: str
    expected_result: str


class TestCaseInput(ApiModel):
    """При сохранении (PUT) поля, которых нет в запросе, берутся из текущей версии."""

    __test__ = False

    title: NonEmptyStr
    module: Module
    description: str | None = None
    preconditions: str | None = None
    priority: Code | None = None
    severity: Severity | None = None
    type: Code | None = None
    automated: bool = False
    autotest_key: str | None = None
    feature_ref: str | None = None
    epic_ref: str | None = None
    requirement_ref: str | None = None
    template_id: uuid.UUID | None = None
    steps: list[StepInput] | None = None
    version: int | None = Field(
        None, ge=1, description="Только PUT: версия, от которой сделана правка (VERSION_CONFLICT)"
    )


class LastResult(ApiModel):
    run_id: uuid.UUID
    run_key: str
    case_version: int
    status: ResultStatus
    actual_result: str | None
    failed_step_position: int | None
    environment: str
    finished_at: datetime


class TestCase(ApiModel):
    __test__ = False

    id: uuid.UUID
    key: str
    status: CaseStatus
    version: int
    current_version: int
    module: str
    title: str
    description: str | None
    preconditions: str | None
    priority: str
    severity: str
    type: str
    automated: bool
    autotest_key: str | None
    feature_ref: str | None
    epic_ref: str | None
    requirement_ref: str | None
    template_id: uuid.UUID | None
    copied_from_id: uuid.UUID | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    steps: list[Step]
    last_result: LastResult | None = Field(
        None, description="Только чтение: последний результат прогона (ADR-014)"
    )

    @model_validator(mode="before")
    @classmethod
    def _from_row(cls, data: Any) -> Any:
        # paginate() передаёт строку test_case; содержимое берётся из текущей версии.
        if isinstance(data, TestCaseRow):
            return case_fields(data, data.current)
        return data


def case_fields(case: TestCaseRow, version: TestCaseVersion) -> dict[str, Any]:
    return {
        **{column: getattr(case, column) for column in _CASE_COLUMNS},
        **{column: getattr(version, column) for column in _VERSION_COLUMNS},
        "current_version": case.current_version,
        "steps": version.steps,
    }


_CASE_COLUMNS = (
    "id",
    "key",
    "status",
    "module",
    "feature_ref",
    "epic_ref",
    "requirement_ref",
    "template_id",
    "copied_from_id",
    "created_by",
    "created_at",
    "updated_at",
)
_VERSION_COLUMNS = (
    "version",
    "title",
    "description",
    "preconditions",
    "priority",
    "severity",
    "type",
    "automated",
    "autotest_key",
)


class TestCaseVersionInfo(ApiModel):
    __test__ = False

    version: int
    author: str
    created_at: datetime
    changed_fields: list[str]


class TestCaseVersionList(ApiModel):
    __test__ = False

    items: list[TestCaseVersionInfo]


class CaseStatusInput(ApiModel):
    status: CaseStatus


class CopyInput(ApiModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class CaseFilter(ApiModel):
    """Отбор кейсов: параметры GET /test-cases и условие набора FILTER.

    Без status архивные кейсы не отбираются (индекс test_case_active_idx).
    """

    model_config = ConfigDict(extra="forbid")

    module: str | None = None
    status: CaseStatus | None = None
    type: str | None = None
    epic_ref: str | None = None
    automated: bool | None = None
    q: str | None = None
    suite_id: uuid.UUID | None = None

    def is_empty(self) -> bool:
        return not self.model_dump(exclude_none=True)
