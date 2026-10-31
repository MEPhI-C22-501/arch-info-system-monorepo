"""Прогоны.

Создание фиксирует текущие версии кейсов строками run_result (ADR-003). Строка прогона
блокируется на время записи результата и смены статуса: так результат не попадает в только что
завершённый прогон (120, раздел 8), а последний кейс не проскакивает автозавершение (050,
раздел 4). Запуск блокирует строку набора: один набор исполняется на окружении один раз
(FR-RUN-10). Поверх этого модуля работают планы и демо-данные: они вызывают функции без
фиксации транзакции (insert_run, start, finish, write_result).
"""

import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, Select, delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Principal, Role
from app.cases.schemas import CaseFilter
from app.cases.service import CURRENT_VERSION, filter_clauses
from app.defects.schemas import DefectLink
from app.defects.service import links_of_results, register_failure
from app.errors import ApiError, conflict, not_found, validation_failed
from app.keys import next_key
from app.models import RunResult as RunResultRow
from app.models import (
    DefectRunLink,
    Environment,
    StepResult,
    TestCase,
    TestCaseVersion,
    TestPlan,
    TestPlanCase,
    TestRun,
    TestStep,
    TestSuite,
)
from app.models.enums import (
    CaseStatus,
    PlanStatus,
    ResultStatus,
    RunStatus,
    RunTrigger,
    SuiteStatus,
)
from app.runs.schemas import ResultInput, Run, RunInput, RunResult, RunResultStep, RunSummary
from app.schemas import Page, PageParams, paginate_rows

# 050, раздел 4.
TRANSITIONS = {
    RunStatus.CREATED: {RunStatus.IN_PROGRESS, RunStatus.ABORTED},
    RunStatus.IN_PROGRESS: {RunStatus.COMPLETED, RunStatus.ABORTED},
    RunStatus.COMPLETED: set(),
    RunStatus.ABORTED: set(),
}
FINISHED_STATUSES = (RunStatus.COMPLETED, RunStatus.ABORTED)
UNFINISHED_STATUSES = (RunStatus.CREATED, RunStatus.IN_PROGRESS)
RUNNABLE_CASE_STATUSES = (CaseStatus.ACTUAL, CaseStatus.NEEDS_UPDATE)
# Причина у результата SKIPPED, которая считается «не проверено» (vision 4.6, 130 раздел 4.6).
UNVERIFIED_REASON = "проверка невозможна"

Composition = list[tuple[uuid.UUID, uuid.UUID]]


def list_runs(
    session: Session,
    principal: Principal,
    plan_id: uuid.UUID | None,
    suite_id: uuid.UUID | None,
    status: RunStatus | None,
    params: PageParams,
) -> Page[Run]:
    stmt = select(TestRun).order_by(TestRun.created_at.desc(), TestRun.id)
    if plan_id is not None:
        stmt = stmt.where(TestRun.plan_id == plan_id)
    if suite_id is not None:
        stmt = stmt.where(TestRun.suite_id == suite_id)
    if status is not None:
        stmt = stmt.where(TestRun.status == status)
    if _own_runs_only(principal):
        stmt = stmt.where(TestRun.started_by == principal.subject)
    return paginate_rows(session, stmt, params, Run, lambda rows: _runs(session, rows))


def read_run(session: Session, run_id: uuid.UUID, principal: Principal) -> Run:
    return _run(session, _get(session, run_id, principal))


