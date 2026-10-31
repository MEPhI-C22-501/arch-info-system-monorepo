"""Тест-кейсы.

Сохранение с изменённым содержимым вставляет новую неизменяемую версию (ADR-003). Номер
версии меняется сравнением с ожидаемым значением: из двух параллельных сохранений одно
получает VERSION_CONFLICT (120, раздел 8). Поля фактического результата у кейса нет:
lastResult читается из run_result по индексу run_result_last_idx (ADR-014).
"""

import uuid
from typing import Any

from pydantic.alias_generators import to_camel
from sqlalchemy import ColumnElement, and_, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.admin.service import check_codes
from app.auth import Principal, Role
from app.cases.schemas import (
    CaseFilter,
    LastResult,
    TestCase,
    TestCaseInput,
    TestCaseVersionInfo,
    case_fields,
)
from app.errors import ApiError, conflict, not_found, validation_failed
from app.keys import next_key
from app.models import (
    Defect,
    Environment,
    RunResult,
    TestCaseTemplate,
    TestCaseVersion,
    TestPlanCase,
    TestRun,
    TestStep,
    TestSuite,
    TestSuiteCase,
)
from app.models import TestCase as TestCaseRow
from app.models.enums import CaseStatus, ClassifierKind, ResultStatus, SuiteKind
from app.schemas import Page, PageParams, paginate

# Поля версии; их изменение создаёт новую версию.
CONTENT_FIELDS = (
    "title",
    "description",
    "preconditions",
    "priority",
    "severity",
    "type",
    "automated",
    "autotest_key",
)
# Поля самого кейса; меняются без новой версии.
REF_FIELDS = ("feature_ref", "epic_ref", "requirement_ref")
CLASSIFIER_FIELDS = {
    "priority": ClassifierKind.PRIORITY,
    "severity": ClassifierKind.SEVERITY,
    "type": ClassifierKind.CASE_TYPE,
}
TEMPLATE_FIELDS = ("description", "preconditions", "priority", "severity", "type")
# Подсистемы стартового набора (vision 7). Проверяются только при создании: модуль входит в
# неизменяемый ключ, а уже созданный кейс с другим модулем должен оставаться доступным.
MODULES = ("RM", "TT", "PS", "REP", "INF")

# 050, раздел 2. Удаление черновика — отдельная операция DELETE.
TRANSITIONS = {
    CaseStatus.DRAFT: {CaseStatus.ACTUAL},
    CaseStatus.ACTUAL: {CaseStatus.NEEDS_UPDATE, CaseStatus.ARCHIVED},
    CaseStatus.NEEDS_UPDATE: {CaseStatus.ACTUAL, CaseStatus.ARCHIVED},
    CaseStatus.ARCHIVED: {CaseStatus.ACTUAL},
}

# Ключ автотеста меняют автоматизатор и QA-лид (070, раздел 2).
AUTOMATION_ROLES = (Role.AUTOMATION, Role.LEAD)

CURRENT_VERSION = and_(
    TestCaseVersion.test_case_id == TestCaseRow.id,
    TestCaseVersion.version == TestCaseRow.current_version,
)

Steps = list[tuple[str, str]]


def get_case(session: Session, case_id: uuid.UUID) -> TestCaseRow:
    case = session.get(TestCaseRow, case_id)
    if case is None:
        raise not_found("Тест-кейс")
    return case


def get_version(session: Session, case: TestCaseRow, number: int) -> TestCaseVersion:
    version = session.scalar(
        select(TestCaseVersion)
        .where(TestCaseVersion.test_case_id == case.id, TestCaseVersion.version == number)
        .options(selectinload(TestCaseVersion.steps))
    )
    if version is None:
        raise not_found(f"Версия {number} кейса {case.key}")
    return version


def read_case(session: Session, case_id: uuid.UUID, version: int | None = None) -> TestCase:
    case = get_case(session, case_id)
    return _out(session, case, get_version(session, case, version or case.current_version))


