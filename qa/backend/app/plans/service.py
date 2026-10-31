"""Тест-планы.

Внешние ссылки на релиз, веху и итерацию — строки без проверки: пока кэша release-context нет,
они вводятся вручную и помечаются непроверенными (ADR-010, ADR-015). Статусная машина — 050,
раздел 3. Демо-данные используют функции без фиксации транзакции.
"""

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import Principal
from app.cases.schemas import CaseFilter
from app.cases.service import CURRENT_VERSION, filter_clauses, last_results
from app.errors import ApiError, conflict, not_found, validation_failed
from app.keys import next_key
from app.models import (
    Defect,
    TestCase,
    TestCaseVersion,
    TestPlanCase,
    TestRun,
)
from app.models import TestPlan as TestPlanRow
from app.models.enums import (
    CaseStatus,
    DefectStatus,
    PlanScope,
    PlanStatus,
    ResultStatus,
    SuiteKind,
)
from app.plans.schemas import (
    PlanCasesInput,
    PlanSummary,
    PlanSummaryCase,
    PlanSummaryCounters,
    PlanSummaryDefect,
    TestPlan,
    TestPlanInput,
)
from app.runs.service import UNFINISHED_STATUSES, abort_plan_runs
from app.schemas import Page, PageParams, paginate_rows
from app.suites.schemas import SuiteInput
from app.suites.service import create_suite

CLOSED_STATUSES = (PlanStatus.COMPLETED, PlanStatus.CANCELLED)
# Необязательные ссылки: пустая строка из формы означает «не задано».
OPTIONAL_REFS = (
    "scope_ref",
    "team_ref",
    "tracker_iteration_id",
    "planning_milestone_id",
    "planning_project_id",
    "planning_release_id",
    "planning_plan_version_id",
)


def list_plans(
    session: Session,
    status: PlanStatus | None,
    tracker_iteration_id: str | None,
    planning_project_id: str | None,
    planning_release_id: str | None,
    params: PageParams,
) -> Page[TestPlan]:
    stmt = select(TestPlanRow).order_by(TestPlanRow.created_at.desc(), TestPlanRow.id)
    if status is not None:
        stmt = stmt.where(TestPlanRow.status == status)
    if tracker_iteration_id is not None:
        stmt = stmt.where(TestPlanRow.tracker_iteration_id == tracker_iteration_id)
    if planning_project_id is not None:
        stmt = stmt.where(TestPlanRow.planning_project_id == planning_project_id)
    if planning_release_id is not None:
        stmt = stmt.where(TestPlanRow.planning_release_id == planning_release_id)
    return paginate_rows(session, stmt, params, TestPlan, lambda rows: _plans(session, rows))


def read_plan(session: Session, plan_id: uuid.UUID) -> TestPlan:
    return _plan(session, _get(session, plan_id))


def create_plan(session: Session, data: TestPlanInput) -> TestPlan:
    plan = insert_plan(session, data)
    session.commit()
    return _plan(session, plan)


def insert_plan(session: Session, data: TestPlanInput) -> TestPlanRow:
    values = _validated(data)
    plan = TestPlanRow(
        key=next_key(session, "TP"),
        status=PlanStatus.DRAFT,
        refs_verified=False,
        created_at=datetime.now(UTC),
        **values,
    )
    session.add(plan)
    session.flush()
    return plan


def update_plan(session: Session, plan_id: uuid.UUID, data: TestPlanInput) -> TestPlan:
    plan = _get(session, plan_id, lock=True)
    _ensure_open(plan)
    values = _validated(data)
    for column, value in values.items():
        setattr(plan, column, value)
    # Ссылки могли измениться: проверка по источнику выполняется заново.
    plan.refs_verified = False
    session.commit()
    return _plan(session, plan)


def add_cases(
    session: Session, plan_id: uuid.UUID, data: PlanCasesInput, principal: Principal
) -> TestPlan:
    plan = _get(session, plan_id, lock=True)
    _ensure_open(plan)
    cases, errors = _selected_cases(session, data)
    if errors:
        raise validation_failed(errors, "Состав плана не прошёл проверку")
    insert_cases(session, plan, cases, principal.subject)
    if data.save_as_suite is None:
        session.commit()
    else:
        # create_suite фиксирует транзакцию, поэтому состав плана и набор сохраняются вместе.
        suite = SuiteInput(name=data.save_as_suite, kind=SuiteKind.FILTER, filter=data.filter)
        try:
            create_suite(session, suite, principal)
        except ApiError:
            session.rollback()
            raise
    return _plan(session, plan)