def create_run(
    session: Session, data: RunInput, principal: Principal, idempotency_key: str | None
) -> tuple[Run, bool]:
    """Возвращает прогон и признак создания; повтор с тем же ключом создания не означает."""
    existing = _by_idempotency_key(session, principal, idempotency_key)
    if existing is not None:
        return _run(session, existing), False

    if principal.has_any(Role.CI) and not _is_human(principal) and data.plan_id is not None:
        raise ApiError(403, "PERMISSION_DENIED", "Сервис пайплайна запускает только наборы")
    errors = _source_errors(data)
    if errors:
        raise validation_failed(errors, "Прогон не прошёл проверку")
    environment = _environment(session, data.environment)
    if data.plan_id is not None:
        plan = _active_plan(session, data.plan_id)
        suite = None
        scope = _plan_scope(plan.id)
    else:
        plan = None
        suite = _active_suite(session, data, lock=data.start)
        scope = filter_clauses(session, CaseFilter(suite_id=suite.id))
    composition = _composition(session, scope, data.automated_only)
    if not composition:
        raise ApiError(422, "RUN_EMPTY", "В составе прогона нет ни одного кейса")
    if data.start and suite is not None:
        # Блокировка могла дождаться параллельного запроса с тем же ключом.
        existing = _by_idempotency_key(session, principal, idempotency_key)
        if existing is not None:
            return _run(session, existing), False
        _ensure_not_running(session, suite, environment, data.suite_name is None)

    trigger = RunTrigger.CI if not _is_human(principal) else RunTrigger.MANUAL
    try:
        with session.begin_nested():
            run = insert_run(
                session,
                plan_id=plan.id if plan else None,
                suite_id=suite.id if suite else None,
                environment_id=environment.id,
                trigger=trigger,
                started_by=principal.subject,
                composition=composition,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing = _by_idempotency_key(session, principal, idempotency_key)
        if existing is None:
            raise
        return _run(session, existing), False
    if data.start:
        _advance(run, RunStatus.IN_PROGRESS)
        run.started_at = _now()
    session.commit()
    return _run(session, run), True


def insert_run(
    session: Session,
    *,
    plan_id: uuid.UUID | None,
    suite_id: uuid.UUID | None,
    environment_id: uuid.UUID,
    trigger: RunTrigger,
    started_by: str,
    composition: Composition,
    idempotency_key: str | None = None,
) -> TestRun:
    run = TestRun(
        key=next_key(session, "RUN"),
        plan_id=plan_id,
        suite_id=suite_id,
        environment_id=environment_id,
        status=RunStatus.CREATED,
        trigger=trigger,
        started_by=started_by,
        idempotency_key=idempotency_key,
        created_at=_now(),
    )
    session.add(run)
    session.flush()
    session.add_all(
        RunResultRow(
            run_id=run.id,
            test_case_id=case_id,
            case_version_id=version_id,
            status=ResultStatus.NOT_RUN,
        )
        for case_id, version_id in composition
    )
    session.flush()
    return run


def delete_run(session: Session, run_id: uuid.UUID, principal: Principal) -> None:
    """Физически удаляется только прогон без записей (120, раздел 8)."""
    run = _get(session, run_id, principal, lock=True)
    if session.scalar(select(_has_records(run))):
        raise conflict(
            "RUN_HAS_RESULTS", f"В прогоне {run.key} есть результаты: удаление запрещено"
        )
    session.execute(delete(RunResultRow).where(RunResultRow.run_id == run.id))
    session.delete(run)
    session.commit()


def plan_composition(session: Session, plan_id: uuid.UUID) -> Composition:
    return _composition(session, _plan_scope(plan_id), False)


def _plan_scope(plan_id: uuid.UUID) -> list[ColumnElement[bool]]:
    members = select(TestPlanCase.test_case_id).where(TestPlanCase.plan_id == plan_id)
    return [TestCase.id.in_(members)]


def start_run(session: Session, run_id: uuid.UUID, principal: Principal) -> Run:
    run = _get(session, run_id, principal, lock=True)
    start(session, run)
    session.commit()
    return _run(session, run)


def start(session: Session, run: TestRun) -> None:
    _ensure_allowed(run, RunStatus.IN_PROGRESS)
    if run.suite_id is not None:
        suite = session.get(TestSuite, run.suite_id, with_for_update=True)
        environment = session.get(Environment, run.environment_id)
        _ensure_not_running(session, suite, environment, True)
    run.status = RunStatus.IN_PROGRESS
    run.started_at = _now()


def complete_run(session: Session, run_id: uuid.UUID, principal: Principal) -> Run:
    run = _get(session, run_id, principal, lock=True)
    finish(run, RunStatus.COMPLETED)
    session.commit()
    return _run(session, run)


def abort_run(session: Session, run_id: uuid.UUID, principal: Principal) -> Run:
    run = _get(session, run_id, principal, lock=True)
    finish(run, RunStatus.ABORTED)
    session.commit()
    return _run(session, run)


def finish(run: TestRun, target: RunStatus) -> None:
    _advance(run, target)
    run.finished_at = _now()
    if run.started_at is not None:
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)


