"""Схема БД: миграции совпадают с моделями, ограничения из 120 и ADR работают."""

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import IntegrityError

from app.models import Base, Defect, Environment, TestCase, TestRun, TestSuite


def test_models_match_migrations(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], "Модели изменены без миграции: alembic revision --autogenerate"


def make_case(session, key: str = "TC-QA-01") -> TestCase:
    case = TestCase(key=key, status="DRAFT", current_version=1, module="QA", created_by="t")
    session.add(case)
    session.flush()
    return case


def make_defect(session, case: TestCase, *, origin: str = "AUTO", status: str = "NEW") -> Defect:
    defect = Defect(
        key=f"DEF-{uuid.uuid4().hex[:6]}",
        origin=origin,
        title="Падение",
        actual_result="500",
        severity="MAJOR",
        proposed_priority="P2",
        status=status,
        author="qa-executor",
        test_case_id=case.id,
    )
    session.add(defect)
    session.flush()
    return defect


def assert_rejected(session, build) -> None:
    with pytest.raises(IntegrityError), session.begin_nested():
        build()
        session.flush()


def test_one_open_auto_defect_per_case(db_session):
    case = make_case(db_session)
    make_defect(db_session, case)

    assert_rejected(db_session, lambda: make_defect(db_session, case))
    make_defect(db_session, case, origin="MANUAL")
    make_defect(db_session, make_case(db_session, "TC-QA-02"))


def test_closed_auto_defect_allows_new_one(db_session):
    case = make_case(db_session)
    make_defect(db_session, case, status="CLOSED")
    make_defect(db_session, case)


def test_run_needs_exactly_one_source(db_session):
    env = Environment(code="dev", name="dev", base_urls={})
    db_session.add(env)
    db_session.flush()

    assert_rejected(
        db_session,
        lambda: db_session.add(
            TestRun(
                key="RUN-01",
                environment_id=env.id,
                status="CREATED",
                trigger="MANUAL",
                started_by="t",
            )
        ),
    )


def test_single_smoke_suite(db_session):
    def smoke(name: str) -> TestSuite:
        suite = TestSuite(name=name, kind="MANUAL", status="ACTIVE", purpose="SMOKE", owner="t")
        db_session.add(suite)
        return suite

    smoke("Smoke")
    db_session.flush()
    assert_rejected(db_session, lambda: smoke("Smoke 2"))


def test_unknown_status_rejected(db_session):
    assert_rejected(
        db_session,
        lambda: db_session.add(
            TestCase(key="TC-QA-09", status="DONE", current_version=1, module="QA", created_by="t")
        ),
    )
