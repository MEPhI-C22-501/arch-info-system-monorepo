"""Демонстрационные данные чистой среды: `python -m app seed`.

Источник — JSON-файлы каталога qa/dev/demo-seed (в образе — QA_SEED_DIR). Загрузка
идемпотентна: недостающие записи добавляются, существующие не меняются, чтобы повторный
запуск не затирал правки пользователей. После загрузки key_counter поднимается до последних
номеров демо-ключей, и next_key продолжает нумерацию (TC-RM-05 → TC-RM-06).
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

from app.admin.schemas import ClassifierInput, EnvironmentInput
from app.cases.schemas import CaseFilter, TestCaseInput
from app.cases.service import content_of, insert_version, steps_of
from app.db import get_engine
from app.models import (
    ClassifierValue,
    Environment,
    KeyCounter,
    TestCase,
    TestCaseTemplate,
    TestSuite,
    TestSuiteCase,
)
from app.models.enums import CaseStatus, SuiteKind, SuitePurpose, SuiteStatus
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