def abort_plan_runs(session: Session, plan_id: uuid.UUID) -> None:
    """Прерывает незавершённые прогоны отменяемого плана; транзакцию фиксирует план."""
    runs = session.scalars(
        select(TestRun)
        .where(TestRun.plan_id == plan_id, TestRun.status.in_(UNFINISHED_STATUSES))
        .with_for_update()
    )
    for run in runs:
        finish(run, RunStatus.ABORTED)


def list_results(
    session: Session,
    run_id: uuid.UUID,
    principal: Principal,
    status: ResultStatus | None,
    assignee: str | None,
    params: PageParams,
) -> Page[RunResult]:
    run = _get(session, run_id, principal)
    stmt = (
        select(RunResultRow)
        .join(TestCase, TestCase.id == RunResultRow.test_case_id)
        .where(RunResultRow.run_id == run.id)
        .order_by(TestCase.key, RunResultRow.id)
    )
    if status is not None:
        stmt = stmt.where(RunResultRow.status == status)
    if assignee is not None:
        stmt = stmt.where(RunResultRow.assignee == assignee)
    return paginate_rows(session, stmt, params, RunResult, lambda rows: _results(session, rows))


def record_result(
    session: Session,
    run_id: uuid.UUID,
    result_id: uuid.UUID,
    data: ResultInput,
    principal: Principal,
) -> RunResult:
    run = _get(session, run_id, principal, lock=True)
    result = session.get(RunResultRow, result_id)
    if result is None or result.run_id != run.id:
        raise not_found("Результат")
    if result.assignee not in (None, principal.subject) and not principal.has_any(Role.LEAD):
        raise ApiError(403, "PERMISSION_DENIED", "Кейс назначен другому тестировщику")
    defect = write_result(session, run, result, data, principal.subject)
    session.commit()
    return _results(session, [result], {result.id: defect} if defect else None)[0]


def write_result(
    session: Session, run: TestRun, result: RunResultRow, data: ResultInput, author: str
) -> DefectLink | None:
    """Результат кейса и шагов; при провале — автодефект в той же транзакции (ADR-006)."""
    if run.status in FINISHED_STATUSES:
        raise conflict("RUN_FINISHED", f"Прогон {run.key} завершён, результаты не изменяются")
    if run.status != RunStatus.IN_PROGRESS:
        raise conflict(
            "INVALID_TRANSITION",
            f"Прогон {run.key} ещё не запущен",
            [{"field": "status", "reason": f"allowed:{RunStatus.IN_PROGRESS}"}],
        )
    # Только шаги зафиксированной версии: кейс мог измениться после создания прогона (ADR-003).
    steps = list(
        session.scalars(
            select(TestStep)
            .where(TestStep.case_version_id == result.case_version_id)
            .order_by(TestStep.position)
        )
    )
    failed_step, errors = _check_result(data, steps)
    if errors:
        raise validation_failed(errors, "Результат не прошёл проверку")

    finished = data.status != ResultStatus.NOT_RUN
    now = _now()
    result.status = data.status
    result.actual_result = _actual_result(data, failed_step)
    result.comment = data.comment
    result.failure_reason = data.failure_reason
    result.failed_step_position = failed_step.position if failed_step else None
    result.duration_ms = data.duration_ms
    result.executed_by = author if finished else None
    result.started_at = (result.started_at or now) if finished else None
    result.finished_at = now if finished else None
    session.execute(delete(StepResult).where(StepResult.run_result_id == result.id))
    session.add_all(
        StepResult(
            run_result_id=result.id,
            step_id=step.step_id,
            status=step.status,
            actual_result=step.actual_result,
            comment=step.comment,
        )
        for step in data.steps or []
    )
    session.flush()

    defect = None
    if data.status == ResultStatus.FAILED:
        version = session.get(TestCaseVersion, result.case_version_id)
        defect = register_failure(session, run, result, version, failed_step, steps)
    if not session.scalar(select(_has_unfinished_results(run))):
        finish(run, RunStatus.COMPLETED)
    return defect


