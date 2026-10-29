"""Классификаторы и окружения ведёт администратор QA System (ADR-009, 070 раздел 5а).

Значение не удаляется: его отключают, и только если оно нигде не используется.
"""

import uuid

from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session

from app.admin.schemas import (
    Classifier,
    ClassifierInput,
    ClassifierUpdate,
    Environment,
    EnvironmentInput,
    EnvironmentUpdate,
)
from app.errors import ApiError, conflict, not_found, validation_failed
from app.models import (
    ClassifierValue,
    Defect,
    RunSchedule,
    TestCase,
    TestCaseTemplate,
    TestCaseVersion,
    TestRun,
)
from app.models import Environment as EnvironmentRow
from app.models.enums import CaseStatus, ClassifierKind, DefectStatus, RunStatus
from app.schemas import Page, PageParams, paginate

# Сколько мест использования перечислять в ответе VALUE_IN_USE.
USAGE_SAMPLE = 5

_CASE_COLUMN = {
    ClassifierKind.SEVERITY: TestCaseVersion.severity,
    ClassifierKind.PRIORITY: TestCaseVersion.priority,
    ClassifierKind.CASE_TYPE: TestCaseVersion.type,
}
_TEMPLATE_FIELD = {
    ClassifierKind.SEVERITY: "severity",
    ClassifierKind.PRIORITY: "priority",
    ClassifierKind.CASE_TYPE: "type",
}


def check_codes(
    session: Session, values: dict[str, tuple[ClassifierKind, str]]
) -> list[dict[str, str]]:
    """Ошибки проверки для полей {поле: (вид, код)}: код неизвестен или отключён."""
    if not values:
        return []
    rows = session.execute(
        select(ClassifierValue.kind, ClassifierValue.code, ClassifierValue.is_active).where(
            tuple_(ClassifierValue.kind, ClassifierValue.code).in_(list(values.values()))
        )
    )
    active = {(kind, code): is_active for kind, code, is_active in rows}
    errors = []
    for field, key in values.items():
        if key not in active:
            errors.append({"field": field, "reason": "unknown"})
        elif not active[key]:
            errors.append({"field": field, "reason": "inactive"})
    return errors


def list_classifiers(
    session: Session, kind: ClassifierKind | None, is_active: bool | None, params: PageParams
) -> Page[Classifier]:
    stmt = select(ClassifierValue).order_by(
        ClassifierValue.kind, ClassifierValue.sort_order, ClassifierValue.code
    )
    if kind is not None:
        stmt = stmt.where(ClassifierValue.kind == kind)
    if is_active is not None:
        stmt = stmt.where(ClassifierValue.is_active == is_active)
    return paginate(session, stmt, params, Classifier)


def create_classifier(session: Session, data: ClassifierInput) -> Classifier:
    if data.kind == ClassifierKind.SEVERITY:
        # Коды серьёзности фиксированы: от них зависят Task Tracker (Q-02) и отчёты Reports.
        raise validation_failed([{"field": "kind", "reason": "fixed:SEVERITY"}])
    if session.get(ClassifierValue, (data.kind, data.code)) is not None:
        raise validation_failed([{"field": "code", "reason": "duplicate"}])
    row = ClassifierValue(**data.model_dump())
    session.add(row)
    session.commit()
    return Classifier.model_validate(row)


def update_classifier(
    session: Session, kind: ClassifierKind, code: str, data: ClassifierUpdate
) -> Classifier:
    row = session.get(ClassifierValue, (kind, code))
    if row is None:
        raise not_found("Значение классификатора")
    if data.is_active is False and row.is_active:
        usages = classifier_usages(session, kind, code)
        if usages:
            raise _in_use(f"Значение {kind} {code} используется", usages)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, field, value)
    session.commit()
    return Classifier.model_validate(row)


def classifier_usages(session: Session, kind: ClassifierKind, code: str) -> list[str]:
    """Где используется значение: текущие версии неархивных кейсов, активные шаблоны,
    для серьёзности — незакрытые дефекты."""
    cases = (
        select(TestCase.key)
        .join(TestCase.current)
        .where(TestCase.status != CaseStatus.ARCHIVED, _CASE_COLUMN[kind] == code)
        .order_by(TestCase.key)
    )
    usages = [f"case:{key}" for key in _sample(session, cases)]
    templates = (
        select(TestCaseTemplate.name)
        .where(
            TestCaseTemplate.is_active,
            TestCaseTemplate.body[_TEMPLATE_FIELD[kind]].astext == code,
        )
        .order_by(TestCaseTemplate.name)
    )
    usages += [f"template:{name}" for name in _sample(session, templates)]
    if kind == ClassifierKind.SEVERITY:
        defects = (
            select(Defect.key)
            .where(Defect.status != DefectStatus.CLOSED, Defect.severity == code)
            .order_by(Defect.key)
        )
        usages += [f"defect:{key}" for key in _sample(session, defects)]
    return usages[:USAGE_SAMPLE]


def list_environments(
    session: Session, is_active: bool | None, params: PageParams
) -> Page[Environment]:
    stmt = select(EnvironmentRow).order_by(EnvironmentRow.code)
    if is_active is not None:
        stmt = stmt.where(EnvironmentRow.is_active == is_active)
    return paginate(session, stmt, params, Environment)


def create_environment(session: Session, data: EnvironmentInput) -> Environment:
    if session.scalar(select(EnvironmentRow.id).where(EnvironmentRow.code == data.code)):
        raise validation_failed([{"field": "code", "reason": "duplicate"}])
    row = EnvironmentRow(**data.model_dump())
    session.add(row)
    session.commit()
    return Environment.model_validate(row)


def update_environment(
    session: Session, environment_id: uuid.UUID, data: EnvironmentUpdate
) -> Environment:
    row = session.get(EnvironmentRow, environment_id)
    if row is None:
        raise not_found("Окружение")
    if data.code is not None and data.code != row.code:
        raise validation_failed([{"field": "code", "reason": "immutable"}])
    if data.is_active is False and row.is_active:
        usages = environment_usages(session, row.id)
        if usages:
            raise _in_use(f"Окружение {row.code} используется", usages)
    for field in ("name", "base_urls", "is_active"):
        value = getattr(data, field)
        if value is not None:
            setattr(row, field, value)
    session.commit()
    return Environment.model_validate(row)


def environment_usages(session: Session, environment_id: uuid.UUID) -> list[str]:
    """Незавершённые прогоны и включённые расписания на окружении."""
    runs = (
        select(TestRun.key)
        .where(
            TestRun.environment_id == environment_id,
            TestRun.status.in_([RunStatus.CREATED, RunStatus.IN_PROGRESS]),
        )
        .order_by(TestRun.key)
    )
    usages = [f"run:{key}" for key in _sample(session, runs)]
    schedules = (
        select(RunSchedule.id)
        .where(RunSchedule.environment_id == environment_id, RunSchedule.is_active)
        .order_by(RunSchedule.id)
    )
    usages += [f"schedule:{schedule_id}" for schedule_id in _sample(session, schedules)]
    return usages[:USAGE_SAMPLE]


def _sample(session: Session, stmt: Select) -> list:
    return list(session.scalars(stmt.limit(USAGE_SAMPLE)))


def _in_use(message: str, usages: list[str]) -> ApiError:
    return conflict(
        "VALUE_IN_USE",
        f"{message}: отключить можно только неиспользуемое значение",
        [{"field": "isActive", "reason": f"used-by:{usage}"} for usage in usages],
    )