def list_cases(
    session: Session, case_filter: CaseFilter, params: PageParams, include_archived: bool = False
) -> Page[TestCase]:
    stmt = (
        select(TestCaseRow)
        .join(TestCaseVersion, CURRENT_VERSION)
        .where(*filter_clauses(session, case_filter, include_archived=include_archived))
        .options(contains_eager(TestCaseRow.current).selectinload(TestCaseVersion.steps))
        .order_by(TestCaseRow.key, TestCaseRow.id)
        .execution_options(populate_existing=True)
    )
    page = paginate(session, stmt, params, TestCase)
    results = last_results(session, [item.id for item in page.items])
    for item in page.items:
        item.last_result = results.get(item.id)
    return page


def count_cases(session: Session, case_filter: CaseFilter) -> int:
    return session.scalar(
        select(func.count())
        .select_from(TestCaseRow)
        .join(TestCaseVersion, CURRENT_VERSION)
        .where(*filter_clauses(session, case_filter))
    )


def filter_clauses(
    session: Session, case_filter: CaseFilter, depth: int = 0, include_archived: bool = False
) -> list[ColumnElement[bool]]:
    """Условия на test_case и его текущую версию; запрос должен соединять их CURRENT_VERSION.

    include_archived — только для списка кейсов: в наборы и планы архив не попадает.
    """
    f = case_filter
    clauses: list[ColumnElement[bool]] = []
    if f.status:
        clauses.append(TestCaseRow.status == f.status)
    elif not include_archived:
        clauses.append(TestCaseRow.status != CaseStatus.ARCHIVED)
    if f.module:
        clauses.append(TestCaseRow.module == f.module)
    if f.type:
        clauses.append(TestCaseVersion.type == f.type)
    if f.epic_ref:
        clauses.append(TestCaseRow.epic_ref == f.epic_ref)
    if f.automated is not None:
        clauses.append(TestCaseVersion.automated == f.automated)
    if f.q:
        pattern = "%" + f.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        clauses.append(
            or_(
                TestCaseRow.key.ilike(pattern, escape="\\"),
                TestCaseVersion.title.ilike(pattern, escape="\\"),
            )
        )
    if f.suite_id:
        clauses.append(_in_suite(session, f.suite_id, depth))
    return clauses


def _in_suite(session: Session, suite_id: uuid.UUID, depth: int) -> ColumnElement[bool]:
    suite = session.get(TestSuite, suite_id)
    # Набор FILTER может ссылаться только на ручной набор, так что вложенность не больше 2.
    if suite is None:
        raise validation_failed([{"field": "suiteId", "reason": "not_found"}])
    if depth > 1:
        raise validation_failed([{"field": "suiteId", "reason": "nested"}])
    if suite.kind == SuiteKind.MANUAL:
        members = select(TestSuiteCase.test_case_id).where(TestSuiteCase.suite_id == suite.id)
        return TestCaseRow.id.in_(members)
    nested = (
        select(TestCaseRow.id)
        .join(TestCaseVersion, CURRENT_VERSION)
        .where(*filter_clauses(session, CaseFilter.model_validate(suite.filter), depth + 1))
    )
    return TestCaseRow.id.in_(nested)


def last_results(session: Session, case_ids: list[uuid.UUID]) -> dict[uuid.UUID, LastResult]:
    """Последний результат каждого кейса со статусом, отличным от NOT_RUN (FR-TC-10)."""
    if not case_ids:
        return {}
    rows = session.execute(
        select(
            RunResult.test_case_id,
            RunResult.run_id,
            TestRun.key.label("run_key"),
            TestCaseVersion.version.label("case_version"),
            RunResult.status,
            RunResult.actual_result,
            RunResult.failed_step_position,
            Environment.code.label("environment"),
            RunResult.finished_at,
        )
        .join(TestRun, TestRun.id == RunResult.run_id)
        .join(Environment, Environment.id == TestRun.environment_id)
        .join(TestCaseVersion, TestCaseVersion.id == RunResult.case_version_id)
        .where(
            RunResult.test_case_id.in_(case_ids),
            RunResult.status != ResultStatus.NOT_RUN,
            RunResult.finished_at.is_not(None),
        )
        .order_by(RunResult.test_case_id, RunResult.finished_at.desc())
        .distinct(RunResult.test_case_id)
    )
    return {row.test_case_id: LastResult.model_validate(row._asdict()) for row in rows}