def _has_unfinished_results(run: TestRun) -> ColumnElement[bool]:
    return exists().where(
        RunResultRow.run_id == run.id, RunResultRow.status == ResultStatus.NOT_RUN
    )


def _has_records(run: TestRun) -> ColumnElement[bool]:
    """Результат, вернувшийся в NOT_RUN, сохраняет шаги и связь с дефектом."""
    results = select(RunResultRow.id).where(RunResultRow.run_id == run.id)
    return or_(
        exists().where(RunResultRow.run_id == run.id, RunResultRow.status != ResultStatus.NOT_RUN),
        exists().where(StepResult.run_result_id.in_(results)),
        exists().where(DefectRunLink.run_result_id.in_(results)),
    )


def _check_result(
    data: ResultInput, steps: list[TestStep]
) -> tuple[TestStep | None, list[dict[str, str]]]:
    """Упавший шаг — первый по порядку с FAILED — и ошибки проверки запроса."""
    by_id = {step.id: step for step in steps}
    errors = []
    seen = set()
    failed = []
    for i, step in enumerate(data.steps or []):
        if step.step_id not in by_id:
            errors.append({"field": f"steps.{i}.stepId", "reason": "not_in_case_version"})
        elif step.step_id in seen:
            errors.append({"field": f"steps.{i}.stepId", "reason": "duplicate"})
        elif step.status == ResultStatus.FAILED:
            failed.append(step)
        seen.add(step.step_id)
    if failed and data.status != ResultStatus.FAILED:
        errors.append({"field": "status", "reason": "failed_step"})
    first = min(failed, key=lambda step: by_id[step.step_id].position, default=None)
    if data.status == ResultStatus.FAILED and not (
        data.actual_result or (first and first.actual_result)
    ):
        errors.append({"field": "actualResult", "reason": "required"})
    return (by_id[first.step_id] if first else None), errors


def _actual_result(data: ResultInput, failed_step: TestStep | None) -> str | None:
    if data.actual_result or failed_step is None:
        return data.actual_result
    return next(s.actual_result for s in data.steps if s.step_id == failed_step.id)


def _advance(run: TestRun, target: RunStatus) -> None:
    _ensure_allowed(run, target)
    run.status = target


def _ensure_allowed(run: TestRun, target: RunStatus) -> None:
    allowed = TRANSITIONS[RunStatus(run.status)]
    if target not in allowed:
        raise conflict(
            "INVALID_TRANSITION",
            f"Переход {run.status} → {target} недопустим",
            [{"field": "status", "reason": "allowed:" + ",".join(sorted(allowed))}],
        )


def _source_errors(data: RunInput) -> list[dict[str, str]]:
    sources = [data.plan_id, data.suite_id, data.suite_name]
    if sum(source is not None for source in sources) != 1:
        return [{"field": "planId", "reason": "exactly_one_of:planId,suiteId,suiteName"}]
    return []


def _environment(session: Session, code: str) -> Environment:
    environment = session.scalar(select(Environment).where(Environment.code == code))
    if environment is None or not environment.is_active:
        reason = "not_found" if environment is None else "inactive"
        raise validation_failed([{"field": "environment", "reason": reason}])
    return environment


