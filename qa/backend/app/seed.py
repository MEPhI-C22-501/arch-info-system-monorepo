"""Демонстрационные данные чистой среды: `python -m app seed`.

Источник — JSON-файлы каталога qa/dev/demo-seed (в образе — QA_SEED_DIR). Загрузка
идемпотентна: недостающие записи добавляются, существующие не меняются, чтобы повторный
запуск не затирал правки пользователей. После загрузки key_counter поднимается до последних
номеров демо-ключей, и next_key продолжает нумерацию (TC-RM-05 → TC-RM-06).

План TP-01 с прогоном RUN-01 и дефектом DEF-01 создаются функциями сервисов без фиксации
транзакции, поэтому ключи идут из key_counter, а загрузка остаётся одной транзакцией. Если
TP-01 уже есть, план и прогон не трогаются. Ошибка seed останавливает qa-api, поэтому на томе с
правками кейсы, которые больше не актуальны, просто не попадают в демо-план.
"""

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.admin.schemas import ClassifierInput, EnvironmentInput, TrackerStatusMappingItem
from app.admin.service import write_tracker_mapping
from app.cases.schemas import CaseFilter, TestCaseInput
from app.cases.service import content_of, insert_version, steps_of
from app.db import get_engine
from app.models import (
    ClassifierValue,
    Environment,
    KeyCounter,
    RunResult,
    TestCase,
    TestCaseTemplate,
    TestPlan,
    TestStep,
    TestSuite,
    TestSuiteCase,
    TrackerStatusMapping,
)
from app.models.enums import (
    CaseStatus,
    ResultStatus,
    RunStatus,
    RunTrigger,
    SuiteKind,
    SuitePurpose,
    SuiteStatus,
)
from app.plans.schemas import TestPlanInput
from app.plans.service import activate, insert_cases, insert_plan
from app.runs.schemas import ResultInput, StepResultInput
from app.runs.service import finish, insert_run, plan_composition, start, write_result
from app.templates.schemas import TemplateInput

SEED_DIR = Path(os.getenv("QA_SEED_DIR", Path(__file__).resolve().parents[2] / "dev" / "demo-seed"))
SEED_AUTHOR = "demo-seed"
KEY_PATTERN = re.compile(r"^(?P<prefix>.+)-(?P<number>\d+)$")


def load(session: Session, directory: Path = SEED_DIR) -> Counter[str]:
    """Загружает все файлы каталога в одной транзакции; возвращает число добавленных записей."""
    created: Counter[str] = Counter()
    created["classifiers"] = load_classifiers(session, directory)
    created["environments"] = _load_environments(session, _read(directory, "environments"))
    created["templates"] = _load_templates(session, _read(directory, "templates"))
    cases = _read(directory, "test-cases")
    created["test-cases"] = _load_cases(session, cases)
    _raise_key_counters(session, [row["key"] for row in cases])
    created["suites"] = _load_suites(session, _read(directory, "suites"))
    created["tracker-status-mapping"] = _load_tracker_mapping(
        session, _read(directory, "tracker-status-mapping")
    )
    created["plans"] = _load_plans(session, _read(directory, "plans"))
    session.commit()
    return created


def load_classifiers(session: Session, directory: Path = SEED_DIR) -> int:
    rows = [ClassifierInput.model_validate(row) for row in _read(directory, "classifiers")]
    existing = set(session.execute(select(ClassifierValue.kind, ClassifierValue.code)))
    new = [row for row in rows if (row.kind, row.code) not in existing]
    session.add_all(ClassifierValue(**row.model_dump()) for row in new)
    session.flush()
    return len(new)


def _load_environments(session: Session, rows: list[dict[str, Any]]) -> int:
    existing = set(session.scalars(select(Environment.code)))
    new = [EnvironmentInput.model_validate(row) for row in rows if row["code"] not in existing]
    session.add_all(Environment(**row.model_dump()) for row in new)
    session.flush()
    return len(new)


def _load_templates(session: Session, rows: list[dict[str, Any]]) -> int:
    existing = set(session.scalars(select(TestCaseTemplate.name)))
    new = [TemplateInput.model_validate(row) for row in rows if row["name"] not in existing]
    for row in new:
        body = row.body.model_dump(by_alias=True, exclude_none=True, mode="json")
        session.add(TestCaseTemplate(**row.model_dump(exclude={"body"}), body=body))
    session.flush()
    return len(new)


def _load_cases(session: Session, rows: list[dict[str, Any]]) -> int:
    existing = set(session.scalars(select(TestCase.key)))
    count = 0
    for row in rows:
        if row["key"] in existing:
            continue
        data = TestCaseInput.model_validate(row)
        if not row["key"].startswith(f"TC-{data.module}-"):
            raise ValueError(f"Ключ {row['key']} не соответствует модулю {data.module}")
        case = TestCase(
            key=row["key"],
            status=row.get("status", CaseStatus.ACTUAL),
            current_version=1,
            module=data.module,
            feature_ref=data.feature_ref,
            epic_ref=data.epic_ref,
            requirement_ref=data.requirement_ref,
            created_by=SEED_AUTHOR,
        )
        session.add(case)
        session.flush()
        insert_version(session, case, 1, content_of(data), steps_of(data), [], SEED_AUTHOR)
        count += 1
    return count