def insert_cases(
    session: Session, plan: TestPlanRow, cases: list[dict[str, Any]], author: str
) -> None:
    """Новые кейсы — только актуальные; уже входящие остаются при любом статусе (как у набора)."""
    members = set(_member_ids(session, plan.id))
    not_actual = [
        {"field": case["field"], "reason": f"{case['key']}:{case['status']}"}
        for case in cases
        if case["id"] not in members and case["status"] != CaseStatus.ACTUAL
    ]
    if not_actual:
        raise conflict("CASE_NOT_ACTUAL", "В план добавляются только актуальные кейсы", not_actual)
    new = [
        {"plan_id": plan.id, "test_case_id": case["id"], "added_by": author}
        for case in cases
        if case["id"] not in members
    ]
    if new:
        session.execute(insert(TestPlanCase).on_conflict_do_nothing(), new)
    plan.updated_at = func.now()
    session.flush()


def remove_case(session: Session, plan_id: uuid.UUID, case_id: uuid.UUID) -> None:
    plan = _get(session, plan_id, lock=True)
    _ensure_open(plan)
    removed = session.execute(
        delete(TestPlanCase).where(
            TestPlanCase.plan_id == plan.id, TestPlanCase.test_case_id == case_id
        )
    )
    if removed.rowcount != 1:
        raise not_found("Кейс плана")
    plan.updated_at = func.now()
    session.commit()


def activate_plan(session: Session, plan_id: uuid.UUID) -> TestPlan:
    plan = _get(session, plan_id, lock=True)
    activate(session, plan)
    session.commit()
    return _plan(session, plan)


def activate(session: Session, plan: TestPlanRow) -> None:
    _ensure_status(plan, PlanStatus.ACTIVE, (PlanStatus.DRAFT,))
    if not _member_ids(session, plan.id):
        raise conflict("PLAN_EMPTY", f"В плане {plan.key} нет кейсов")
    plan.status = PlanStatus.ACTIVE


def complete_plan(session: Session, plan_id: uuid.UUID) -> TestPlan:
    plan = _get(session, plan_id, lock=True)
    _ensure_status(plan, PlanStatus.COMPLETED, (PlanStatus.ACTIVE,))
    unfinished = session.scalars(
        select(TestRun.key)
        .where(TestRun.plan_id == plan.id, TestRun.status.in_(UNFINISHED_STATUSES))
        .order_by(TestRun.key)
    ).all()
    if unfinished:
        raise conflict(
            "RUNS_NOT_FINISHED",
            f"В плане {plan.key} есть незавершённые прогоны",
            [{"field": "runs", "reason": f"unfinished:{key}"} for key in unfinished],
        )
    plan.status = PlanStatus.COMPLETED
    session.commit()
    return _plan(session, plan)


def cancel_plan(session: Session, plan_id: uuid.UUID) -> TestPlan:
    plan = _get(session, plan_id, lock=True)
    _ensure_status(plan, PlanStatus.CANCELLED, (PlanStatus.DRAFT, PlanStatus.ACTIVE))
    abort_plan_runs(session, plan.id)
    plan.status = PlanStatus.CANCELLED
    session.commit()
    return _plan(session, plan)


def read_summary(session: Session, plan_id: uuid.UUID) -> PlanSummary:
    plan = _get(session, plan_id)
    rows = session.execute(
        select(TestCase.id, TestCase.key, TestCase.status, TestCaseVersion.title)
        .join(TestPlanCase, TestPlanCase.test_case_id == TestCase.id)
        .join(TestCaseVersion, CURRENT_VERSION)
        .where(TestPlanCase.plan_id == plan.id)
        .order_by(TestCase.key)
    ).all()
    case_ids = [row.id for row in rows]
    results = last_results(session, case_ids)
    cases = [
        PlanSummaryCase(
            test_case_id=row.id,
            test_case_key=row.key,
            title=row.title,
            status=row.status,
            last_result=results.get(row.id),
        )
        for row in rows
    ]
    statuses = Counter(
        case.last_result.status if case.last_result else ResultStatus.NOT_RUN for case in cases
    )
    defects = session.scalars(
        select(Defect)
        .where(Defect.test_case_id.in_(case_ids), Defect.status != DefectStatus.CLOSED)
        .order_by(Defect.key)
    )
    return PlanSummary(
        plan_id=plan.id,
        counters=PlanSummaryCounters(
            total=len(cases),
            passed=statuses[ResultStatus.PASSED],
            failed=statuses[ResultStatus.FAILED],
            blocked=statuses[ResultStatus.BLOCKED],
            skipped=statuses[ResultStatus.SKIPPED],
            not_run=statuses[ResultStatus.NOT_RUN],
        ),
        cases=cases,
        open_defects=[PlanSummaryDefect.model_validate(defect) for defect in defects],
    )


