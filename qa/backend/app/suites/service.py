"""Наборы кейсов.

Набор MANUAL хранит состав в test_suite_case, набор FILTER — условие в filter; кейсы
FILTER отбираются при создании прогона. «Smoke» (SMOKE) и «Приёмка стенда» (ACCEPTANCE)
существуют в одном экземпляре; их ведёт QA-лид (130, ADR-017). Пайплайн находит «Smoke»
по имени (`suiteName`, 130 раздел 1), поэтому имя и назначение таких наборов не меняются.
"""

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth import Principal, Role
from app.cases.schemas import CaseFilter
from app.cases.service import count_cases
from app.errors import ApiError, conflict, not_found, validation_failed
from app.models import RunSchedule, TestCase, TestSuite, TestSuiteCase
from app.models.enums import CaseStatus, SuiteKind, SuitePurpose, SuiteStatus
from app.schemas import Page, PageParams, paginate
from app.suites.schemas import Suite, SuiteInput

PROTECTED_PURPOSES = (SuitePurpose.SMOKE, SuitePurpose.ACCEPTANCE)


def list_suites(
    session: Session,
    status: SuiteStatus | None,
    purpose: SuitePurpose | None,
    kind: SuiteKind | None,
    params: PageParams,
) -> Page[Suite]:
    stmt = select(TestSuite).order_by(TestSuite.name, TestSuite.id)
    if status is not None:
        stmt = stmt.where(TestSuite.status == status)
    if purpose is not None:
        stmt = stmt.where(TestSuite.purpose == purpose)
    if kind is not None:
        stmt = stmt.where(TestSuite.kind == kind)
    page = paginate(session, stmt, params, Suite)
    for item in page.items:
        _fill(session, item)
    return page


def read_suite(session: Session, suite_id: uuid.UUID) -> Suite:
    return _out(session, _get(session, suite_id))


def create_suite(session: Session, data: SuiteInput, principal: Principal) -> Suite:
    purpose = data.purpose or SuitePurpose.GENERAL
    if purpose in PROTECTED_PURPOSES:
        _require_lead(principal)
    errors = _validate(session, data, None)
    taken = session.scalar(select(TestSuite.name).where(TestSuite.purpose == purpose))
    if purpose in PROTECTED_PURPOSES and taken:
        errors.append({"field": "purpose", "reason": f"exists:{taken}"})
    if errors:
        raise validation_failed(errors, "Набор не прошёл проверку")
    suite = TestSuite(
        name=data.name,
        kind=data.kind,
        filter=_filter_json(data),
        status=SuiteStatus.ACTIVE,
        purpose=purpose,
        owner=principal.subject,
    )
    session.add(suite)
    session.flush()
    _set_members(session, suite, data)
    session.commit()
    return _out(session, suite)


def update_suite(
    session: Session, suite_id: uuid.UUID, data: SuiteInput, principal: Principal
) -> Suite:
    suite = _get(session, suite_id)
    if suite.purpose in PROTECTED_PURPOSES:
        _require_lead(principal)
    errors = _validate(session, data, suite)
    if data.purpose is not None and data.purpose != suite.purpose:
        errors.append({"field": "purpose", "reason": "immutable"})
    if suite.purpose in PROTECTED_PURPOSES and data.name != suite.name:
        errors.append({"field": "name", "reason": f"fixed:{suite.purpose}"})
    if errors:
        raise validation_failed(errors, "Набор не прошёл проверку")
    suite.name = data.name
    suite.kind = data.kind
    suite.filter = _filter_json(data)
    _set_members(session, suite, data)
    session.commit()
    return _out(session, suite)


def archive_suite(session: Session, suite_id: uuid.UUID, principal: Principal) -> Suite:
    """Архивирует владелец или QA-лид; расписания набора отключаются (050, раздел 3а)."""
    suite = _change_status(session, suite_id, principal, SuiteStatus.ARCHIVED, "restore")
    session.execute(
        update(RunSchedule)
        .where(RunSchedule.suite_id == suite.id, RunSchedule.is_active)
        .values(is_active=False)
    )
    session.commit()
    return _out(session, suite)


def restore_suite(session: Session, suite_id: uuid.UUID, principal: Principal) -> Suite:
    suite = _change_status(session, suite_id, principal, SuiteStatus.ACTIVE, "archive")
    session.commit()
    return _out(session, suite)