def _load_suites(session: Session, rows: list[dict[str, Any]]) -> int:
    """caseKeys — состав ручного набора; filterSuite — имя ручного набора в условии отбора."""
    names = set(session.scalars(select(TestSuite.name)))
    # «Smoke» и «Приёмка стенда» единственны: переименованный лидом набор не создаётся заново.
    purposes = set(session.scalars(select(TestSuite.purpose))) - {SuitePurpose.GENERAL}
    count = 0
    for row in rows:
        if row["name"] in names or row["purpose"] in purposes:
            continue
        names.add(row["name"])
        purposes.add(row["purpose"])
        suite_filter = None
        if row["kind"] == SuiteKind.FILTER:
            suite_filter = dict(row["filter"])
            if "filterSuite" in row:
                suite_filter["suiteId"] = str(
                    session.scalar(select(TestSuite.id).where(TestSuite.name == row["filterSuite"]))
                )
            CaseFilter.model_validate(suite_filter)
        suite = TestSuite(
            name=row["name"],
            kind=row["kind"],
            filter=suite_filter,
            status=SuiteStatus.ACTIVE,
            purpose=row["purpose"],
            owner=SEED_AUTHOR,
        )
        session.add(suite)
        session.flush()
        case_ids = session.scalars(
            select(TestCase.id).where(TestCase.key.in_(row.get("caseKeys", [])))
        )
        session.add_all(TestSuiteCase(suite_id=suite.id, test_case_id=i) for i in case_ids)
        session.flush()
        count += 1
    return count


def _load_tracker_mapping(session: Session, rows: list[dict[str, Any]]) -> int:
    existing = set(session.scalars(select(TrackerStatusMapping.tracker_status_id)))
    new = [TrackerStatusMappingItem.model_validate(row) for row in rows]
    new = [row for row in new if row.tracker_status_id not in existing]
    return write_tracker_mapping(session, new, SEED_AUTHOR)


def _load_plans(session: Session, rows: list[dict[str, Any]]) -> int:
    existing = set(session.scalars(select(TestPlan.key)))
    count = 0
    for row in rows:
        if row["key"] in existing:
            continue
        plan = insert_plan(session, TestPlanInput.model_validate(row))
        suite_id = select(TestSuite.id).where(TestSuite.name == row["casesFromSuite"])
        cases = session.execute(
            select(TestCase.id, TestCase.key, TestCase.status)
            .join(TestSuiteCase, TestSuiteCase.test_case_id == TestCase.id)
            .where(
                TestSuiteCase.suite_id.in_(suite_id),
                TestCase.status == CaseStatus.ACTUAL,
            )
            .order_by(TestCase.key)
        )
        insert_cases(
            session, plan, [dict(case._mapping) | {"field": "ids"} for case in cases], SEED_AUTHOR
        )
        activate(session, plan)
        _load_run(session, plan, row["run"])
        count += 1
    return count


def _load_run(session: Session, plan: TestPlan, row: dict[str, Any]) -> None:
    environment_id = session.scalar(
        select(Environment.id).where(Environment.code == row["environment"])
    )
    run = insert_run(
        session,
        plan_id=plan.id,
        suite_id=None,
        environment_id=environment_id,
        trigger=RunTrigger.MANUAL,
        started_by=SEED_AUTHOR,
        composition=plan_composition(session, plan.id),
    )
    start(session, run)
    results = {
        key: result
        for key, result in session.execute(
            select(TestCase.key, RunResult)
            .join(RunResult, RunResult.test_case_id == TestCase.id)
            .where(RunResult.run_id == run.id)
        )
        .tuples()
        .all()
    }
    for key in row["passed"]:
        if key in results:
            passed = ResultInput(status=ResultStatus.PASSED)
            write_result(session, run, results[key], passed, SEED_AUTHOR)
    failed = row["failed"]
    if failed["case"] in results:
        result = results[failed["case"]]
        step_id = session.scalar(
            select(TestStep.id).where(
                TestStep.case_version_id == result.case_version_id,
                TestStep.position == failed["step"],
            )
        )
        data = ResultInput(
            status=ResultStatus.FAILED,
            steps=[
                StepResultInput(
                    step_id=step_id,
                    status=ResultStatus.FAILED,
                    actual_result=failed["actualResult"],
                )
            ],
        )
        write_result(session, run, result, data, SEED_AUTHOR)
    if run.status == RunStatus.IN_PROGRESS:
        finish(run, RunStatus.COMPLETED)


def _raise_key_counters(session: Session, keys: list[str]) -> None:
    last: dict[str, int] = {}
    for key in keys:
        match = KEY_PATTERN.match(key)
        prefix, number = match["prefix"], int(match["number"])
        last[prefix] = max(last.get(prefix, 0), number)
    for prefix, number in last.items():
        stmt = insert(KeyCounter).values(prefix=prefix, last_value=number)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[KeyCounter.prefix],
                set_={"last_value": func.greatest(KeyCounter.last_value, stmt.excluded.last_value)},
            )
        )


def _read(directory: Path, name: str) -> list[dict[str, Any]]:
    return json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))


def main() -> None:
    with Session(get_engine()) as session:
        created = load(session)
    print("Демо-данные загружены из", SEED_DIR, dict(created))
