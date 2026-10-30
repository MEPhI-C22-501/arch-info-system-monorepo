"""Дефекты.

Автодефект создаётся в транзакции записи результата: один незакрытый на кейс держит индекс
defect_open_auto_uq, проигравший гонку запрос получает IntegrityError в savepoint и связывает
результат с уже созданным дефектом (ADR-006). Запрос к Task Tracker — строка outbox_message
той же транзакции; отправляет её воркер (ADR-007). Статусы разработки принадлежат Task Tracker
(ADR-008): вручную их ставит только QA-лид и только при выключенном опросе.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pydantic.alias_generators import to_camel

from app.admin.service import check_codes
from app.auth import Principal, Role
from app.cases.service import get_version
from app.config import get_settings
from app.defects.schemas import (
    Defect,
    DefectComment,
    DefectCommentInput,
    DefectDetail,
    DefectHistoryEntry,
    DefectInput,
    DefectLink,
    DefectRun,
    DefectUpdate,
)
from app.errors import ApiError, conflict, not_found, validation_failed
from app.keys import next_key
from app.models import DefectComment as DefectCommentRow
from app.models import (
    DefectHistory,
    DefectRunLink,
    Environment,
    OutboxMessage,
    RunResult,
    TestCase,
    TestCaseVersion,
    TestPlan,
    TestRun,
    TestStep,
)
from app.models import Defect as DefectRow
from app.models.enums import (
    TRACKER_OWNED_STATUSES,
    ChangeSource,
    ClassifierKind,
    DefectOrigin,
    DefectStatus,
    OutboxKind,
    Severity,
    TrackerSyncState,
)
from app.schemas import Page, PageParams, paginate_rows

# 050, раздел 6.
TRANSITIONS = {
    DefectStatus.NEW: {DefectStatus.OPEN},
    DefectStatus.OPEN: {DefectStatus.IN_PROGRESS},
    DefectStatus.IN_PROGRESS: {DefectStatus.FIXED},
    DefectStatus.FIXED: {DefectStatus.READY_FOR_TEST},
    DefectStatus.READY_FOR_TEST: {DefectStatus.CLOSED, DefectStatus.REOPENED},
    DefectStatus.CLOSED: {DefectStatus.REOPENED},
    DefectStatus.REOPENED: {DefectStatus.IN_PROGRESS},
}

# 130, раздел 6.1; шкала Task Tracker — Q-02.
TRACKER_SEVERITY = {
    Severity.BLOCKER: "critical",
    Severity.CRITICAL: "critical",
    Severity.MAJOR: "high",
    Severity.MINOR: "medium",
    Severity.TRIVIAL: "low",
}
TRACKER_SOURCE = "qa-system"
TRACKER_DESTINATION = "task-tracker"

# Поля PUT, которые совпадают со столбцами; priority и environment разбираются отдельно.
EDITABLE_COLUMNS = (
    "title",
    "description",
    "repro_steps",
    "expected_result",
    "actual_result",
    "build_version",
    "requirement_ref",
    "epic_ref",
)
REQUIRED_FIELDS = ("title", "actual_result", "severity", "priority")
HISTORY_LABELS = {"proposed_priority": "priority", "environment_id": "environment"}


def list_defects(
    session: Session,
    params: PageParams,
    *,
    status: DefectStatus | None = None,
    severity: Severity | None = None,
    author: str | None = None,
    tracker_mismatch: bool | None = None,
    planning_project_id: str | None = None,
    planning_release_id: str | None = None,
    tracker_iteration_id: str | None = None,
) -> Page[Defect]:
    stmt = select(DefectRow).order_by(DefectRow.created_at.desc(), DefectRow.id)
    if status is not None:
        stmt = stmt.where(DefectRow.status == status)
    if severity is not None:
        stmt = stmt.where(DefectRow.severity == severity)
    if author is not None:
        stmt = stmt.where(DefectRow.author == author)
    if tracker_mismatch is not None:
        stmt = stmt.where(DefectRow.tracker_mismatch == tracker_mismatch)
    plan_refs = {
        TestPlan.planning_project_id: planning_project_id,
        TestPlan.planning_release_id: planning_release_id,
        TestPlan.tracker_iteration_id: tracker_iteration_id,
    }
    for column, value in plan_refs.items():
        if value is not None:
            stmt = stmt.where(DefectRow.plan_id.in_(select(TestPlan.id).where(column == value)))
    return paginate_rows(session, stmt, params, Defect, lambda rows: _models(session, rows))


def read_defect(session: Session, defect_id: uuid.UUID) -> DefectDetail:
    return _detail(session, _get(session, defect_id))


def create_defect(session: Session, data: DefectInput, principal: Principal) -> DefectDetail:
    """Ручной дефект из кейса, шага или результата (FR-DEF-01)."""
    result = run = None
    errors = []
    if data.run_result_id is not None:
        result = session.get(RunResult, data.run_result_id)
        if result is None:
            errors.append({"field": "runResultId", "reason": "not_found"})
        else:
            run = session.get(TestRun, result.run_id)
    case_id = result.test_case_id if result else data.test_case_id
    if result and data.test_case_id not in (None, result.test_case_id):
        errors.append({"field": "testCaseId", "reason": "mismatch"})
    case = session.get(TestCase, case_id) if case_id else None
    if case is None and not errors:
        reason = "required" if case_id is None else "not_found"
        errors.append({"field": "testCaseId", "reason": reason})
    environment_id = _environment_id(session, data.environment, errors)
    if environment_id is None and run is None and "environment" not in _fields(errors):
        errors.append({"field": "environment", "reason": "required"})
    if errors:
        raise validation_failed(errors, "Дефект не прошёл проверку")

    # Шаг ищется в зафиксированной версии результата, иначе — в текущей версии кейса (ADR-003).
    if result is not None:
        version = session.get(TestCaseVersion, result.case_version_id)
    else:
        version = get_version(session, case, case.current_version)
    step = _step(session, data.step_id, version.id, errors)
    priority = data.priority or version.priority
    codes = {"severity": (ClassifierKind.SEVERITY, str(data.severity))}
    if data.priority:
        codes["priority"] = (ClassifierKind.PRIORITY, data.priority)
    errors += check_codes(session, codes)
    if errors:
        raise validation_failed(errors, "Дефект не прошёл проверку")

    defect = DefectRow(
        key=next_key(session, "DEF"),
        origin=DefectOrigin.MANUAL,
        title=data.title,
        description=data.description,
        repro_steps=data.repro_steps,
        expected_result=data.expected_result,
        actual_result=data.actual_result,
        severity=data.severity,
        proposed_priority=priority,
        status=DefectStatus.NEW,
        environment_id=environment_id or run.environment_id,
        build_version=_build_version(run) if run else None,
        author=principal.subject,
        test_case_id=case.id,
        case_version_id=version.id,
        failed_step_id=step.id if step else None,
        plan_id=run.plan_id if run else None,
        requirement_ref=data.requirement_ref or case.requirement_ref,
        epic_ref=data.epic_ref or case.epic_ref,
        created_at=datetime.now(UTC),
    )
    session.add(defect)
    session.flush()
    _log(session, defect, principal.subject, ChangeSource.QA, "status", None, DefectStatus.NEW)
    _enqueue_bug(session, defect, case, run, step)
    if result is not None:
        _link(session, defect, result)
    session.commit()
    return read_defect(session, defect.id)


def update_defect(
    session: Session, defect_id: uuid.UUID, data: DefectUpdate, principal: Principal
) -> DefectDetail:
    defect = _get(session, defect_id, lock=True)
    sent = data.model_dump(exclude_unset=True)
    errors = [
        {"field": field, "reason": "required"}
        for field in REQUIRED_FIELDS
        if field in sent and sent[field] is None
    ]
    changes: dict[str, Any] = {}
    for field in EDITABLE_COLUMNS:
        if field in sent and sent[field] != getattr(defect, field):
            changes[field] = sent[field]
    if sent.get("severity") and sent["severity"] != defect.severity:
        errors += check_codes(
            session, {"severity": (ClassifierKind.SEVERITY, str(sent["severity"]))}
        )
        changes["severity"] = str(sent["severity"])
    if sent.get("priority") and sent["priority"] != defect.proposed_priority:
        # После создания «Ошибки» приоритет исправления ведёт Task Tracker (vision 4.4).
        if defect.tracker_sync_state == TrackerSyncState.SYNCED:
            errors.append({"field": "priority", "reason": "owned_by_tracker"})
        else:
            errors += check_codes(
                session, {"priority": (ClassifierKind.PRIORITY, sent["priority"])}
            )
            changes["proposed_priority"] = sent["priority"]
    if "environment" in sent:
        environment_id = _environment_id(session, sent["environment"], errors)
        if environment_id != defect.environment_id:
            changes["environment_id"] = environment_id
    if errors:
        raise validation_failed(errors, "Дефект не прошёл проверку")

    for field, value in changes.items():
        old, new = getattr(defect, field), value
        if field == "environment_id":
            old, new = _environment_code(session, old), _environment_code(session, new)
        label = HISTORY_LABELS.get(field, to_camel(field))
        _log(session, defect, principal.subject, ChangeSource.QA, label, old, new)
        setattr(defect, field, value)
    session.commit()
    return read_defect(session, defect.id)


def transition(
    session: Session,
    defect_id: uuid.UUID,
    target: DefectStatus,
    comment: str | None,
    principal: Principal,
) -> DefectDetail:
    defect = _get(session, defect_id, lock=True)
    if target in TRACKER_OWNED_STATUSES:
        if not principal.has_any(Role.LEAD):
            raise ApiError(403, "PERMISSION_DENIED", "Статус разработки вручную ставит QA-лид")
        if get_settings().tracker_sync_enabled:
            raise conflict(
                "STATUS_OWNED_BY_TRACKER",
                f"Статус {target} приходит из Task Tracker, пока включён опрос",
            )
    allowed = TRANSITIONS.get(DefectStatus(defect.status), set())
    if target not in allowed:
        raise conflict(
            "INVALID_TRANSITION",
            f"Переход {defect.status} → {target} недопустим",
            [{"field": "to", "reason": "allowed:" + ",".join(sorted(allowed))}],
        )

    previous = defect.status
    try:
        with session.begin_nested():
            defect.status = target
            if target == DefectStatus.CLOSED:
                defect.closed_at = datetime.now(UTC)
            if target == DefectStatus.REOPENED:
                defect.reopen_count += 1
                defect.closed_at = None
            session.flush()
    except IntegrityError:
        # Закрытый автодефект возвращается, а по кейсу уже заведён новый (defect_open_auto_uq).
        other = _open_auto(session, defect.test_case_id)
        raise conflict(
            "INVALID_TRANSITION",
            f"По кейсу уже есть незакрытый автодефект {other.key if other else ''}".strip(),
            [{"field": "to", "reason": f"open-auto:{other.key if other else ''}"}],
        )
    _log(session, defect, principal.subject, ChangeSource.QA, "status", previous, target)
    if comment:
        _comment(session, defect, comment, principal.subject)
    session.commit()
    return read_defect(session, defect.id)


def list_history(session: Session, defect_id: uuid.UUID) -> list[DefectHistoryEntry]:
    defect = _get(session, defect_id)
    rows = session.scalars(
        select(DefectHistory)
        .where(DefectHistory.defect_id == defect.id)
        .order_by(DefectHistory.occurred_at.desc(), DefectHistory.id)
    )
    return [DefectHistoryEntry.model_validate(row) for row in rows]


def add_comment(
    session: Session, defect_id: uuid.UUID, data: DefectCommentInput, principal: Principal
) -> DefectComment:
    defect = _get(session, defect_id)
    comment = _comment(session, defect, data.body, principal.subject)
    _log(session, defect, principal.subject, ChangeSource.QA, "comment", None, data.body)
    session.commit()
    return DefectComment.model_validate(comment)


def register_failure(
    session: Session,
    run: TestRun,
    result: RunResult,
    version: TestCaseVersion,
    failed_step: TestStep | None,
    steps: list[TestStep],
) -> DefectLink:
    """Заводит автодефект по провалу или связывает провал с незакрытым (FR-DEF-02, FR-DEF-03).

    Автор — запустивший прогон (vision 4.4). Фиксирует транзакцию вызывающий код.
    """
    defect = _open_auto(session, result.test_case_id)
    created = False
    if defect is None:
        try:
            with session.begin_nested():
                defect = _insert_auto(session, run, result, version, failed_step, steps)
            created = True
        except IntegrityError:
            defect = _open_auto(session, result.test_case_id)
            if defect is None:
                raise
    if _link(session, defect, result) and not created:
        _log(session, defect, run.started_by, ChangeSource.SYSTEM, "run", None, run.key)
        defect.updated_at = datetime.now(UTC)
    return DefectLink(id=defect.id, key=defect.key, created=created)


def links_of_results(session: Session, result_ids: list[uuid.UUID]) -> dict[uuid.UUID, DefectLink]:
    """Дефект каждого результата; при нескольких связях — самая новая."""
    if not result_ids:
        return {}
    rows = session.execute(
        select(DefectRunLink.run_result_id, DefectRow.id, DefectRow.key)
        .join(DefectRow, DefectRow.id == DefectRunLink.defect_id)
        .where(DefectRunLink.run_result_id.in_(result_ids))
        .order_by(DefectRunLink.created_at)
    )
    return {
        result_id: DefectLink(id=defect_id, key=key, created=False)
        for result_id, defect_id, key in rows
    }


def _insert_auto(
    session: Session,
    run: TestRun,
    result: RunResult,
    version: TestCaseVersion,
    failed_step: TestStep | None,
    steps: list[TestStep],
) -> DefectRow:
    case = session.get(TestCase, result.test_case_id)
    step_prefix = f"Шаг {failed_step.position}: " if failed_step else ""
    defect = DefectRow(
        key=next_key(session, "DEF"),
        origin=DefectOrigin.AUTO,
        title=f"[{case.key}] {step_prefix}{version.title}",
        repro_steps=_repro_steps(version, steps, failed_step),
        expected_result=failed_step.expected_result if failed_step else None,
        actual_result=result.actual_result,
        severity=version.severity,
        proposed_priority=version.priority,
        status=DefectStatus.NEW,
        environment_id=run.environment_id,
        build_version=_build_version(run),
        author=run.started_by,
        test_case_id=case.id,
        case_version_id=version.id,
        failed_step_id=failed_step.id if failed_step else None,
        plan_id=run.plan_id,
        requirement_ref=case.requirement_ref,
        epic_ref=case.epic_ref,
        created_at=datetime.now(UTC),
    )
    session.add(defect)
    session.flush()
    _log(session, defect, run.started_by, ChangeSource.SYSTEM, "status", None, DefectStatus.NEW)
    _enqueue_bug(session, defect, case, run, failed_step)
    return defect


def _repro_steps(
    version: TestCaseVersion, steps: list[TestStep], failed_step: TestStep | None
) -> str:
    """Предусловия и шаги зафиксированной версии до упавшего включительно (vision 4.4)."""
    lines = [f"Предусловия: {version.preconditions}"] if version.preconditions else []
    for step in steps:
        if failed_step is None or step.position <= failed_step.position:
            lines.append(f"{step.position}. {step.action} — ожидается: {step.expected_result}")
    return "\n".join(lines)


def _build_version(run: TestRun) -> str | None:
    parts = [f"{name} {value}" for name, value in sorted((run.sut_versions or {}).items())]
    if run.autotests_commit_sha:
        parts.append(f"autotests {run.autotests_commit_sha}")
    return ", ".join(parts) or None


def _enqueue_bug(
    session: Session,
    defect: DefectRow,
    case: TestCase,
    run: TestRun | None,
    step: TestStep | None,
) -> None:
    """Тело POST /api/v1/bugs по 130, раздел 6.1; поля без значения не передаются."""
    base = get_settings().ui_base_url.rstrip("/")
    environment = session.get(Environment, defect.environment_id)
    payload = {
        "externalSource": TRACKER_SOURCE,
        "externalDefectId": defect.key,
        "title": defect.title,
        "description": _bug_description(defect, case, step),
        "severity": TRACKER_SEVERITY[Severity(defect.severity)],
        "environment": environment.code,
        "build": defect.build_version,
        "testRunUrl": f"{base}/runs/{run.id}" if run else None,
        "testCaseUrl": f"{base}/test-cases/{case.id}",
    }
    session.add(
        OutboxMessage(
            kind=OutboxKind.TRACKER_BUG,
            destination=TRACKER_DESTINATION,
            partition_key=defect.key,
            payload={field: value for field, value in payload.items() if value is not None},
        )
    )


def _bug_description(defect: DefectRow, case: TestCase, step: TestStep | None) -> str:
    sections = [
        ("Описание", defect.description),
        ("Шаги воспроизведения", defect.repro_steps),
        ("Ожидаемый результат", defect.expected_result),
        ("Фактический результат", defect.actual_result),
        ("Серьёзность", defect.severity),
        ("Предложенный приоритет", defect.proposed_priority),
        ("Кейс", case.key),
        ("Шаг", str(step.position) if step else None),
    ]
    return "\n".join(f"{title}: {value}" for title, value in sections if value)


def _link(session: Session, defect: DefectRow, result: RunResult) -> bool:
    """True, если связи ещё не было: результат можно записать повторно."""
    inserted = session.scalar(
        insert(DefectRunLink)
        .values(defect_id=defect.id, run_result_id=result.id, created_at=datetime.now(UTC))
        .on_conflict_do_nothing()
        .returning(DefectRunLink.defect_id)
    )
    return inserted is not None


def _comment(session: Session, defect: DefectRow, body: str, author: str) -> DefectCommentRow:
    comment = DefectCommentRow(
        defect_id=defect.id,
        author=author,
        source=ChangeSource.QA,
        body=body,
        created_at=datetime.now(UTC),
    )
    session.add(comment)
    defect.updated_at = datetime.now(UTC)
    session.flush()
    return comment


def _log(
    session: Session,
    defect: DefectRow,
    author: str,
    source: ChangeSource,
    field: str,
    old: Any,
    new: Any,
) -> None:
    session.add(
        DefectHistory(
            defect_id=defect.id,
            author=author,
            source=source,
            field=field,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
            occurred_at=datetime.now(UTC),
        )
    )


def _open_auto(session: Session, case_id: uuid.UUID | None) -> DefectRow | None:
    return session.scalar(
        select(DefectRow).where(
            DefectRow.test_case_id == case_id,
            DefectRow.origin == DefectOrigin.AUTO,
            DefectRow.status != DefectStatus.CLOSED,
        )
    )


def _environment_id(
    session: Session, code: str | None, errors: list[dict[str, str]]
) -> uuid.UUID | None:
    if code is None:
        return None
    environment = session.scalar(select(Environment).where(Environment.code == code))
    if environment is None:
        errors.append({"field": "environment", "reason": "not_found"})
        return None
    return environment.id


def _environment_code(session: Session, environment_id: uuid.UUID | None) -> str | None:
    environment = session.get(Environment, environment_id) if environment_id else None
    return environment.code if environment else None


def _step(
    session: Session,
    step_id: uuid.UUID | None,
    version_id: uuid.UUID,
    errors: list[dict[str, str]],
) -> TestStep | None:
    if step_id is None:
        return None
    step = session.get(TestStep, step_id)
    if step is None or step.case_version_id != version_id:
        errors.append({"field": "stepId", "reason": "not_found"})
        return None
    return step


def _fields(errors: list[dict[str, str]]) -> set[str]:
    return {error["field"] for error in errors}


def _get(session: Session, defect_id: uuid.UUID, lock: bool = False) -> DefectRow:
    defect = session.get(DefectRow, defect_id, with_for_update=lock or None)
    if defect is None:
        raise not_found("Дефект")
    return defect


def _models(session: Session, defects: list[DefectRow]) -> list[Defect]:
    """Строки дефектов со связями: окружение, ключ кейса, версия, прогоны — запросом на страницу."""
    environment_ids = {d.environment_id for d in defects if d.environment_id}
    case_ids = {d.test_case_id for d in defects if d.test_case_id}
    version_ids = {d.case_version_id for d in defects if d.case_version_id}
    environments = dict(
        session.execute(
            select(Environment.id, Environment.code).where(Environment.id.in_(environment_ids))
        )
        .tuples()
        .all()
    )
    case_keys = dict(
        session.execute(select(TestCase.id, TestCase.key).where(TestCase.id.in_(case_ids)))
        .tuples()
        .all()
    )
    versions = dict(
        session.execute(
            select(TestCaseVersion.id, TestCaseVersion.version).where(
                TestCaseVersion.id.in_(version_ids)
            )
        )
        .tuples()
        .all()
    )
    run_ids: dict[uuid.UUID, list[uuid.UUID]] = {}
    links = session.execute(
        select(DefectRunLink.defect_id, RunResult.run_id)
        .join(RunResult, RunResult.id == DefectRunLink.run_result_id)
        .where(DefectRunLink.defect_id.in_([d.id for d in defects]))
        .order_by(DefectRunLink.created_at)
    )
    for defect_id, run_id in links:
        run_ids.setdefault(defect_id, []).append(run_id)
    return [
        Defect.model_validate(
            {
                **{column: getattr(defect, column) for column in _DEFECT_COLUMNS},
                "priority": defect.proposed_priority,
                "environment": environments.get(defect.environment_id),
                "test_case_key": case_keys.get(defect.test_case_id),
                "case_version": versions.get(defect.case_version_id),
                "step_id": defect.failed_step_id,
                "run_ids": run_ids.get(defect.id, []),
            }
        )
        for defect in defects
    ]


def _detail(session: Session, defect: DefectRow) -> DefectDetail:
    links = session.execute(
        select(
            TestRun.id.label("run_id"),
            TestRun.key.label("run_key"),
            RunResult.id.label("result_id"),
            RunResult.status.label("result_status"),
            DefectRunLink.created_at.label("linked_at"),
        )
        .join(RunResult, RunResult.id == DefectRunLink.run_result_id)
        .join(TestRun, TestRun.id == RunResult.run_id)
        .where(DefectRunLink.defect_id == defect.id)
        .order_by(DefectRunLink.created_at, TestRun.key)
    )
    comments = session.scalars(
        select(DefectCommentRow)
        .where(DefectCommentRow.defect_id == defect.id)
        .order_by(DefectCommentRow.created_at, DefectCommentRow.id)
    )
    return DefectDetail(
        **_models(session, [defect])[0].model_dump(),
        runs=[DefectRun.model_validate(row._asdict()) for row in links],
        comments=[DefectComment.model_validate(comment) for comment in comments],
    )


_DEFECT_COLUMNS = (
    "id",
    "key",
    "origin",
    "title",
    "description",
    "repro_steps",
    "expected_result",
    "actual_result",
    "severity",
    "status",
    "build_version",
    "author",
    "test_case_id",
    "plan_id",
    "requirement_ref",
    "epic_ref",
    "tracker_work_item_id",
    "tracker_work_item_url",
    "tracker_sync_state",
    "tracker_status",
    "tracker_priority",
    "tracker_assignee",
    "tracker_mismatch",
    "reopen_count",
    "created_at",
    "updated_at",
    "closed_at",
)