def _change_status(
    session: Session,
    suite_id: uuid.UUID,
    principal: Principal,
    target: SuiteStatus,
    allowed_action: str,
) -> TestSuite:
    suite = _get(session, suite_id)
    if suite.purpose in PROTECTED_PURPOSES or suite.owner != principal.subject:
        _require_lead(principal)
    if suite.status == target:
        raise conflict(
            "INVALID_TRANSITION",
            f"Набор {suite.name} уже в статусе {target}",
            [{"field": "status", "reason": f"allowed:{allowed_action}"}],
        )
    suite.status = target
    return suite


def _validate(session: Session, data: SuiteInput, suite: TestSuite | None) -> list[dict[str, str]]:
    errors = []
    own_id = suite.id if suite else None
    same_name = session.scalar(select(TestSuite.id).where(TestSuite.name == data.name))
    if same_name not in (None, own_id):
        errors.append({"field": "name", "reason": "duplicate"})
    if data.kind == SuiteKind.FILTER:
        if data.filter is None or data.filter.is_empty():
            errors.append({"field": "filter", "reason": "required"})
        elif data.filter.suite_id is not None:
            errors += _check_filter_suite(session, data.filter.suite_id, own_id)
        if data.case_ids:
            errors.append({"field": "caseIds", "reason": "not_allowed:FILTER"})
    else:
        if data.filter is not None:
            errors.append({"field": "filter", "reason": "not_allowed:MANUAL"})
        errors += _check_members(session, data.case_ids or [], suite)
    return errors


def _check_filter_suite(
    session: Session, target_id: uuid.UUID, own_id: uuid.UUID | None
) -> list[dict[str, str]]:
    # Условие ссылается только на ручной набор: так вычисление не уходит в цикл.
    target = session.get(TestSuite, target_id)
    if target is None or target.id == own_id:
        return [{"field": "filter.suiteId", "reason": "not_found"}]
    if target.kind != SuiteKind.MANUAL:
        return [{"field": "filter.suiteId", "reason": "not_manual"}]
    return []


def _check_members(
    session: Session, case_ids: list[uuid.UUID], suite: TestSuite | None
) -> list[dict[str, str]]:
    """В набор добавляются только актуальные кейсы; уже входящие остаются при любом статусе."""
    query = select(TestCase.id, TestCase.status).where(TestCase.id.in_(case_ids))
    statuses = dict(session.execute(query).tuples().all())
    members = set(_member_ids(session, suite.id)) if suite else set()
    errors = []
    for i, case_id in enumerate(case_ids):
        if case_id not in statuses:
            errors.append({"field": f"caseIds.{i}", "reason": "not_found"})
        elif case_id not in members and statuses[case_id] != CaseStatus.ACTUAL:
            errors.append({"field": f"caseIds.{i}", "reason": f"status:{statuses[case_id]}"})
    return errors


def _set_members(session: Session, suite: TestSuite, data: SuiteInput) -> None:
    wanted = set(data.case_ids or []) if suite.kind == SuiteKind.MANUAL else set()
    current = set(_member_ids(session, suite.id))
    session.execute(
        delete(TestSuiteCase).where(
            TestSuiteCase.suite_id == suite.id, TestSuiteCase.test_case_id.in_(current - wanted)
        )
    )
    session.add_all(TestSuiteCase(suite_id=suite.id, test_case_id=i) for i in wanted - current)
    session.flush()


def _member_ids(session: Session, suite_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(TestSuiteCase.test_case_id)
            .join(TestCase, TestCase.id == TestSuiteCase.test_case_id)
            .where(TestSuiteCase.suite_id == suite_id)
            .order_by(TestCase.key)
        )
    )


def _filter_json(data: SuiteInput) -> dict | None:
    if data.kind != SuiteKind.FILTER or data.filter is None:
        return None
    return data.filter.model_dump(by_alias=True, exclude_none=True, mode="json")


def _get(session: Session, suite_id: uuid.UUID) -> TestSuite:
    suite = session.get(TestSuite, suite_id)
    if suite is None:
        raise not_found("Набор")
    return suite


def _out(session: Session, suite: TestSuite) -> Suite:
    return _fill(session, Suite.model_validate(suite))


def _fill(session: Session, item: Suite) -> Suite:
    if item.kind == SuiteKind.MANUAL:
        item.case_ids = _member_ids(session, item.id)
    item.case_count = count_cases(session, CaseFilter(suite_id=item.id))
    return item


def _require_lead(principal: Principal) -> None:
    if not principal.has_any(Role.LEAD):
        raise ApiError(
            403,
            "PERMISSION_DENIED",
            "Наборы «Smoke», «Приёмка стенда» и чужие наборы архивирует и меняет только QA-лид",
        )