def _active_plan(session: Session, plan_id: uuid.UUID) -> TestPlan:
    plan = session.get(TestPlan, plan_id, with_for_update={"key_share": True, "read": True})
    if plan is None:
        raise validation_failed([{"field": "planId", "reason": "not_found"}])
    if plan.status != PlanStatus.ACTIVE:
        raise conflict(
            "PLAN_NOT_ACTIVE",
            f"План {plan.key} в статусе {plan.status}: прогоны создаются только из активного",
        )
    return plan


def _active_suite(session: Session, data: RunInput, lock: bool) -> TestSuite:
    field = "suiteId" if data.suite_id is not None else "suiteName"
    stmt = select(TestSuite).where(
        TestSuite.id == data.suite_id
        if data.suite_id is not None
        else TestSuite.name == data.suite_name
    )
    suite = session.scalar(stmt.with_for_update() if lock else stmt)
    if suite is None:
        raise validation_failed([{"field": field, "reason": "not_found"}])
    if suite.status != SuiteStatus.ACTIVE:
        raise validation_failed([{"field": field, "reason": "archived"}])
    return suite


def _composition(
    session: Session, scope: list[ColumnElement[bool]], automated_only: bool
) -> Composition:
    """Кейсы и их текущие версии: черновики и архив в прогон не попадают (050, раздел 2)."""
    stmt: Select = (
        select(TestCase.id, TestCaseVersion.id)
        .join(TestCaseVersion, CURRENT_VERSION)
        .where(*scope, TestCase.status.in_(RUNNABLE_CASE_STATUSES))
        .order_by(TestCase.key)
    )
    if automated_only:
        stmt = stmt.where(TestCaseVersion.automated)
    return list(session.execute(stmt).tuples())


def _ensure_not_running(
    session: Session, suite: TestSuite, environment: Environment, by_id: bool
) -> None:
    running = session.scalar(
        select(TestRun.key).where(
            TestRun.suite_id == suite.id,
            TestRun.environment_id == environment.id,
            TestRun.status == RunStatus.IN_PROGRESS,
        )
    )
    if running:
        raise conflict(
            "SUITE_ALREADY_RUNNING",
            f"Набор {suite.name} уже выполняется на окружении {environment.code}: {running}",
            [{"field": "suiteId" if by_id else "suiteName", "reason": f"running:{running}"}],
        )


def _by_idempotency_key(session: Session, principal: Principal, key: str | None) -> TestRun | None:
    if key is None:
        return None
    return session.scalar(
        select(TestRun).where(
            TestRun.started_by == principal.subject, TestRun.idempotency_key == key
        )
    )


def _get(session: Session, run_id: uuid.UUID, principal: Principal, lock: bool = False) -> TestRun:
    run = session.get(TestRun, run_id, with_for_update=lock or None)
    if run is None or (_own_runs_only(principal) and run.started_by != principal.subject):
        raise not_found("Прогон")
    return run


def _is_human(principal: Principal) -> bool:
    return principal.has_any(Role.VIEWER, Role.TESTER, Role.AUTOMATION, Role.LEAD, Role.ADMIN)


def _own_runs_only(principal: Principal) -> bool:
    """R-06 видит только то, что запустил сам (070, раздел 5б)."""
    return not _is_human(principal)


def _now() -> datetime:
    # Время приложения, а не now() транзакции: списки и lastResult упорядочены по времени, а в
    # одной транзакции now() одинаков.
    return datetime.now(UTC)


def _run(session: Session, run: TestRun) -> Run:
    return _runs(session, [run])[0]


def _runs(session: Session, runs: list[TestRun]) -> list[Run]:
    environments = dict(
        session.execute(
            select(Environment.id, Environment.code).where(
                Environment.id.in_({run.environment_id for run in runs})
            )
        )
        .tuples()
        .all()
    )
    summaries = _summaries(session, [run.id for run in runs])
    return [
        Run.model_validate(
            {
                **{column: getattr(run, column) for column in _RUN_COLUMNS},
                "environment": environments[run.environment_id],
                "summary": summaries.get(run.id, RunSummary()),
                "smoke_verdict": _smoke_verdict(run, summaries.get(run.id)),
            }
        )
        for run in runs
    ]