def list_versions(session: Session, case_id: uuid.UUID) -> list[TestCaseVersionInfo]:
    case = get_case(session, case_id)
    versions = session.scalars(
        select(TestCaseVersion)
        .where(TestCaseVersion.test_case_id == case.id)
        .order_by(TestCaseVersion.version.desc())
    )
    return [TestCaseVersionInfo.model_validate(version) for version in versions]


def create_case(session: Session, data: TestCaseInput, principal: Principal) -> TestCase:
    content = content_of(data)
    if content["automated"] or content["autotest_key"]:
        _require_automation_role(principal)
    steps = steps_of(data) if data.steps is not None else None
    if data.template_id is not None:
        steps = _apply_template(session, data.template_id, content, steps)
    steps = steps or []
    errors = _content_errors(content)
    if data.module not in MODULES:
        errors.append({"field": "module", "reason": "unknown"})
    errors += check_codes(
        session,
        {
            field: (kind, content[field])
            for field, kind in CLASSIFIER_FIELDS.items()
            if content[field]
        },
    )
    if errors:
        raise validation_failed(errors, "Тест-кейс не прошёл проверку")
    case = TestCaseRow(
        key=next_key(session, f"TC-{data.module}"),
        status=CaseStatus.DRAFT,
        current_version=1,
        module=data.module,
        template_id=data.template_id,
        created_by=principal.subject,
        **{field: _blank_to_none(getattr(data, field)) for field in REF_FIELDS},
    )
    session.add(case)
    session.flush()
    version = insert_version(session, case, 1, content, steps, [], principal.subject)
    session.commit()
    return _out(session, case, version, with_last_result=False)