def _validated(data: TestPlanInput) -> dict[str, Any]:
    values = data.model_dump()
    for column in OPTIONAL_REFS:
        value = values[column]
        values[column] = value.strip() or None if isinstance(value, str) else value
    errors = []
    if values["start_date"] > values["end_date"]:
        errors.append({"field": "endDate", "reason": "before_start"})
    if data.scope_kind in (PlanScope.RELEASE, PlanScope.PROJECT):
        if not values["planning_project_id"]:
            errors.append({"field": "planningProjectId", "reason": "required"})
    if data.scope_kind == PlanScope.RELEASE and not values["planning_release_id"]:
        errors.append({"field": "planningReleaseId", "reason": "required"})
    if errors:
        raise validation_failed(errors, "План не прошёл проверку")
    return values


def _selected_cases(
    session: Session, data: PlanCasesInput
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Кейсы запроса: {id, key, status, field}; field — куда указать в ошибке."""
    has_ids, has_filter = data.ids is not None, data.filter is not None
    if has_ids == has_filter:
        return [], [{"field": "ids", "reason": "exactly_one_of:ids,filter"}]
    if data.save_as_suite is not None and not has_filter:
        return [], [{"field": "saveAsSuite", "reason": "requires_filter"}]
    if has_filter:
        return _filtered_cases(session, data.filter)
    rows = session.execute(
        select(TestCase.id, TestCase.key, TestCase.status).where(TestCase.id.in_(data.ids))
    )
    found = {row.id: row for row in rows}
    cases, errors = [], []
    for i, case_id in enumerate(data.ids):
        row = found.get(case_id)
        if row is None:
            errors.append({"field": f"ids.{i}", "reason": "not_found"})
        else:
            cases.append({"id": row.id, "key": row.key, "status": row.status, "field": f"ids.{i}"})
    return cases, errors


def _filtered_cases(
    session: Session, case_filter: CaseFilter
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if case_filter.is_empty():
        return [], [{"field": "filter", "reason": "required"}]
    rows = session.execute(
        select(TestCase.id, TestCase.key, TestCase.status)
        .join(TestCaseVersion, CURRENT_VERSION)
        .where(*filter_clauses(session, case_filter))
        .order_by(TestCase.key)
    )
    return [
        {"id": row.id, "key": row.key, "status": row.status, "field": "filter"} for row in rows
    ], []


def _ensure_open(plan: TestPlanRow) -> None:
    if plan.status in CLOSED_STATUSES:
        raise conflict("PLAN_CLOSED", f"План {plan.key} закрыт: изменения запрещены")


def _ensure_status(plan: TestPlanRow, target: PlanStatus, allowed: tuple[PlanStatus, ...]) -> None:
    if plan.status not in allowed:
        raise conflict(
            "INVALID_TRANSITION",
            f"Переход {plan.status} → {target} недопустим",
            [{"field": "status", "reason": "allowed:" + ",".join(allowed)}],
        )


def _member_ids(session: Session, plan_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(TestPlanCase.test_case_id)
            .join(TestCase, TestCase.id == TestPlanCase.test_case_id)
            .where(TestPlanCase.plan_id == plan_id)
            .order_by(TestCase.key)
        )
    )


def _get(session: Session, plan_id: uuid.UUID, lock: bool = False) -> TestPlanRow:
    plan = session.get(TestPlanRow, plan_id, with_for_update=lock or None)
    if plan is None:
        raise not_found("План")
    return plan


def _plan(session: Session, plan: TestPlanRow) -> TestPlan:
    return _plans(session, [plan])[0]


def _plans(session: Session, plans: list[TestPlanRow]) -> list[TestPlan]:
    members: dict[uuid.UUID, list[uuid.UUID]] = {}
    rows = session.execute(
        select(TestPlanCase.plan_id, TestPlanCase.test_case_id)
        .join(TestCase, TestCase.id == TestPlanCase.test_case_id)
        .where(TestPlanCase.plan_id.in_([plan.id for plan in plans]))
        .order_by(TestCase.key)
    )
    for plan_id, case_id in rows:
        members.setdefault(plan_id, []).append(case_id)
    items = []
    for plan in plans:
        item = TestPlan.model_validate(plan)
        item.case_ids = members.get(plan.id, [])
        item.case_count = len(item.case_ids)
        items.append(item)
    return items