def _summaries(session: Session, run_ids: list[uuid.UUID]) -> dict[uuid.UUID, RunSummary]:
    unverified_reason = RunResultRow.failure_reason == UNVERIFIED_REASON
    rows = session.execute(
        select(RunResultRow.run_id, RunResultRow.status, unverified_reason, func.count())
        .where(RunResultRow.run_id.in_(run_ids))
        .group_by(RunResultRow.run_id, RunResultRow.status, unverified_reason)
    )
    counters: dict[uuid.UUID, Counter[str]] = {}
    for run_id, status, unverified, count in rows:
        counter = counters.setdefault(run_id, Counter())
        counter[status] += count
        if status == ResultStatus.SKIPPED and unverified:
            counter["unverified"] += count
    return {
        run_id: RunSummary(
            total=sum(c[status] for status in ResultStatus),
            passed=c[ResultStatus.PASSED],
            failed=c[ResultStatus.FAILED],
            blocked=c[ResultStatus.BLOCKED],
            not_run=c[ResultStatus.NOT_RUN],
            skipped=c[ResultStatus.SKIPPED],
            unverified=c["unverified"],
        )
        for run_id, c in counters.items()
    }


def _smoke_verdict(run: TestRun, summary: RunSummary | None) -> str | None:
    if run.status not in FINISHED_STATUSES:
        return None
    return "RED" if summary and summary.failed else "GREEN"


def _results(
    session: Session,
    results: list[RunResultRow],
    defects: dict[uuid.UUID, DefectLink] | None = None,
) -> list[RunResult]:
    version_ids = {result.case_version_id for result in results}
    cases = dict(
        session.execute(
            select(TestCase.id, TestCase.key).where(
                TestCase.id.in_({result.test_case_id for result in results})
            )
        )
        .tuples()
        .all()
    )
    versions = {
        version.id: version
        for version in session.scalars(
            select(TestCaseVersion).where(TestCaseVersion.id.in_(version_ids))
        )
    }
    steps: dict[uuid.UUID, list[TestStep]] = {}
    for step in session.scalars(
        select(TestStep)
        .where(TestStep.case_version_id.in_(version_ids))
        .order_by(TestStep.position)
    ):
        steps.setdefault(step.case_version_id, []).append(step)
    step_results = {
        (row.run_result_id, row.step_id): row
        for row in session.scalars(
            select(StepResult).where(StepResult.run_result_id.in_([r.id for r in results]))
        )
    }
    links = links_of_results(session, [result.id for result in results])
    links.update(defects or {})
    return [
        RunResult.model_validate(
            {
                **{column: getattr(result, column) for column in _RESULT_COLUMNS},
                "test_case_key": cases[result.test_case_id],
                "title": versions[result.case_version_id].title,
                "case_version": versions[result.case_version_id].version,
                "steps": [
                    _result_step(step, step_results.get((result.id, step.id)))
                    for step in steps.get(result.case_version_id, [])
                ],
                "defect": links.get(result.id),
            }
        )
        for result in results
    ]


def _result_step(step: TestStep, row: StepResult | None) -> RunResultStep:
    return RunResultStep(
        step_id=step.id,
        position=step.position,
        action=step.action,
        expected_result=step.expected_result,
        status=row.status if row else ResultStatus.NOT_RUN,
        actual_result=row.actual_result if row else None,
        comment=row.comment if row else None,
    )


_RUN_COLUMNS = (
    "id",
    "key",
    "plan_id",
    "suite_id",
    "parent_run_id",
    "status",
    "trigger",
    "started_by",
    "autotests_commit_sha",
    "sut_versions",
    "created_at",
    "started_at",
    "finished_at",
    "duration_ms",
    "verdict",
    "verdict_by",
    "verdict_at",
)
_RESULT_COLUMNS = (
    "id",
    "test_case_id",
    "assignee",
    "status",
    "failed_step_position",
    "actual_result",
    "comment",
    "failure_reason",
    "executed_by",
    "started_at",
    "finished_at",
    "duration_ms",
)