def update_case(
    session: Session, case_id: uuid.UUID, data: TestCaseInput, principal: Principal
) -> TestCase:
    case = get_case(session, case_id)
    if case.status == CaseStatus.ARCHIVED:
        raise conflict(
            "CASE_ARCHIVED", f"Кейс {case.key} в архиве: верните его в работу, чтобы изменить"
        )
    base = case.current_version
    if data.version is not None and data.version != base:
        raise _version_conflict(case)
    if data.module != case.module:
        raise validation_failed([{"field": "module", "reason": "immutable"}])

    current = get_version(session, case, base)
    sent = data.model_fields_set
    new_content = content_of(data)
    content = {
        field: new_content[field] if field in sent else getattr(current, field)
        for field in CONTENT_FIELDS
    }
    old_steps = [(step.action, step.expected_result) for step in current.steps]
    steps = steps_of(data) if data.steps is not None else old_steps
    changed = [to_camel(f) for f in CONTENT_FIELDS if content[f] != getattr(current, f)]
    if steps != old_steps:
        changed.append("steps")
    if {"automated", "autotestKey"} & set(changed):
        _require_automation_role(principal)

    errors = _content_errors(content)
    errors += check_codes(
        session,
        {
            field: (kind, content[field])
            for field, kind in CLASSIFIER_FIELDS.items()
            if content[field] and field in changed
        },
    )
    if case.status == CaseStatus.ACTUAL and not steps:
        # Актуальный кейс остаётся готовым к прогону (FR-TC-02).
        errors.append({"field": "steps", "reason": "required"})
    if errors:
        raise validation_failed(errors, "Тест-кейс не прошёл проверку")

    refs = {f: _blank_to_none(getattr(data, f)) for f in REF_FIELDS if f in sent}
    refs = {f: value for f, value in refs.items() if value != getattr(case, f)}
    if not changed and not refs:
        return _out(session, case, current)

    values: dict[str, Any] = {**refs, "updated_at": func.now()}
    if changed:
        values["current_version"] = base + 1
    saved = session.execute(
        update(TestCaseRow)
        .where(TestCaseRow.id == case.id, TestCaseRow.current_version == base)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if saved.rowcount != 1:
        session.rollback()
        raise _version_conflict(case)
    version = current
    if changed:
        try:
            version = insert_version(
                session, case, base + 1, content, steps, changed, principal.subject
            )
        except IntegrityError:
            session.rollback()
            raise _version_conflict(case)
    session.commit()
    session.refresh(case)
    return _out(session, case, version)


def change_status(
    session: Session, case_id: uuid.UUID, target: CaseStatus, principal: Principal
) -> TestCase:
    case = get_case(session, case_id)
    allowed = TRANSITIONS[CaseStatus(case.status)]
    if target not in allowed:
        raise conflict(
            "INVALID_TRANSITION",
            f"Переход {case.status} → {target} недопустим",
            [{"field": "status", "reason": "allowed:" + ",".join(sorted(allowed))}],
        )
    current = get_version(session, case, case.current_version)
    if target == CaseStatus.ACTUAL and not _is_ready(current):
        raise conflict(
            "CASE_NOT_READY",
            f"Кейс {case.key} не готов: нужны название и хотя бы один шаг с ожидаемым результатом",
            [{"field": "steps", "reason": "required"}],
        )
    case.status = target
    session.commit()
    return _out(session, case, current)


def delete_case(session: Session, case_id: uuid.UUID, principal: Principal) -> None:
    """Физически удаляется только черновик без прогонов — с версиями и шагами (120, раздел 8)."""
    case = get_case(session, case_id)
    if not principal.has_any(Role.LEAD) and case.created_by != principal.subject:
        raise ApiError(403, "PERMISSION_DENIED", "Удалить можно только свой черновик")
    if case.status != CaseStatus.DRAFT:
        raise conflict(
            "INVALID_TRANSITION",
            f"Удалить можно только черновик; кейс {case.key} в статусе {case.status}",
            [{"field": "status", "reason": "allowed:ARCHIVED"}],
        )
    has_runs = exists().where(RunResult.test_case_id == case.id)
    has_defects = exists().where(Defect.test_case_id == case.id)
    if session.scalar(select(has_runs | has_defects)):
        raise conflict(
            "CASE_HAS_RUNS", f"Кейс {case.key} участвовал в прогонах или связан с дефектами"
        )
    session.execute(
        update(TestCaseRow)
        .where(TestCaseRow.copied_from_id == case.id)
        .values(copied_from_id=None, updated_at=func.now())
    )
    version_ids = select(TestCaseVersion.id).where(TestCaseVersion.test_case_id == case.id)
    session.execute(delete(TestSuiteCase).where(TestSuiteCase.test_case_id == case.id))
    session.execute(delete(TestPlanCase).where(TestPlanCase.test_case_id == case.id))
    session.execute(delete(TestStep).where(TestStep.case_version_id.in_(version_ids)))
    session.execute(delete(TestCaseVersion).where(TestCaseVersion.test_case_id == case.id))
    session.delete(case)
    session.commit()


def copy_cases(session: Session, ids: list[uuid.UUID], principal: Principal) -> list[TestCase]:
    """Копии — черновики версии 1 со ссылкой на исходный кейс (FR-TC-03), в одной транзакции.

    Связь с автотестом не копируется: один ключ автотеста — один кейс.
    """
    errors = [
        {"field": f"ids.{i}", "reason": "duplicate"} for i, x in enumerate(ids) if x in ids[:i]
    ]
    sources = {
        case.id: case
        for case in session.scalars(select(TestCaseRow).where(TestCaseRow.id.in_(ids)))
    }
    errors += [
        {"field": f"ids.{i}", "reason": "not_found"} for i, x in enumerate(ids) if x not in sources
    ]
    if errors:
        raise validation_failed(errors)
    copies = []
    for source_id in ids:
        source = sources[source_id]
        current = get_version(session, source, source.current_version)
        copy = TestCaseRow(
            key=next_key(session, f"TC-{source.module}"),
            status=CaseStatus.DRAFT,
            current_version=1,
            module=source.module,
            copied_from_id=source.id,
            template_id=source.template_id,
            created_by=principal.subject,
            **{field: getattr(source, field) for field in REF_FIELDS},
        )
        session.add(copy)
        session.flush()
        content = {field: getattr(current, field) for field in CONTENT_FIELDS}
        content.update(automated=False, autotest_key=None)
        steps = [(step.action, step.expected_result) for step in current.steps]
        copies.append(
            (copy, insert_version(session, copy, 1, content, steps, [], principal.subject))
        )
    session.commit()
    return [_out(session, copy, version, with_last_result=False) for copy, version in copies]


def insert_version(
    session: Session,
    case: TestCaseRow,
    number: int,
    content: dict[str, Any],
    steps: Steps,
    changed_fields: list[str],
    author: str,
) -> TestCaseVersion:
    version = TestCaseVersion(
        test_case_id=case.id,
        version=number,
        changed_fields=changed_fields,
        author=author,
        **content,
    )
    version.steps = [
        TestStep(position=position, action=action, expected_result=expected)
        for position, (action, expected) in enumerate(steps, start=1)
    ]
    session.add(version)
    session.flush()
    return version


def content_of(data: TestCaseInput) -> dict[str, Any]:
    content = {field: getattr(data, field) for field in CONTENT_FIELDS}
    content["autotest_key"] = _blank_to_none(content["autotest_key"])
    content["severity"] = str(data.severity) if data.severity else None
    return content


def steps_of(data: TestCaseInput) -> Steps:
    return [(step.action, step.expected_result) for step in data.steps or []]


def _apply_template(
    session: Session, template_id: uuid.UUID, content: dict[str, Any], steps: Steps | None
) -> Steps:
    """Незаполненные поля и шаги берутся из шаблона (FR-TC-06)."""
    template = session.get(TestCaseTemplate, template_id)
    if template is None or not template.is_active:
        reason = "not_found" if template is None else "inactive"
        raise validation_failed([{"field": "templateId", "reason": reason}])
    for field in TEMPLATE_FIELDS:
        if content[field] is None:
            content[field] = template.body.get(field)
    if steps is None:
        steps = [(s["action"], s["expectedResult"]) for s in template.body.get("steps", [])]
    return steps


def _content_errors(content: dict[str, Any]) -> list[dict[str, str]]:
    errors = [{"field": f, "reason": "required"} for f in CLASSIFIER_FIELDS if not content[f]]
    if content["automated"] and not content["autotest_key"]:
        errors.append({"field": "autotestKey", "reason": "required"})
    return errors


def _is_ready(version: TestCaseVersion) -> bool:
    return bool(version.title.strip()) and any(
        step.action.strip() and step.expected_result.strip() for step in version.steps
    )


def _require_automation_role(principal: Principal) -> None:
    if not principal.has_any(*AUTOMATION_ROLES):
        raise ApiError(
            403, "PERMISSION_DENIED", "Признак и ключ автотеста меняют автоматизатор и QA-лид"
        )


def _version_conflict(case: TestCaseRow) -> ApiError:
    return conflict(
        "VERSION_CONFLICT",
        f"Кейс {case.key} уже сохранён другим запросом: откройте последнюю версию",
        [{"field": "version", "reason": f"current:{case.current_version}"}],
    )


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if isinstance(value, str) else value


def _out(
    session: Session, case: TestCaseRow, version: TestCaseVersion, with_last_result: bool = True
) -> TestCase:
    out = TestCase.model_validate(case_fields(case, version))
    if with_last_result:
        out.last_result = last_results(session, [case.id]).get(case.id)
    return out
